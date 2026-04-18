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
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(
                        f"{remote_base}/articles/{article_id}/confirm-vinted-publish",
                        headers=hdrs,
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
