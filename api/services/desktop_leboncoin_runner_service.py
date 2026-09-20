"""Leboncoin publish on the local machine: metadata from remote API, nodriver here."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.desktop_stubs_service import DesktopStubsService
from services.leboncoin_publish_service import publish_article_to_leboncoin
from services.vinted_progress_session_service import VintedProgressSessionService as progress_hub

logger = logging.getLogger(__name__)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


class DesktopLeboncoinRunnerService:
    @staticmethod
    async def run_desktop_leboncoin_publish_job(
        article_id: int,
        user_id: int,
        token: str,
        remote_base: str,
    ) -> None:
        hdrs = _headers(token)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                ar = await client.get(f"{remote_base}/articles/{article_id}", headers=hdrs)
                ar.raise_for_status()
                article_d = ar.json()
                if article_d.get("user_id") != user_id:
                    await progress_hub.finish(article_id, {"leboncoin": {"published": False, "detail": "forbidden"}})
                    return
                sr = await client.get(f"{remote_base}/settings", headers=hdrs)
                sr.raise_for_status()
                settings_d = sr.json()
                postal = (settings_d.get("sender_postal_code") or "").strip()

            article = DesktopStubsService.article_from_api_dict(article_d)
            image_urls = [im["image_url"] for im in article_d.get("images") or []]

            async def on_progress(ev: dict[str, Any]) -> None:
                await progress_hub.emit(article_id, ev)

            result = await publish_article_to_leboncoin(
                article,
                image_urls,
                postal_code=postal,
                progress=on_progress,
            )
            if bool(result.get("published")):
                payload: dict[str, Any] = {}
                if result.get("listing_id"):
                    payload["listing_id"] = result["listing_id"]
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(
                        f"{remote_base}/articles/{article_id}/confirm-leboncoin-publish",
                        headers={**hdrs, "Content-Type": "application/json"},
                        json=payload,
                    )
                    try:
                        r.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.warning("confirm-leboncoin-publish failed article_id=%s: %s", article_id, exc)
            await progress_hub.finish(article_id, {"leboncoin": result})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Desktop Leboncoin publish failed article_id=%s", article_id)
            await progress_hub.finish(article_id, {"leboncoin": {"published": False, "detail": str(exc)}})
        finally:
            progress_hub.cleanup_later(article_id)
