"""
Local Cardmarket pricing for GoupixDex, backed by the ``cardmarket-api`` package.

Two responsibilities:

1. Own the process-wide :class:`cardmarket_api.CardmarketPriceApi` singleton
   (disk-cached price guide, RAM lookups — no network on request paths).
2. Harvest the Cardmarket ``idProduct`` from TCGdex card payloads
   (``pricing.cardmarket.idProduct``): TCGdex maintains the card ↔ product
   mapping in its open database, so GoupixDex never has to build it itself.

Reference picking mirrors :class:`cardmarket_api.CardPriceService`
(``trend → avg7 → avg30 → avg1 → avg``, never ``low``) so a price computed from
a TCGdex pricing block matches one computed from the local guide.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from cardmarket_api import (
    CardmarketCardPrices,
    CardmarketPriceApi,
    CardPriceService,
    PriceGuideRefreshReport,
)

from config import get_settings
from services.tcgdex_client_service import SUPPORTED_LOCALES, TcgdexClientService

logger = logging.getLogger(__name__)

_PRICING_BLOCK_TTL_SEC = 6 * 3600.0

_api_lock = threading.Lock()
_price_api: CardmarketPriceApi | None = None

#: TTL cache of TCGdex pricing blocks: ``tcgdex_card_id`` → (fetched_at, block | None).
_pricing_block_lock = threading.Lock()
_pricing_block_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


def get_price_api() -> CardmarketPriceApi:
    """Process-wide facade over the disk-cached Cardmarket price guide."""
    global _price_api
    with _api_lock:
        if _price_api is None:
            settings = get_settings()
            cache_dir = Path(settings.cardmarket_cache_dir)
            if not cache_dir.is_absolute():
                cache_dir = Path(__file__).resolve().parent.parent / cache_dir
            cache_dir.mkdir(parents=True, exist_ok=True)
            _price_api = CardmarketPriceApi(cache_dir)
        return _price_api


def refresh_price_guide(*, force: bool = False) -> PriceGuideRefreshReport:
    """Refresh the guide from Cardmarket's S3 bucket (network — never call in a request path)."""
    return get_price_api().refresh(force=force)


def extract_cardmarket_block(card_payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    """First ``pricing.cardmarket`` block carrying an ``idProduct`` among locale payloads."""
    for payload in card_payloads:
        pricing = payload.get("pricing")
        if not isinstance(pricing, dict):
            continue
        block = pricing.get("cardmarket")
        if isinstance(block, dict) and isinstance(block.get("idProduct"), int):
            return block
    return None


def reference_eur_from_block(block: dict[str, Any]) -> float | None:
    """Sales-based reference from a TCGdex pricing block (same picking order as the local guide)."""
    return CardPriceService.pick_reference_eur_from_mapping(block)


def resolve_market_price_eur(
    id_product: int | None,
    tcgdex_block: dict[str, Any] | None,
) -> float | None:
    """
    Reference EUR for a card: local price guide first, TCGdex block as fallback.

    Both views are built from the same Cardmarket daily file; the local guide
    simply wins because it is refreshed by our own nightly job.
    """
    if id_product is not None:
        local: CardmarketCardPrices | None = get_price_api().get_card_prices(id_product)
        if local is not None and local.reference_eur is not None:
            return round(local.reference_eur, 2)
    if tcgdex_block is not None:
        block_reference = reference_eur_from_block(tcgdex_block)
        if block_reference is not None:
            return round(block_reference, 2)
    return None


def fetch_pricing_block_for_card(
    tcgdex_card_id: str,
    physical_language: str | None = None,
    client: TcgdexClientService | None = None,
) -> dict[str, Any] | None:
    """
    TCGdex ``pricing.cardmarket`` block for a card id, with a 6 h TTL cache.

    Tries the physical language's locale first, then the other supported ones
    (Japan-only prints have no EN payload). Returns ``None`` when the card has
    no individual Cardmarket listing.
    """
    cid = tcgdex_card_id.strip()
    if not cid:
        return None

    now = time.time()
    with _pricing_block_lock:
        cached = _pricing_block_cache.get(cid)
        if cached is not None and now - cached[0] < _PRICING_BLOCK_TTL_SEC:
            return cached[1]

    lang = (physical_language or "").strip().lower()
    locales = [lang] if lang in SUPPORTED_LOCALES else []
    locales += [loc for loc in sorted(SUPPORTED_LOCALES) if loc not in locales]

    tcgdex = client or TcgdexClientService()
    block: dict[str, Any] | None = None
    for locale in locales:
        try:
            payload = dict(tcgdex.get_card(locale, cid))
        except (RuntimeError, ValueError):
            continue
        block = extract_cardmarket_block([payload])
        if block is not None:
            break

    with _pricing_block_lock:
        _pricing_block_cache[cid] = (now, block)
    return block
