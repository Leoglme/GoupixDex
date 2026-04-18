"""Background task: Vinted publish after article creation (logs → SSE)."""

from __future__ import annotations

import logging
from typing import Any

from core.database import SessionLocal
from models.user import User
from services import article_service
from services.vinted_progress_session_service import VintedProgressSessionService as vp
from services.vinted_publish_service import publish_article_to_vinted

logger = logging.getLogger(__name__)


class VintedBackgroundService:
    """Vinted publish as a background task (API server)."""

    @staticmethod
    async def run_vinted_publish_job(
        article_id: int,
        user_id: int,
        image_sources: list[str],
        *,
        finish_session: bool = True,
    ) -> dict[str, Any]:
        db = SessionLocal()
        result: dict[str, Any] = {"published": False, "detail": "unknown"}
        try:
            article = article_service.get_article(db, article_id, user_id)
            user = db.get(User, user_id)
            if article is None or user is None:
                result = {"published": False, "detail": "article_or_user_missing"}
                if finish_session:
                    await vp.finish(article_id, {"vinted": result})
                return result

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
            if finish_session:
                await vp.finish(article_id, {"vinted": result})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vinted background job failed article_id=%s", article_id)
            result = {"published": False, "detail": str(exc)}
            if finish_session:
                await vp.finish(article_id, {"vinted": result})
        finally:
            db.close()
            if finish_session:
                vp.cleanup_later(article_id)
        return result
