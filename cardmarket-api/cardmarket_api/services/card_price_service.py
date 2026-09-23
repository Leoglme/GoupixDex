"""Reference-price picking rules over a :class:`PriceGuideRow`."""

from __future__ import annotations

from collections.abc import Mapping

from cardmarket_api.types import CardmarketCardPrices, PriceGuideRow

#: Sales-based fields tried in order for the reference price. ``avg30`` (30-day
#: average) leads on purpose: it is the most stable figure, so a low-liquidity
#: promo whose ``trend`` spiked on a single sale (frequent on Japanese cards)
#: still reads a fair market price. ``trend`` is the last resort, only used when
#: every average is missing. ``low`` is deliberately excluded: it is the single
#: cheapest listing of the product, any language (Korean copies on Japanese
#: sets) and any condition.
REFERENCE_FIELD_ORDER: tuple[str, ...] = ("avg30", "avg7", "avg", "avg1", "trend")


class CardPriceService:
    """Builds consumer-facing price views from raw price guide rows."""

    @staticmethod
    def pick_reference_eur(row: PriceGuideRow) -> float | None:
        """First positive sales-based aggregate (``avg30 → avg7 → avg → avg1 → trend``)."""
        for field in REFERENCE_FIELD_ORDER:
            value = getattr(row, field)
            if isinstance(value, float) and value > 0:
                return value
        return None

    @staticmethod
    def pick_reference_eur_from_mapping(values: Mapping[str, object]) -> float | None:
        """Same picking order over a plain mapping (e.g. a TCGdex ``pricing.cardmarket`` block).

        A ``pricing.cardmarket`` block carries the same aggregate keys as a guide
        row, so a price computed from a TCGdex block matches one from the guide.
        """
        for field in REFERENCE_FIELD_ORDER:
            value = values.get(field)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None

    @staticmethod
    def pick_reverse_reference_eur(row: PriceGuideRow) -> float | None:
        """Same picking order on the ``*-holo`` columns (reverse-holo variant)."""
        for field in REFERENCE_FIELD_ORDER:
            value = getattr(row, f"{field}_holo")
            if isinstance(value, float) and value > 0:
                return value
        return None

    @staticmethod
    def pick_reverse_reference_eur_from_mapping(values: Mapping[str, object]) -> float | None:
        """Same picking order on the ``*-holo`` keys of a mapping (e.g. a TCGdex block)."""
        for field in REFERENCE_FIELD_ORDER:
            value = values.get(f"{field}-holo")
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None

    @classmethod
    def build_card_prices(
        cls,
        row: PriceGuideRow,
        guide_created_at: str | None,
    ) -> CardmarketCardPrices:
        """Assemble the full view for one product."""
        return CardmarketCardPrices(
            id_product=row.id_product,
            reference_eur=cls.pick_reference_eur(row),
            reverse_reference_eur=cls.pick_reverse_reference_eur(row),
            trend=row.trend,
            avg1=row.avg1,
            avg7=row.avg7,
            avg30=row.avg30,
            avg=row.avg,
            low=row.low,
            guide_created_at=guide_created_at,
        )
