"""Vinted-related types (condition labels, package size, listing removal outcome)."""

from typing import Literal, TypedDict

VintedConditions = Literal[
    "Neuf avec étiquette",
    "Neuf sans étiquette",
    "Très bon état",
    "Bon état",
    "Satisfaisant",
]

VintedPackageSize = Literal["small", "medium", "large"]

VINTED_CONDITIONS: tuple[str, ...] = (
    "Neuf avec étiquette",
    "Neuf sans étiquette",
    "Très bon état",
    "Bon état",
    "Satisfaisant",
)


class VintedListingRemovalOutcome(TypedDict):
    """Résultat réel d’un retrait d’annonce Vinted : ``delisted`` n’est vrai que si Vinted ne liste plus l’annonce."""

    article_id: int
    delisted: bool
    vinted_id: int | None
    detail: str | None
