"""Item listing payload shape (matches ``items.json`` entries)."""

from typing import NotRequired, TypedDict

from app_types.vinted import VintedConditions


class ItemPayload(TypedDict):
    """
    Describes one Vinted listing loaded from ``items.json``.

    Attributes:
        title: Listing title shown on Vinted.
        description: Optional long description (see VintedService for how it is applied).
        price: Price as a number (currency follows your Vinted account).
        condition: One of the French Vinted condition labels.
        images: Filenames under the project ``images/`` folder.
    """

    title: str
    description: NotRequired[str]
    price: float | int
    condition: VintedConditions
    images: list[str]
