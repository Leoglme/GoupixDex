"""Pre-compute Cardmarket / TCGPlayer reference prices on articles (option B)."""

from __future__ import annotations

import datetime as dt
import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from models.article import Article
from services.collection_article_sync_service import is_unresolved, linked_collection_card
from services.pricing_service import fetch_card_prices

logger = logging.getLogger(__name__)

_ARTICLE_REPRICE_SLEEP_SEC = 0.12


def _tcgplayer_eur_from_usd(usd: float | None) -> float | None:
    if usd is None or float(usd) <= 0:
        return None
    return round(float(usd) * get_settings().usd_to_eur, 2)


def apply_pricing_snapshot_to_article(article: Article, snapshot: dict[str, Any]) -> None:
    """Write ``fetch_card_prices`` result onto the article row (in-memory; caller commits)."""
    cm = snapshot.get("cardmarket_eur")
    tcg_eur = _tcgplayer_eur_from_usd(snapshot.get("tcgplayer_usd"))
    raw_id = snapshot.get("cardmarket_id_product")
    article.cardmarket_id_product = int(raw_id) if isinstance(raw_id, int) else None
    article.market_cardmarket_eur = Decimal(str(cm)) if cm is not None else None
    article.market_tcgplayer_eur = Decimal(str(tcg_eur)) if tcg_eur is not None else None
    article.market_priced_at = dt.datetime.now(dt.UTC)


def clear_article_market_reference(article: Article) -> None:
    article.cardmarket_id_product = None
    article.market_cardmarket_eur = None
    article.market_tcgplayer_eur = None
    article.market_priced_at = None


def _printed_card_number(value: str | None) -> str:
    """Printed number without denominator nor leading zeros (``"071/063"`` gives ``"71"``), to compare an article with its card."""
    head = (value or "").split("/", 1)[0].strip().lower()
    return head.lstrip("0") or head


def fetch_article_card_prices(db: Session, article: Article) -> dict[str, Any]:
    """
    Reference prices of an article's card, identified by its linked collection card when that card is resolved and still has the article's number.

    Args:
        db: Database session.
        article: Article to price.

    Returns:
        The ``fetch_card_prices`` result.
    """
    linked_card = linked_collection_card(db, article)
    if (
        linked_card is not None
        and not is_unresolved(linked_card)
        and _printed_card_number(linked_card.card_number) == _printed_card_number(article.card_number)
    ):
        return fetch_card_prices(
            article.set_code,
            article.card_number,
            article.pokemon_name,
            tcgdex_card_id=linked_card.tcgdex_card_id,
            language=linked_card.language,
        )
    return fetch_card_prices(article.set_code, article.card_number, article.pokemon_name)


def refresh_article_market_reference(article: Article) -> None:
    """Resolve set + number and store reference prices (TCGdex + local guide)."""
    set_code = (article.set_code or "").strip()
    card_number = (article.card_number or "").strip()
    if not set_code or not card_number:
        clear_article_market_reference(article)
        return
    snapshot = fetch_card_prices(set_code, card_number, article.pokemon_name)
    apply_pricing_snapshot_to_article(article, snapshot)


def revalue_all_articles(db: Session) -> dict[str, int]:
    """Re-price every article that has set + number (called after guide refresh)."""
    repriced = 0
    cleared = 0
    rows = db.query(Article).all()
    for row in rows:
        if not (row.set_code or "").strip() or not (row.card_number or "").strip():
            if row.market_priced_at is not None:
                clear_article_market_reference(row)
                cleared += 1
            continue
        try:
            apply_pricing_snapshot_to_article(row, fetch_article_card_prices(db, row))
            repriced += 1
        except Exception as exc:
            logger.warning("Article %s market reprice failed: %s", row.id, exc)
        time.sleep(_ARTICLE_REPRICE_SLEEP_SEC)
    return {"articles_repriced": repriced, "articles_market_cleared": cleared}
