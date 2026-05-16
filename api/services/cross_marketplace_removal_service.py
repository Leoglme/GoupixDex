"""Tâches asynchrones : retirer l’annonce eBay après une vente déclarée sur Vinted."""

from __future__ import annotations

import logging

from core.database import SessionLocal
from models.user import User
from services import article_service
from services.ebay_listing_delete_service import clear_ebay_publication_fields, delete_ebay_listing_for_article

logger = logging.getLogger(__name__)


async def run_background_ebay_removal_after_vinted_sale(article_id: int, user_id: int) -> None:
    """Appelé depuis ``BackgroundTasks`` après ``PATCH …/sold`` (source Vinted)."""
    db = SessionLocal()
    try:
        article = article_service.get_article(db, article_id, user_id)
        user = db.get(User, user_id)
        if article is None or user is None:
            return
        if not article.published_on_ebay:
            article.cross_ebay_removal_failed = False
            article.cross_ebay_removal_error = None
            db.add(article)
            db.commit()
            return

        ok, err = await delete_ebay_listing_for_article(db, article, user)
        if ok:
            clear_ebay_publication_fields(article)
            article.cross_ebay_removal_failed = False
            article.cross_ebay_removal_error = None
        else:
            article.cross_ebay_removal_failed = True
            article.cross_ebay_removal_error = (err or "Erreur inconnue")[:500]
        db.add(article)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("cross eBay removal task article_id=%s", article_id)
        try:
            article = article_service.get_article(db, article_id, user_id)
            if article is not None:
                article.cross_ebay_removal_failed = True
                article.cross_ebay_removal_error = str(exc)[:500]
                db.add(article)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()
