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
            refresh_article_market_reference(row)
            repriced += 1
        except Exception as exc:
            logger.warning("Article %s market reprice failed: %s", row.id, exc)
        time.sleep(_ARTICLE_REPRICE_SLEEP_SEC)
    return {"articles_repriced": repriced, "articles_market_cleared": cleared}
