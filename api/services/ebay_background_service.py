"""Background task: eBay publish for one article (or sequential batch)."""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from models.user import User
from services import article_service
from services.ebay_publish_service import publish_article_to_ebay
from services.user_settings_service import get_or_create_user_settings

logger = logging.getLogger(__name__)


class EbayBackgroundService:
    @staticmethod
    async def run_ebay_publish_job(article_id: int, user_id: int) -> None:
        db = SessionLocal()
        try:
            article = article_service.get_article(db, article_id, user_id)
            user = db.get(User, user_id)
            if article is None or user is None:
                logger.warning("eBay job missing article or user id=%s user=%s", article_id, user_id)
                return
            ms = get_or_create_user_settings(db, user_id)
            image_urls = [img.image_url for img in article.images]
            result = await publish_article_to_ebay(db, article, user, ms, image_urls)
            if result.get("ok") and result.get("listing_id"):
                article_service.mark_article_published_on_ebay(
                    article_id,
                    user_id,
                    str(result["listing_id"]),
                )
        except Exception:
            logger.exception("eBay background job failed article_id=%s", article_id)
        finally:
            db.close()

    @staticmethod
    async def run_ebay_batch_sequential(user_id: int, article_ids: list[int]) -> None:
        """Publish many articles one after another (courtesy delay between calls)."""
        for aid in article_ids:
            await EbayBackgroundService.run_ebay_publish_job(aid, user_id)
            await asyncio.sleep(1.5)
