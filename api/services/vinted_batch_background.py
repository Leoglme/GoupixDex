"""Tâche en arrière-plan : lot Vinted (plusieurs articles, une session navigateur)."""

from __future__ import annotations

import logging

from core.database import SessionLocal
from models.article import Article
from models.user import User
from services import article_service
from services import vinted_batch_progress as batch_hub
from services.vinted_batch_orchestrator import run_vinted_batch_job

logger = logging.getLogger(__name__)


async def run_vinted_batch_publish_job(job_id: str, user_id: int, article_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            logger.error("Vinted batch: user missing job_id=%s", job_id)
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "error",
                    "message": "Utilisateur introuvable — abandon du lot.",
                    "form_step": "failed",
                },
            )
            await batch_hub.finish_job(
                job_id,
                {"summary": [], "vinted": {"published": False, "detail": "user_missing"}},
            )
            batch_hub.clear_active_job_for_user(user_id)
            batch_hub.cleanup_later(job_id)
            return

        items: list[tuple[Article, list[str]]] = []
        for aid in article_ids:
            article = article_service.get_article(db, aid, user_id)
            if article is None:
                logger.warning("Vinted batch: skip missing article_id=%s", aid)
                continue
            urls = [img.image_url for img in article.images]
            if not urls:
                logger.warning("Vinted batch: skip article without images id=%s", aid)
                continue
            items.append((article, urls))

        if not items:
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "log",
                    "step": "error",
                    "message": "Aucun article valide (introuvable ou sans image).",
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

        await run_vinted_batch_job(job_id, user_id, items, user)
    except Exception as exc:
        logger.exception("Vinted batch job crashed job_id=%s", job_id)
        await batch_hub.emit_event(
            job_id,
            {
                "type": "log",
                "step": "error",
                "message": f"Erreur interne du lot : {exc}",
                "form_step": "failed",
            },
        )
        await batch_hub.finish_job(
            job_id,
            {"summary": [], "vinted": {"published": False, "detail": "internal_error"}},
        )
        batch_hub.clear_active_job_for_user(user_id)
        batch_hub.cleanup_later(job_id)
    finally:
        db.close()
