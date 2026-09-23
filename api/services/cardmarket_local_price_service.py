"""
Local Cardmarket pricing for GoupixDex, backed by the ``cardmarket-api`` package.

Two responsibilities:

1. Own the process-wide :class:`cardmarket_api.CardmarketPriceApi` singleton
   (disk-cached price guide, RAM lookups — no network on request paths).
2. Harvest the Cardmarket ``idProduct`` from TCGdex card payloads
   (``pricing.cardmarket.idProduct``): TCGdex maintains the card ↔ product
   mapping in its open database, so GoupixDex never has to build it itself.

Reference picking mirrors :class:`cardmarket_api.CardPriceService`
(``avg30 → avg7 → avg → avg1 → trend``, never ``low``) so a price computed from
a TCGdex pricing block matches one computed from the local guide.

On top of that ordering, :func:`resolve_market_price_eur` applies an anti-pollution
rule: some Cardmarket products (Japanese promos…) carry a barely-traded "normal"
bucket whose short- and long-term aggregates each collapse to a single spiked value,
sitting next to a liquid reverse-holo bucket. There the ``*-holo`` columns are the
real market, so we use them instead of the inflated normal cote.
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

#: TTL cache: ``tcgdex_card_id`` → (fetched_at, cardmarket block | None, tcgplayer USD | None).
_pricing_block_lock = threading.Lock()
_pricing_block_cache: dict[str, tuple[float, dict[str, Any] | None, float | None]] = {}


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


def reference_usd_from_tcgplayer_block(block: dict[str, Any]) -> float | None:
    """
    Pick a reference USD price from a TCGdex ``pricing.tcgplayer`` object
    (``normal`` / ``holofoil`` / … sub-blocks with ``marketPrice`` or ``midPrice``).
    """
    best: float | None = None
    for key, val in block.items():
        if key in ("unit", "updated") or not isinstance(val, dict):
            continue
        picked: float | None = None
        for field in ("marketPrice", "midPrice", "lowPrice"):
            raw = val.get(field)
            if isinstance(raw, (int, float)) and float(raw) > 0:
                picked = float(raw)
                break
        if picked is None:
            continue
        best = picked if best is None else max(best, picked)
    return round(best, 2) if best is not None else None


def extract_tcgplayer_usd(card_payloads: list[dict[str, Any]]) -> float | None:
    """First usable TCGPlayer USD reference among locale payloads."""
    for payload in card_payloads:
        pricing = payload.get("pricing")
        if not isinstance(pricing, dict):
            continue
        tcg_block = pricing.get("tcgplayer")
        if not isinstance(tcg_block, dict):
            continue
        usd = reference_usd_from_tcgplayer_block(tcg_block)
        if usd is not None:
            return usd
    return None


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


def reverse_reference_eur_from_block(block: dict[str, Any]) -> float | None:
    """Reverse-holo reference (``*-holo`` columns) from a TCGdex pricing block."""
    return CardPriceService.pick_reverse_reference_eur_from_mapping(block)


def _normal_bucket_is_illiquid(
    trend: object,
    avg1: object,
    avg7: object,
    avg30: object,
) -> bool:
    """
    Vrai quand la cote « normale » d'un produit Cardmarket est trop peu échangée pour être fiable :
    ses agrégats court terme (``avg1``/``trend``) et long terme (``avg7``/``avg30``) se figent chacun
    sur une seule valeur. C'est la signature d'une promo dont le bucket normal est pollué (copies mal
    classées, gradées, autres langues) alors que la série reverse-holo, elle, reflète le vrai marché.
    """
    values = [v if isinstance(v, (int, float)) else None for v in (trend, avg1, avg7, avg30)]
    trend_v, avg1_v, avg7_v, avg30_v = values
    return (
        avg7_v is not None
        and avg7_v == avg30_v
        and avg1_v is not None
        and avg1_v == trend_v
        and avg7_v != avg1_v
    )


def _market_reference_eur(
    base_reference: float | None,
    reverse_reference: float | None,
    trend: object,
    avg1: object,
    avg7: object,
    avg30: object,
) -> float | None:
    """
    Cote de marché : la référence « normale », sauf quand ce bucket est illiquide (voir
    :func:`_normal_bucket_is_illiquid`) et qu'une cote reverse-holo existe — on prend alors cette
    dernière, plus représentative. Repli sur la reverse-holo si la normale est absente.
    """
    if (
        reverse_reference is not None
        and reverse_reference > 0
        and _normal_bucket_is_illiquid(trend, avg1, avg7, avg30)
    ):
        return round(float(reverse_reference), 2)
    if base_reference is not None:
        return round(float(base_reference), 2)
    if reverse_reference is not None:
        return round(float(reverse_reference), 2)
    return None


def resolve_market_price_eur(
    id_product: int | None,
    tcgdex_block: dict[str, Any] | None,
) -> float | None:
    """
    Reference EUR for a card: local price guide first, TCGdex block as fallback.

    Both views are built from the same Cardmarket daily file; the local guide
    simply wins because it is refreshed by our own nightly job. The reference
    leads with the 30-day average (see :data:`cardmarket_api.REFERENCE_FIELD_ORDER`)
    and, via :func:`_market_reference_eur`, ignores a polluted "normal" bucket in
    favour of the liquid reverse-holo one — so a JP promo reads a fair price.
    """
    if id_product is not None:
        local: CardmarketCardPrices | None = get_price_api().get_card_prices(id_product)
        if local is not None:
            reference = _market_reference_eur(
                local.reference_eur,
                local.reverse_reference_eur,
                local.trend,
                local.avg1,
                local.avg7,
                local.avg30,
            )
            if reference is not None:
                return reference
    if tcgdex_block is not None:
        reference = _market_reference_eur(
            reference_eur_from_block(tcgdex_block),
            reverse_reference_eur_from_block(tcgdex_block),
            tcgdex_block.get("trend"),
            tcgdex_block.get("avg1"),
            tcgdex_block.get("avg7"),
            tcgdex_block.get("avg30"),
        )
        if reference is not None:
            return reference
    return None


def resolve_sealed_market_price_eur(id_product: int | None) -> float | None:
    """
    Reference EUR for a **sealed** product: the Cardmarket ``trend`` (the "Price Trend" shown on the
    product page), falling back to the standard cote (``avg``) when ``trend`` is missing.

    Sealed products carry no ``avg30``/``avg7``/``avg1`` in the downloadable guide (unlike singles), so the
    card ordering would collapse to the all-time ``avg`` — laggy and inflated by launch prices. ``trend`` is
    Cardmarket's recomputed current price, so the value here matches what the user reads on the Cardmarket
    listing.
    """
    if id_product is None:
        return None
    local: CardmarketCardPrices | None = get_price_api().get_card_prices(id_product)
    if local is not None and isinstance(local.trend, (int, float)) and float(local.trend) > 0:
        return round(float(local.trend), 2)
    return resolve_market_price_eur(id_product, None)


def fetch_tcgdex_pricing_snapshot(
    tcgdex_card_id: str,
    physical_language: str | None = None,
    client: TcgdexClientService | None = None,
) -> tuple[dict[str, Any] | None, float | None]:
    """
    Cardmarket block + TCGPlayer USD from TCGdex (6 h TTL cache).

    Tries the physical language's locale first, then the other supported ones.
    """
    cid = tcgdex_card_id.strip()
    if not cid:
        return None, None

    now = time.time()
    with _pricing_block_lock:
        cached = _pricing_block_cache.get(cid)
        if cached is not None and now - cached[0] < _PRICING_BLOCK_TTL_SEC:
            return cached[1], cached[2]

    lang = (physical_language or "").strip().lower()
    locales = [lang] if lang in SUPPORTED_LOCALES else []
    locales += [loc for loc in sorted(SUPPORTED_LOCALES) if loc not in locales]

    tcgdex = client or TcgdexClientService()
    payloads: list[dict[str, Any]] = []
    for locale in locales:
        try:
            payloads.append(dict(tcgdex.get_card(locale, cid)))
        except (RuntimeError, ValueError):
            continue

    block = extract_cardmarket_block(payloads)
    tcg_usd = extract_tcgplayer_usd(payloads)

    with _pricing_block_lock:
        _pricing_block_cache[cid] = (now, block, tcg_usd)
    return block, tcg_usd


def fetch_pricing_block_for_card(
    tcgdex_card_id: str,
    physical_language: str | None = None,
    client: TcgdexClientService | None = None,
) -> dict[str, Any] | None:
    """TCGdex ``pricing.cardmarket`` block for a card id (cached)."""
    block, _ = fetch_tcgdex_pricing_snapshot(tcgdex_card_id, physical_language, client)
    return block


def fetch_tcgplayer_usd_for_card(
    tcgdex_card_id: str,
    physical_language: str | None = None,
    client: TcgdexClientService | None = None,
) -> float | None:
    """TCGPlayer reference USD from TCGdex ``pricing.tcgplayer`` (cached)."""
    _, tcg_usd = fetch_tcgdex_pricing_snapshot(tcgdex_card_id, physical_language, client)
    return tcg_usd
