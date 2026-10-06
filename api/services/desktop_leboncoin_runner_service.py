"""Leboncoin publish on the local machine: metadata from remote API, nodriver here."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app_types.leboncoin import LeboncoinListingRemovalOutcome
from services.desktop_api_confirmation_service import post_confirmation_to_api
from services.desktop_stubs_service import DesktopStubsService
from services.leboncoin_listing_copy import build_leboncoin_listing_copy
from services.leboncoin_publish_service import ProgressFn, publish_article_to_leboncoin
from services.leboncoin_service import LeboncoinService
from services.vinted_batch_session_service import VintedBatchSessionService as batch_hub
from services.vinted_progress_session_service import VintedProgressSessionService as progress_hub

logger = logging.getLogger(__name__)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


class DesktopLeboncoinRunnerService:
    @staticmethod
    async def _publish_article(
        article_id: int,
        user_id: int,
        token: str,
        remote_base: str,
        *,
        progress: ProgressFn,
    ) -> dict[str, Any]:
        """
        Publie un article sur Leboncoin dans le Chrome local, puis confirme la publication à GoupixDex.

        Returns:
            Le résultat (``published``, ``detail``, ``listing_id``) : une erreur devient un échec, jamais une exception.
        """
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    return {"published": False, "detail": "forbidden"}
                sr = await client.get(f"{remote_base}/settings", headers=hdrs)
                sr.raise_for_status()
                settings_d = sr.json()
                postal = (settings_d.get("sender_postal_code") or "").strip()
                line1 = (settings_d.get("sender_line1") or "").strip()
                city = (settings_d.get("sender_city") or "").strip()

            article = DesktopStubsService.article_from_api_dict(article_d)
            image_urls = [im["image_url"] for im in article_d.get("images") or []]
            has_recorded_publication = False

            async def record_publication(listing_id: str | None = None) -> None:
                """Enregistre la publication dans GoupixDex, avec l'identifiant de l'annonce quand il est connu."""
                nonlocal has_recorded_publication
                try:
                    await post_confirmation_to_api(
                        f"{remote_base}/articles/{article_id}/confirm-leboncoin-publish",
                        {**hdrs, "Content-Type": "application/json"},
                        {"listing_id": listing_id} if listing_id else {},
                    )
                    has_recorded_publication = True
                except httpx.HTTPError as exc:
                    logger.warning("confirm-leboncoin-publish failed article_id=%s: %s", article_id, exc)

            result = await publish_article_to_leboncoin(
                article,
                image_urls,
                postal_code=postal,
                sender_line1=line1,
                sender_city=city,
                progress=progress,
                on_deposited=record_publication,
            )
            if bool(result.get("published")) and (result.get("listing_id") or not has_recorded_publication):
                await record_publication(result.get("listing_id"))
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Desktop Leboncoin publish failed article_id=%s", article_id)
            return {"published": False, "detail": str(exc)}

    @staticmethod
    async def _remove_article_listing(
        article_id: int,
        user_id: int,
        token: str,
        remote_base: str,
        *,
        open_browser: Callable[[], Awaitable[None]],
    ) -> LeboncoinListingRemovalOutcome:
        """
        Supprime l’annonce Leboncoin d’un article puis enregistre le résultat (ou l’erreur) sur sa fiche GoupixDex.

        Returns:
            Le résultat réel : ``delisted`` n’est vrai que si l’annonce n’est plus en vente sur Leboncoin.
        """
        hdrs = _headers(token)
        hdrs_json = {**hdrs, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
            if article_d.get("user_id") != user_id:
                return {"article_id": article_id, "delisted": False, "detail": "Article introuvable sur ce compte."}
            if not article_d.get("published_on_leboncoin"):
                return {"article_id": article_id, "delisted": True, "detail": "Déjà retirée de Leboncoin."}
            await open_browser()
            listing_title, _ = build_leboncoin_listing_copy(DesktopStubsService.article_from_api_dict(article_d))
            was_online = await LeboncoinService.delete_listing(article_d.get("leboncoin_listing_id"), listing_title)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Leboncoin listing removal failed article_id=%s", article_id)
            detail = (str(exc) or type(exc).__name__)[:480]
            try:
                await post_confirmation_to_api(
                    f"{remote_base}/articles/{article_id}/fail-leboncoin-cross-removal",
                    hdrs_json,
                    {"detail": detail},
                )
            except httpx.HTTPError as report_exc:
                logger.warning("fail-leboncoin-cross-removal failed article_id=%s: %s", article_id, report_exc)
            return {"article_id": article_id, "delisted": False, "detail": detail}
        try:
            await post_confirmation_to_api(
                f"{remote_base}/articles/{article_id}/confirm-leboncoin-unlist",
                hdrs_json,
                {},
            )
        except httpx.HTTPError as exc:
            logger.warning("confirm-leboncoin-unlist failed article_id=%s: %s", article_id, exc)
            return {
                "article_id": article_id,
                "delisted": True,
                "detail": "Retirée de Leboncoin, mais la fiche GoupixDex n’a pas pu être mise à jour.",
            }
        return {
            "article_id": article_id,
            "delisted": True,
            "detail": None if was_online else "Annonce déjà absente de « Mes annonces » sur Leboncoin.",
        }

    @staticmethod
    async def run_leboncoin_listings_removal(
        article_ids: list[int],
        user_id: int,
        token: str,
        remote_base: str,
    ) -> list[LeboncoinListingRemovalOutcome]:
        """
        Supprime sur Leboncoin les annonces de ces articles, l’une après l’autre dans un même Chrome.

        Returns:
            Le résultat de chaque article, dans l’ordre demandé.
        """
        async with LeboncoinService.browser_job_lock:
            is_browser_open = False

            async def open_browser() -> None:
                """Ouvre Chrome au premier article qui a une annonce à supprimer."""
                nonlocal is_browser_open
                if not is_browser_open:
                    await LeboncoinService.init_browser()
                    is_browser_open = True
                    await LeboncoinService.init_page("about:blank")

            try:
                return [
                    await DesktopLeboncoinRunnerService._remove_article_listing(
                        article_id, user_id, token, remote_base, open_browser=open_browser
                    )
                    for article_id in article_ids
                ]
            finally:
                if is_browser_open:
                    LeboncoinService.close_browser()

    @staticmethod
    async def run_desktop_leboncoin_publish_job(
        article_id: int,
        user_id: int,
        token: str,
        remote_base: str,
    ) -> None:
        """Publie un article sur Leboncoin et diffuse sa progression dans le journal de l’article."""

        async def on_progress(ev: dict[str, Any]) -> None:
            await progress_hub.emit(article_id, ev)

        try:
            result = await DesktopLeboncoinRunnerService._publish_article(
                article_id, user_id, token, remote_base, progress=on_progress
            )
            await progress_hub.finish(article_id, {"leboncoin": result})
        finally:
            progress_hub.cleanup_later(article_id)

    @staticmethod
    async def run_desktop_leboncoin_batch_job(
        job_id: str,
        user_id: int,
        article_ids: list[int],
        token: str,
        remote_base: str,
    ) -> None:
        """Publie plusieurs articles sur Leboncoin l’un après l’autre (un Chrome chacun) et écrit le résultat de chacun dans le journal du lot."""
        n = len(article_ids)
        summary: list[dict[str, Any]] = []
        position_label = ""

        async def forward_progress(ev: dict[str, Any]) -> None:
            """Relaie une étape de la publication en cours dans le journal du lot, précédée de la position de l’article."""
            if ev.get("type") == "log" and isinstance(ev.get("message"), str):
                ev = {**ev, "message": f"{position_label} — {ev['message']}"}
            await batch_hub.emit_event(job_id, ev)

        try:
            await batch_hub.emit_event(
                job_id,
                {"type": "log", "step": "prep", "message": f"Publication Leboncoin — {n} article(s)…", "form_step": "prep"},
            )
            for i, article_id in enumerate(article_ids):
                position_label = f"{i + 1}/{n}"
                await batch_hub.emit_event(
                    job_id,
                    {"type": "progress", "current": i + 1, "total": n, "article_id": article_id},
                )
                result = await DesktopLeboncoinRunnerService._publish_article(
                    article_id, user_id, token, remote_base, progress=forward_progress
                )
                summary.append({"article_id": article_id, **result})
                if result.get("published"):
                    outcome_event = {
                        "type": "log",
                        "step": "published",
                        "message": f"{position_label} — Annonce publiée sur Leboncoin.",
                        "form_step": "published",
                    }
                else:
                    outcome_event = {
                        "type": "log",
                        "step": "error",
                        "message": f"{position_label} — Échec : {result.get('detail') or 'publication non confirmée'}.",
                        "form_step": "failed",
                    }
                await batch_hub.emit_event(job_id, outcome_event)
            published_count = sum(1 for outcome in summary if outcome.get("published"))
            has_published_all = published_count == n
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "done" if has_published_all else "error",
                    "message": f"Publication terminée : {published_count}/{n} annonce(s) publiée(s) sur Leboncoin.",
                    "form_step": "done" if has_published_all else "failed",
                },
            )
            await batch_hub.finish_job(
                job_id,
                {
                    "summary": summary,
                    "leboncoin": {"published": has_published_all, "count": n, "published_count": published_count},
                },
            )
        except Exception:
            logger.exception("Leboncoin batch crashed job_id=%s", job_id)
            await batch_hub.finish_job(
                job_id,
                {"summary": summary, "leboncoin": {"published": False, "detail": "internal_error"}},
            )
        finally:
            batch_hub.clear_active_job_for_user(user_id)
            batch_hub.cleanup_later(job_id)
