"""Plain types for Cardmarket product scrape + seller aggregation (no nodriver)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CardmarketOffer:
    seller_name: str
    price_eur: float
    quantity: int
    seller_location: str | None = None
    shipping_time_days: int | None = None
    comments: str | None = None
    article_id: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "seller_name": self.seller_name,
            "price_eur": self.price_eur,
            "quantity": self.quantity,
            "seller_location": self.seller_location,
            "shipping_time_days": self.shipping_time_days,
            "comments": self.comments,
            "article_id": self.article_id,
        }


@dataclass
class CardmarketCardResult:
    code: str
    product_name: str | None
    product_url: str | None
    offers: list[CardmarketOffer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        cheapest = min((o.price_eur for o in self.offers), default=None)
        return {
            "code": self.code,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "warnings": list(self.warnings),
            "offers": [o.to_json_dict() for o in self.offers],
            "cheapest_eur": cheapest,
        }
