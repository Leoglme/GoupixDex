"""
Leboncoin « Loisirs → Collection → Jeux de cartes » — libellés UI et mapping depuis GoupixDex.

Les valeurs ``LEBONCOIN_*`` correspondent aux options visibles dans le dépôt d’annonce (combobox).
Les clés ``APP_CONDITION_*`` reprennent le formulaire article (``GoupixDexArticleForm``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from models.article import Article

# --- Libellés Leboncoin (assistant dépôt, catégorie Collection / Jeux de cartes) ---

LEBONCOIN_PRODUIT_JEUX_CARTES: Final[str] = "Jeux de cartes"

LEBONCOIN_ETAT_NEUF: Final[str] = "État neuf"
LEBONCOIN_ETAT_TRES_BON: Final[str] = "Très bon état"
LEBONCOIN_ETAT_BON: Final[str] = "Bon état"
LEBONCOIN_ETAT_SATISFAISANT: Final[str] = "État satisfaisant"

LEBONCOIN_ETATS: Final[tuple[str, ...]] = (
    LEBONCOIN_ETAT_NEUF,
    LEBONCOIN_ETAT_TRES_BON,
    LEBONCOIN_ETAT_BON,
    LEBONCOIN_ETAT_SATISFAISANT,
)

LEBONCOIN_COND_BLISTER: Final[str] = "Sous blister / scellé"
LEBONCOIN_COND_BOITE: Final[str] = "Avec boîte d'origine"
LEBONCOIN_COND_SANS: Final[str] = "Sans emballage"
LEBONCOIN_COND_LOT: Final[str] = "Lot / collection groupée"

LEBONCOIN_CONDITIONNEMENTS: Final[tuple[str, ...]] = (
    LEBONCOIN_COND_BLISTER,
    LEBONCOIN_COND_BOITE,
    LEBONCOIN_COND_SANS,
    LEBONCOIN_COND_LOT,
)

LEBONCOIN_EPOQUE_APRES_2010: Final[str] = "Après 2010"
LEBONCOIN_EPOQUE_1990_2010: Final[str] = "1990–2010"
LEBONCOIN_EPOQUE_1970_1990: Final[str] = "1970–1990"
LEBONCOIN_EPOQUE_AUTRE: Final[str] = "Autre"

LEBONCOIN_EPOQUES: Final[tuple[str, ...]] = (
    "Avant 1900",
    "1900–1945",
    "1945–1970",
    LEBONCOIN_EPOQUE_1970_1990,
    LEBONCOIN_EPOQUE_1990_2010,
    LEBONCOIN_EPOQUE_APRES_2010,
    LEBONCOIN_EPOQUE_AUTRE,
)

# Suggestion catégorie (étape titre) — bouton « Loisirs → Collection ».
LEBONCOIN_CATEGORY_SUGGESTION_COLLECTION: Final[str] = "Collection"

# Type d’annonce (radio, généralement pré-coché).
LEBONCOIN_AD_TYPE_OFFRE: Final[str] = "Offre"

# --- Mapping état GoupixDex → état Leboncoin ---

_APP_CONDITION_TO_LEBONCOIN_ETAT: dict[str, str] = {
    "Mint": LEBONCOIN_ETAT_NEUF,
    "Near Mint": LEBONCOIN_ETAT_TRES_BON,
    "NM": LEBONCOIN_ETAT_TRES_BON,
    "Excellent": LEBONCOIN_ETAT_TRES_BON,
    "Good": LEBONCOIN_ETAT_BON,
    "Lightly Played": LEBONCOIN_ETAT_BON,
    "Played": LEBONCOIN_ETAT_SATISFAISANT,
    "Poor": LEBONCOIN_ETAT_SATISFAISANT,
    "Moderately Played": LEBONCOIN_ETAT_BON,
    "Very Good": LEBONCOIN_ETAT_BON,
    "Heavily Played": LEBONCOIN_ETAT_SATISFAISANT,
}


def leboncoin_etat_from_app_condition(app_condition: str, *, is_graded: bool = False) -> str:
    """Libellé combobox « État » sur Leboncoin."""
    if is_graded:
        return LEBONCOIN_ETAT_NEUF
    key = (app_condition or "").strip()
    return _APP_CONDITION_TO_LEBONCOIN_ETAT.get(key, LEBONCOIN_ETAT_TRES_BON)


def leboncoin_conditionnement_from_article(article: Article) -> str:
    """Libellé combobox « Conditionnement » (carte à l’unité vs slab vs lot)."""
    if article.is_graded:
        return LEBONCOIN_COND_BOITE
    title_low = (article.title or "").lower()
    if "lot" in title_low or "bundle" in title_low:
        return LEBONCOIN_COND_LOT
    return LEBONCOIN_COND_SANS


def leboncoin_epoque_from_article(article: Article) -> str | None:
    """
    « Époque » est souvent optionnelle ; on renseigne une valeur plausible pour les cartes Pokémon modernes.
    """
    code = (article.set_code or "").strip().upper()
    if not code:
        return LEBONCOIN_EPOQUE_APRES_2010
    vintage_prefixes = ("BS", "JU", "FO", "TR", "GYM", "NEO", "LC", "EX", "DP", "HGSS", "BW")
    if any(code.startswith(p) for p in vintage_prefixes) or code in {"BS", "BASE"}:
        return LEBONCOIN_EPOQUE_1990_2010
    return LEBONCOIN_EPOQUE_APRES_2010


@dataclass(frozen=True)
class LeboncoinListingFields:
    """Attributs structurés pour l’étape « Dites-nous en plus »."""

    produit: str
    etat: str
    conditionnement: str
    epoque: str | None
    category_suggestion: str = LEBONCOIN_CATEGORY_SUGGESTION_COLLECTION


def leboncoin_listing_fields_from_article(article: Article) -> LeboncoinListingFields:
    return LeboncoinListingFields(
        produit=LEBONCOIN_PRODUIT_JEUX_CARTES,
        etat=leboncoin_etat_from_app_condition(article.condition, is_graded=article.is_graded),
        conditionnement=leboncoin_conditionnement_from_article(article),
        epoque=leboncoin_epoque_from_article(article),
    )
