"""Vinted publish on the local machine: data from remote API, nodriver here."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.desktop_stubs_service import DesktopStubsService
from services.vinted_batch_orchestrator_service import VintedBatchOrchestratorService
from services.vinted_batch_session_service import VintedBatchSessionService as batch_hub
from services.vinted_progress_session_service import VintedProgressSessionService as vp
from services.vinted_publish_service import publish_article_to_vinted
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
                vid_found: int | None = None
                try:
                    tab_x = VintedService._require_tab()
                    sp = article.sell_price
                    vid_found = await VintedService.find_member_listing_item_id_for_match(
                        tab_x,
                        title=article.title or "",
                        sell_price=float(sp) if sp is not None else None,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "vinted_id resolve after publish failed article_id=%s: %s",
                        article_id,
                        exc,
                    )
                payload: dict[str, Any] = {}
                if vid_found is not None:
                    payload["vinted_id"] = vid_found
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
    ) -> None:
        """Delete the Vinted listing in Chrome and call ``confirm-vinted-unlist`` on success."""
        hdrs = _headers(token)
        hdrs_json = {**hdrs, "Content-Type": "application/json"}
        browser_started = False
        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    return
                if not article_d.get("published_on_vinted"):
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
            email = user.vinted_email or ""
            password = pwd_plain or ""
            if not email or not password:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        f"{remote_base}/articles/{article_id}/fail-vinted-cross-removal",
                        headers=hdrs_json,
                        json={"detail": "Identifiants Vinted manquants (paramètres ou worker)."},
                    )
                return

            raw_vid = article_d.get("vinted_id")
            item_id = int(raw_vid) if raw_vid is not None else None

            browser_started = await VintedService.ensure_browser_session()
            await VintedService.ensure_sign_in(email, password, form_progress=None)
            tab = VintedService._require_tab()
            if item_id is None:
                sp = article.sell_price
                item_id = await VintedService.find_member_listing_item_id_for_match(
                    tab,
                    title=article.title or "",
                    sell_price=float(sp) if sp is not None else None,
                )
            if item_id is None:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        f"{remote_base}/articles/{article_id}/fail-vinted-cross-removal",
                        headers=hdrs_json,
                        json={
                            "detail": "Annonce Vinted introuvable sur le dressing (recoupement titre/prix).",
                        },
                    )
                return
            await VintedService.delete_vinted_item_listing(tab, int(item_id))
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{remote_base}/articles/{article_id}/confirm-vinted-unlist",
                    headers=hdrs,
                )
                r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vinted listing removal failed article_id=%s", article_id)
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    await client.post(
                        f"{remote_base}/articles/{article_id}/fail-vinted-cross-removal",
                        headers=hdrs_json,
                        json={"detail": str(exc)[:480]},
                    )
            except Exception:
                pass
        finally:
            if browser_started:
                try:
                    VintedService.close_browser()
                except Exception:
                    pass

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

            async def mark_pub(aid: int, uid: int) -> None:
                _ = uid
                async with httpx.AsyncClient(timeout=60.0) as c:
                    r = await c.post(
                        f"{remote_base}/articles/{aid}/confirm-vinted-publish",
                        headers=hdrs,
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
