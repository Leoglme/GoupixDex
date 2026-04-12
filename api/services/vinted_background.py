"""Tâche asynchrone : publication Vinted après création d'article (logs → SSE)."""

from __future__ import annotations

import logging

from core.database import SessionLocal
from models.user import User
from services import article_service
from services import vinted_progress as vp
from services.vinted_publish_service import publish_article_to_vinted

logger = logging.getLogger(__name__)


async def run_vinted_publish_job(article_id: int, user_id: int, image_sources: list[str]) -> None:
    db = SessionLocal()
    try:
        article = article_service.get_article(db, article_id, user_id)
        user = db.get(User, user_id)
        if article is None or user is None:
            await vp.finish(
                article_id,
                {"published": False, "detail": "article_or_user_missing"},
            )
            return

        async def on_progress(ev: dict) -> None:
            await vp.emit(article_id, ev)

        result = await publish_article_to_vinted(
            article,
            user,
            image_sources,
            progress=on_progress,
        )
        if bool(result.get("published")):
            article_service.mark_article_published_on_vinted(article_id, user_id)
        await vp.finish(article_id, result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vinted background job failed article_id=%s", article_id)
        await vp.finish(article_id, {"published": False, "detail": str(exc)})
    finally:
        db.close()
        vp.cleanup_later(article_id)
