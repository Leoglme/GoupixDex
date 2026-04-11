"""Vinted-related literal types (condition labels, package size)."""

from typing import Literal

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
