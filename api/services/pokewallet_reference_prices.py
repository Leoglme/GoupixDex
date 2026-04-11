"""Pick reference EUR/USD prices from PokéWallet Cardmarket / TCGPlayer rows."""

from app_types.pokewallet import PokeWalletCardmarketPriceRow, PokeWalletTcgPlayerPriceRow


def pick_cardmarket_reference_eur(
    rows: list[PokeWalletCardmarketPriceRow],
) -> float | None:
    """
    Pick a single reference EUR price from Cardmarket rows for display or comparison.
    Prefers ``variant_type == "normal"``, then the first positive value among
    avg1 → avg7 → avg30 → trend → avg → low.

    Args:
        rows: Price rows from a card's Cardmarket block (e.g. ``card["cardmarket"]["prices"]``).

    Returns:
        First suitable price in EUR, or ``None`` when none qualify.
    """
    ordered = sorted(rows, key=lambda r: (0 if r.get("variant_type") == "normal" else 1))
    for row in ordered:
        candidates: list[float | None] = [
            _float_or_none(row.get("avg1")),
            _float_or_none(row.get("avg7")),
            _float_or_none(row.get("avg30")),
            _float_or_none(row.get("trend")),
            _float_or_none(row.get("avg")),
            _float_or_none(row.get("low")),
        ]
        for c in candidates:
            if c is not None and c > 0:
                return c
    return None


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def pick_tcgplayer_reference_usd(rows: list[PokeWalletTcgPlayerPriceRow]) -> float | None:
    """
    Pick a single reference USD price from TCGPlayer rows.
    Uses the first row with positive ``mid_price``, otherwise ``market_price``.

    Args:
        rows: Price rows from a TCGPlayer block.

    Returns:
        Mid or market price in USD, or ``None`` when none qualify.
    """
    for row in rows:
        mid = float(row["mid_price"])
        if mid > 0:
            return mid
        market = float(row["market_price"])
        if market > 0:
            return market
    return None
