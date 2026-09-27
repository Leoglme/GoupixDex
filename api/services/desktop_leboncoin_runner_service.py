"""Leboncoin publish on the local machine: metadata from remote API, nodriver here."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.desktop_api_confirmation_service import post_confirmation_to_api
from services.desktop_stubs_service import DesktopStubsService
from services.leboncoin_publish_service import ProgressFn, publish_article_to_leboncoin
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

            result = await publish_article_to_leboncoin(
                article,
                image_urls,
                postal_code=postal,
                sender_line1=line1,
                sender_city=city,
                progress=progress,
            )
            if bool(result.get("published")):
                payload: dict[str, Any] = {}
                if result.get("listing_id"):
                    payload["listing_id"] = result["listing_id"]
                try:
                    await post_confirmation_to_api(
                        f"{remote_base}/articles/{article_id}/confirm-leboncoin-publish",
                        {**hdrs, "Content-Type": "application/json"},
                        payload,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("confirm-leboncoin-publish failed article_id=%s: %s", article_id, exc)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Desktop Leboncoin publish failed article_id=%s", article_id)
            return {"published": False, "detail": str(exc)}

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
