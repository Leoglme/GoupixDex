"""Background task: eBay publish for one article (or sequential batch)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.database import SessionLocal
from models.user import User
from services import article_service
from services.ebay_publish_service import publish_article_to_ebay
from services.user_settings_service import get_or_create_user_settings
from services.vinted_progress_session_service import VintedProgressSessionService as progress_hub

logger = logging.getLogger(__name__)


def _ebay_sse_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "published": bool(result.get("ok")),
        "listing_id": result.get("listing_id"),
        "detail": result.get("detail"),
    }


class EbayBackgroundService:
    @staticmethod
    async def run_ebay_publish_job(
        article_id: int,
        user_id: int,
        *,
        finish_session: bool = True,
    ) -> dict[str, Any]:
        progress_hub.register(article_id)
        db = SessionLocal()
        result: dict[str, Any] = {"ok": False, "detail": "unknown"}
        try:
            article = article_service.get_article(db, article_id, user_id)
            user = db.get(User, user_id)
            if article is None or user is None:
                logger.warning("eBay job missing article or user id=%s user=%s", article_id, user_id)
                result = {"ok": False, "detail": "article_or_user_missing"}
                if finish_session:
                    await progress_hub.finish(article_id, {"ebay": _ebay_sse_payload(result)})
                return result

            ms = get_or_create_user_settings(db, user_id)
            image_urls = [img.image_url for img in article.images]

            async def on_progress(ev: dict[str, Any]) -> None:
                await progress_hub.emit(article_id, ev)

            result = await publish_article_to_ebay(
                db,
                article,
                user,
                ms,
                image_urls,
                progress=on_progress,
            )
            if result.get("ok") and result.get("listing_id"):
                article_service.mark_article_published_on_ebay(
                    article_id,
                    user_id,
                    str(result["listing_id"]),
                )
            if finish_session:
                await progress_hub.finish(article_id, {"ebay": _ebay_sse_payload(result)})
        except Exception as exc:
            logger.exception("eBay background job failed article_id=%s", article_id)
            result = {"ok": False, "detail": str(exc)}
            if finish_session:
                await progress_hub.finish(article_id, {"ebay": _ebay_sse_payload(result)})
        finally:
            db.close()
            if finish_session:
                progress_hub.cleanup_later(article_id)
        return result

    @staticmethod
    async def run_ebay_batch_sequential(user_id: int, article_ids: list[int]) -> None:
        """Publish many articles one after another (courtesy delay between calls)."""
        for aid in article_ids:
            await EbayBackgroundService.run_ebay_publish_job(aid, user_id)
            await asyncio.sleep(1.5)
