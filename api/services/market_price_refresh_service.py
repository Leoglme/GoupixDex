"""
Nightly Cardmarket refresh: price guide download + full collection revaluation.

Runs inside the FastAPI process (started from ``main.py``'s lifespan):

- **Bootstrap** at startup when the local guide is missing or older than a day
  and a half, so a fresh install prices cards without waiting for the night.
- **Nightly loop** at ``settings.cardmarket_refresh_hour_local`` (Europe/Paris),
  after Cardmarket regenerated its files (~02:49): one conditional download,
  then every collection card is re-priced from the in-RAM guide — zero external
  API calls for already-mapped cards.

Cards still missing their ``cardmarket_id_product`` get a capped, throttled
TCGdex resolution pass.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from typing import Any
from zoneinfo import ZoneInfo

from cardmarket_api import CardmarketDataUnavailableError

from config import get_settings
from core.database import SessionLocal
from models.collection_card import CollectionCard
from services import collection_card_service
from services.cardmarket_local_price_service import (
    fetch_pricing_block_for_card,
    get_price_api,
    refresh_price_guide,
    resolve_market_price_eur,
)

logger = logging.getLogger(__name__)

_PARIS_TZ = ZoneInfo("Europe/Paris")
#: Max TCGdex resolution attempts per run (unmapped cards only) — bounds duration.
_MAX_TCGDEX_RESOLUTIONS_PER_RUN = 500
_TCGDEX_RESOLUTION_SLEEP_SEC = 0.15
#: Bootstrap triggers when the cached guide is older than this (or absent).
_BOOTSTRAP_MAX_AGE_HOURS = 36.0


def refresh_market_prices() -> dict[str, Any]:
    """
    Refresh the price guide then revalue every collection card. Synchronous —
    call from a worker thread or a manual endpoint, never an async event loop.
    """
    report = refresh_price_guide(force=True)
    revaluation = _revalue_all_collection_cards()
    result = {
        "guide_refreshed": report.refreshed,
        "guide_source": report.source,
        "guide_row_count": report.row_count,
        "guide_created_at": report.created_at,
        **revaluation,
    }
    logger.info("Cardmarket market refresh done: %s", result)
    return result


def _revalue_all_collection_cards() -> dict[str, int]:
    """Re-price every card from the local guide; resolve missing mappings (capped)."""
    db = SessionLocal()
    repriced = 0
    newly_mapped = 0
    unpriced = 0
    resolution_attempts = 0
    try:
        rows = db.query(CollectionCard).all()
        for row in rows:
            id_product = row.cardmarket_id_product
            block: dict[str, Any] | None = None
            if id_product is None and resolution_attempts < _MAX_TCGDEX_RESOLUTIONS_PER_RUN:
                resolution_attempts += 1
                block = fetch_pricing_block_for_card(row.tcgdex_card_id, row.language)
                raw_id = block.get("idProduct") if block else None
                if isinstance(raw_id, int):
                    id_product = raw_id
                    newly_mapped += 1
                time.sleep(_TCGDEX_RESOLUTION_SLEEP_SEC)

            price = resolve_market_price_eur(id_product, block)
            if price is None:
                unpriced += 1
                continue
            collection_card_service.apply_market_price(
                row,
                cardmarket_id_product=id_product,
                market_price_eur=price,
            )
            repriced += 1
        db.commit()
    finally:
        db.close()
    return {
        "cards_repriced": repriced,
        "cards_newly_mapped": newly_mapped,
        "cards_unpriced": unpriced,
    }


async def bootstrap_market_prices_async() -> None:
    """Startup task: make the local guide usable without waiting for the night."""
    api = get_price_api()
    age = api.guide_age_hours()
    if api.row_count > 0 and age is not None and age < _BOOTSTRAP_MAX_AGE_HOURS:
        logger.info(
            "Cardmarket guide ready (%s rows, %.1f h old) — no bootstrap needed.",
            api.row_count,
            age,
        )
        return
    try:
        await asyncio.to_thread(refresh_market_prices)
    except CardmarketDataUnavailableError as exc:
        logger.warning("Cardmarket bootstrap refresh failed (will retry tonight): %s", exc)
    except Exception:
        logger.exception("Cardmarket bootstrap refresh crashed")


async def nightly_refresh_loop_async() -> None:
    """Endless loop: run the refresh every night at the configured local hour."""
    settings = get_settings()
    while True:
        await asyncio.sleep(_seconds_until_next_run(settings.cardmarket_refresh_hour_local))
        try:
            await asyncio.to_thread(refresh_market_prices)
        except CardmarketDataUnavailableError as exc:
            logger.warning("Nightly Cardmarket refresh failed: %s", exc)
        except Exception:
            logger.exception("Nightly Cardmarket refresh crashed")


def _seconds_until_next_run(hour_local: int) -> float:
    """Seconds until the next occurrence of ``hour_local`` in Europe/Paris."""
    now = dt.datetime.now(_PARIS_TZ)
    next_run = now.replace(hour=hour_local, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += dt.timedelta(days=1)
    return (next_run - now).total_seconds()
