"""Vinted publish on the local machine: data from remote API, nodriver here."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app_types.vinted import VintedListingRemovalOutcome
from services.desktop_stubs_service import DesktopStubsService
from services.vinted_batch_orchestrator_service import VintedBatchOrchestratorService
from services.vinted_batch_session_service import VintedBatchSessionService as batch_hub
from services.vinted_progress_session_service import VintedProgressSessionService as vp
from services.vinted_publish_service import ProgressFn, listed_vinted_price, publish_article_to_vinted
from services.vinted_service import VintedService

logger = logging.getLogger(__name__)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


class DesktopVintedRunnerService:
    """Vinted publish for the local HTTP worker."""

    @staticmethod
    async def run_desktop_vinted_publish_job(article_id: int, user_id: int, token: str, remote_base: str) -> None:
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    await vp.finish(article_id, {"vinted": {"published": False, "detail": "forbidden"}})
                    return
                cr = await client.get(f"{remote_base}/users/me/vinted-decrypted", headers=hdrs)
                cr.raise_for_status()
                creds: dict[str, Any] = cr.json()
                me = await client.get(f"{remote_base}/users/me", headers=hdrs)
                me.raise_for_status()
                me_d = me.json()

            article = DesktopStubsService.article_from_api_dict(article_d)
            user = DesktopStubsService.user_stub(me_d["id"], me_d["email"], creds.get("vinted_email"))
            pwd_plain = creds.get("vinted_password")
            image_urls = [im["image_url"] for im in article_d.get("images") or []]

            async def on_progress(ev: dict[str, Any]) -> None:
                await vp.emit(article_id, ev)

            result = await publish_article_to_vinted(
                article,
                user,
                image_urls,
                progress=on_progress,
                vinted_password_plain=pwd_plain,
            )
            if bool(result.get("published")):
                vinted_id = result.get("vinted_id")
                payload: dict[str, Any] = {"vinted_id": vinted_id} if isinstance(vinted_id, int) else {}
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(
                        f"{remote_base}/articles/{article_id}/confirm-vinted-publish",
                        headers={**hdrs, "Content-Type": "application/json"},
                        json=payload,
                    )
                    try:
                        r.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.warning("confirm-vinted-publish failed article_id=%s: %s", article_id, exc)
            await vp.finish(article_id, {"vinted": result})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Desktop Vinted publish failed article_id=%s", article_id)
            await vp.finish(article_id, {"vinted": {"published": False, "detail": str(exc)}})
        finally:
            vp.cleanup_later(article_id)

    @staticmethod
    def _article_needs_vinted_unlist(article_d: dict[str, Any]) -> bool:
        """True when GoupixDex still expects a live Vinted listing to be removed."""
        return bool(
            article_d.get("is_sold")
            and str(article_d.get("sale_source") or "").lower() == "ebay"
            and article_d.get("published_on_vinted")
        )

    @staticmethod
    async def _run_vinted_listing_removal(
        article_id: int,
        user_id: int,
        token: str,
        remote_base: str,
        *,
        progress: ProgressFn | None = None,
        batch_position_label: str = "",
    ) -> VintedListingRemovalOutcome:
        """
        Supprime l’annonce Vinted dans Chrome puis confirme le retrait à GoupixDex, ou y enregistre l’échec.

        Args:
            article_id: Article GoupixDex dont l’annonce Vinted doit disparaître.
            user_id: Propriétaire attendu de l’article.
            token: JWT de l’utilisateur pour l’API distante.
            remote_base: URL de l’API GoupixDex.
            progress: Journal du lot où écrire chaque étape, optionnel.
            batch_position_label: Position dans le lot (``"1/3"``) en tête de chaque ligne de journal.

        Returns:
            Le résultat réel : ``delisted`` n’est vrai que si Vinted ne liste plus l’annonce.
        """
        hdrs = _headers(token)
        hdrs_json = {**hdrs, "Content-Type": "application/json"}
        log_prefix = f"{batch_position_label} — " if batch_position_label else ""

        async def log_step(message: str, form_step: str) -> None:
            """Écrit une étape du retrait dans le journal du lot, s’il y en a un."""
            if progress is not None:
                await progress(
                    {"type": "log", "step": "delist", "message": f"{log_prefix}{message}", "form_step": form_step}
                )

        async def record_failure(detail: str, vinted_id: int | None) -> VintedListingRemovalOutcome:
            """Journalise l’échec, l’enregistre sur l’article et le renvoie."""
            await log_step(f"Échec du retrait : {detail}", "failed")
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    await client.post(
                        f"{remote_base}/articles/{article_id}/fail-vinted-cross-removal",
                        headers=hdrs_json,
                        json={"detail": detail[:480]},
                    )
            except httpx.HTTPError as exc:
                logger.warning("fail-vinted-cross-removal failed article_id=%s: %s", article_id, exc)
            return {"article_id": article_id, "delisted": False, "vinted_id": vinted_id, "detail": detail}

        browser_started = False
        item_id: int | None = None
        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    return {
                        "article_id": article_id,
                        "delisted": False,
                        "vinted_id": None,
                        "detail": "Article introuvable sur ce compte.",
                    }
                if not article_d.get("published_on_vinted"):
                    await log_step("Aucune annonce Vinted active dans GoupixDex — rien à retirer.", "delisted")
                    return {
                        "article_id": article_id,
                        "delisted": True,
                        "vinted_id": None,
                        "detail": "Déjà retiré de Vinted.",
                    }

                cr = await client.get(f"{remote_base}/users/me/vinted-decrypted", headers=hdrs)
                cr.raise_for_status()
                creds: dict[str, Any] = cr.json()
                me = await client.get(f"{remote_base}/users/me", headers=hdrs)
                me.raise_for_status()
                me_d = me.json()

            article = DesktopStubsService.article_from_api_dict(article_d)
            user = DesktopStubsService.user_stub(me_d["id"], me_d["email"], creds.get("vinted_email"))
            pwd_plain = creds.get("vinted_password")
            email = user.vinted_email or ""
            password = pwd_plain or ""
            if not email or not password:
                return await record_failure("Identifiants Vinted manquants (paramètres ou worker).", None)

            raw_vid = article_d.get("vinted_id")
            item_id = int(raw_vid) if raw_vid is not None else None

            await log_step("Connexion à Vinted…", "auth")
            browser_started = await VintedService.ensure_browser_session()
            await VintedService.ensure_sign_in(email, password, form_progress=None)
            tab = VintedService._require_tab()
            if item_id is None:
                await log_step(f"Recherche de l’annonce « {article.title} » sur votre dressing…", "search")
                item_id = await VintedService.find_member_listing_item_id_for_match(
                    tab,
                    title=article.title or "",
                    sell_price=listed_vinted_price(article),
                )
            if item_id is None:
                return await record_failure(
                    "Annonce introuvable sur votre dressing Vinted (titre ou prix modifié depuis la publication ?).",
                    None,
                )
            await log_step(f"Suppression de l’annonce Vinted #{item_id}…", "delete")
            await VintedService.delete_vinted_item_listing(tab, item_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vinted listing removal failed article_id=%s", article_id)
            return await record_failure(str(exc) or type(exc).__name__, item_id)
        finally:
            if browser_started:
                try:
                    VintedService.close_browser()
                except Exception:
                    pass

        await log_step(f"Annonce Vinted #{item_id} supprimée.", "delisted")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{remote_base}/articles/{article_id}/confirm-vinted-unlist",
                    headers=hdrs_json,
                    json={"hide_when_off_all_platforms": True},
                )
                r.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("confirm-vinted-unlist failed article_id=%s: %s", article_id, exc)
            return {
                "article_id": article_id,
                "delisted": True,
                "vinted_id": item_id,
                "detail": "Supprimée sur Vinted, mais la fiche GoupixDex n’a pas pu être mise à jour.",
            }
        return {"article_id": article_id, "delisted": True, "vinted_id": item_id, "detail": None}

    @staticmethod
    async def run_remove_vinted_listing(article_id: int, user_id: int, token: str, remote_base: str) -> None:
        """Retire l’annonce Vinted depuis la fiche article (worker local)."""
        await DesktopVintedRunnerService._run_vinted_listing_removal(article_id, user_id, token, remote_base)

    @staticmethod
    async def run_vinted_unlist_after_ebay_sale(article_id: int, user_id: int, token: str, remote_base: str) -> None:
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    return
                if not DesktopVintedRunnerService._article_needs_vinted_unlist(article_d):
                    logger.info(
                        "Vinted unlist skipped article_id=%s (not pending / already unlisted in GoupixDex)",
                        article_id,
                    )
                    return
        except Exception:
            logger.exception("Vinted unlist precheck failed article_id=%s", article_id)
            return
        await DesktopVintedRunnerService._run_vinted_listing_removal(article_id, user_id, token, remote_base)

    @staticmethod
    async def run_desktop_vinted_batch_job(
        job_id: str,
        user_id: int,
        article_ids: list[int],
        token: str,
        remote_base: str,
    ) -> None:
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                me_r = await client.get(f"{remote_base}/users/me", headers=hdrs)
                me_r.raise_for_status()
                me_d = me_r.json()
                cred_r = await client.get(f"{remote_base}/users/me/vinted-decrypted", headers=hdrs)
                cred_r.raise_for_status()
                creds: dict[str, Any] = cred_r.json()

                items: list[tuple[Any, list[str]]] = []
                for aid in article_ids:
                    ar = await client.get(f"{remote_base}/articles/{aid}", headers=hdrs)
                    if ar.status_code == 404:
                        continue
                    ar.raise_for_status()
                    d = ar.json()
                    if d.get("user_id") != user_id:
                        continue
                    urls = [im["image_url"] for im in d.get("images") or []]
                    if not urls:
                        continue
                    items.append((DesktopStubsService.article_from_api_dict(d), urls))

            if not items:
                await batch_hub.emit_event(
                    job_id,
                    {
                        "type": "log",
                        "step": "error",
                        "message": "No valid articles (missing or no images).",
                        "form_step": "failed",
                    },
                )
                await batch_hub.finish_job(
                    job_id,
                    {
                        "summary": [],
                        "vinted": {"published": False, "detail": "no_valid_articles"},
                    },
                )
                batch_hub.clear_active_job_for_user(user_id)
                batch_hub.cleanup_later(job_id)
                return

            user = DesktopStubsService.user_stub(me_d["id"], me_d["email"], creds.get("vinted_email"))
            pwd_plain = creds.get("vinted_password")

            async def mark_pub(aid: int, uid: int, vinted_id: int | None) -> None:
                _ = uid
                async with httpx.AsyncClient(timeout=60.0) as c:
                    r = await c.post(
                        f"{remote_base}/articles/{aid}/confirm-vinted-publish",
                        headers=hdrs,
                        json={"vinted_id": vinted_id} if vinted_id is not None else None,
                    )
                    r.raise_for_status()

            await VintedBatchOrchestratorService.run_vinted_batch_job(
                job_id,
                user_id,
                items,
                user,
                vinted_password_plain=pwd_plain,
                mark_published=mark_pub,
            )
        except Exception:
            logger.exception("Desktop Vinted batch crashed job_id=%s", job_id)
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "error",
                    "message": "Erreur interne du lot (worker local).",
                    "form_step": "failed",
                },
            )
            await batch_hub.finish_job(
                job_id,
                {"summary": [], "vinted": {"published": False, "detail": "internal_error"}},
            )
            batch_hub.clear_active_job_for_user(user_id)
            batch_hub.cleanup_later(job_id)

    @staticmethod
    async def run_desktop_vinted_batch_delist_job(
        job_id: str,
        user_id: int,
        article_ids: list[int],
        token: str,
        remote_base: str,
    ) -> None:
        """Retire plusieurs annonces Vinted (une session Chrome chacune) et écrit le résultat réel de chaque retrait dans le journal du lot."""
        n = len(article_ids)
        summary: list[VintedListingRemovalOutcome] = []

        async def forward_progress(ev: dict[str, Any]) -> None:
            """Relaie les étapes d’un retrait dans le journal du lot."""
            await batch_hub.emit_event(job_id, ev)

        try:
            await batch_hub.emit_event(
                job_id,
                {"type": "log", "step": "prep", "message": f"Retrait Vinted — {n} article(s)…", "form_step": "prep"},
            )
            for i, aid in enumerate(article_ids):
                await batch_hub.emit_event(
                    job_id,
                    {
                        "type": "progress",
                        "current": i + 1,
                        "total": n,
                        "article_id": aid,
                    },
                )
                summary.append(
                    await DesktopVintedRunnerService._run_vinted_listing_removal(
                        aid,
                        user_id,
                        token,
                        remote_base,
                        progress=forward_progress,
                        batch_position_label=f"{i + 1}/{n}",
                    )
                )
            removed_count = sum(1 for outcome in summary if outcome["delisted"])
            has_removed_all = removed_count == n
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "done" if has_removed_all else "error",
                    "message": f"Retrait terminé : {removed_count}/{n} annonce(s) retirée(s) de Vinted.",
                    "form_step": "done" if has_removed_all else "failed",
                },
            )
            await batch_hub.finish_job(
                job_id,
                {
                    "summary": summary,
                    "vinted": {"delisted": has_removed_all, "count": n, "removed": removed_count},
                },
            )
        except Exception:
            logger.exception("Vinted batch delist crashed job_id=%s", job_id)
            await batch_hub.finish_job(
                job_id,
                {"summary": summary, "vinted": {"delisted": False, "detail": "internal_error"}},
            )
        finally:
            batch_hub.clear_active_job_for_user(user_id)
            batch_hub.cleanup_later(job_id)

    @staticmethod
    async def run_desktop_vinted_batch_refresh_job(
        job_id: str,
        user_id: int,
        article_ids: list[int],
        token: str,
        remote_base: str,
    ) -> None:
        """Supprime puis republie sur Vinted (annonces neuves)."""
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                await client.post(
                    f"{remote_base}/articles/bulk-prepare-for-sale",
                    headers={**hdrs, "Content-Type": "application/json"},
                    json={"ids": article_ids},
                )
        except Exception:
            logger.exception("bulk-prepare-for-sale before refresh failed")

        to_delist: list[int] = []
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                for aid in article_ids:
                    ar = await client.get(f"{remote_base}/articles/{aid}", headers=hdrs)
                    if ar.status_code != 200:
                        continue
                    d = ar.json()
                    if d.get("user_id") != user_id:
                        continue
                    if d.get("published_on_vinted"):
                        to_delist.append(aid)
        except Exception:
            logger.exception("Vinted refresh preflight failed")

        if to_delist:
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "prep",
                    "message": f"Suppression de {len(to_delist)} annonce(s) existante(s)…",
                    "form_step": "prep",
                },
            )
            for aid in to_delist:
                await DesktopVintedRunnerService._run_vinted_listing_removal(aid, user_id, token, remote_base)

        await batch_hub.emit_event(
            job_id,
            {"type": "log", "step": "prep", "message": "Republication sur Vinted…", "form_step": "prep"},
        )
        await DesktopVintedRunnerService.run_desktop_vinted_batch_job(
            job_id, user_id, article_ids, token, remote_base
        )
