"""
Cartes des extensions japonaises que TCGdex liste sans aucune carte (Shiny Star V, ère XY, ADV, LEGEND…).

Liste reprise de LimitlessTCG comme TailTCG (``scripts/catalog-sync.mjs``), sinon de TCGplayer pour les extensions
antérieures à l'ère XY que Limitless ne couvre pas. Les identifiants suivent le format TCGdex (``S4a-001``) : une
carte ajoutée en collection garde le sien le jour où TCGdex publie l'extension.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.card_image_fallback_service import (
    CardImageUrls,
    tcgplayer_japanese_card_listings,
    tcgplayer_japanese_card_names,
)
from services.catalog_limitless_ja_service import LimitlessCard, limitless_jp_cards

_BASIC_ENERGY_TYPE = "Basic Energy"


@dataclass(frozen=True)
class ExternalCard:
    """Carte absente de TCGdex : numéro au format TCGdex, noms japonais et anglais, rareté, scans et source."""

    local_id: str
    name_ja: str | None
    name_en: str | None
    rarity: str | None
    images: CardImageUrls | None
    source: str


def external_set_cards(set_id: str) -> list[ExternalCard]:
    """
    Cartes d'une extension japonaise d'après Limitless, sinon TCGplayer ; vide quand aucune source ne la couvre.

    Args:
        set_id: Identifiant TCGdex de l'extension (``S4a``, ``ADV1``).
    """
    printed = [
        card
        for card in limitless_jp_cards(set_id)
        # Énergies de base sans numéro (« G », « NAN1 ») : hors de la liste imprimée de l'extension.
        if card.number.isdigit() or card.card_type != _BASIC_ENERGY_TYPE
    ]
    if printed:
        english_names = _missing_english_names(set_id, printed)
        return [
            ExternalCard(
                local_id=_tcgdex_local_id(card.number),
                name_ja=card.name_ja,
                name_en=card.name_en or english_names.get(card.number),
                rarity=card.rarity,
                images=_limitless_image_urls(card.image_xs),
                source="limitless",
            )
            for card in printed
        ]
    return [
        ExternalCard(
            local_id=_tcgdex_local_id(card.number),
            name_ja=None,
            name_en=card.name,
            rarity=card.rarity,
            images=card.urls,
            source="tcgplayer",
        )
        for card in tcgplayer_japanese_card_listings(set_id)
    ]


def external_card(set_id: str, local_id: str) -> ExternalCard | None:
    """
    Carte ``local_id`` d'une extension japonaise hors TCGdex, ``None`` quand aucune source ne la connaît.

    Args:
        set_id: Identifiant TCGdex de l'extension.
        local_id: Numéro de la carte, avec ou sans zéros (``7`` ou ``007``).
    """
    wanted = _tcgdex_local_id(local_id)
    return next((card for card in external_set_cards(set_id) if card.local_id == wanted), None)


def _missing_english_names(set_id: str, cards: list[LimitlessCard]) -> dict[str, str]:
    """Noms anglais TCGplayer par numéro, lus seulement si Limitless n'a pas traduit l'extension (ère XY)."""
    if all(card.name_en for card in cards):
        return {}
    return tcgplayer_japanese_card_names(set_id)


def _tcgdex_local_id(number: str) -> str:
    """Numéro au format TCGdex japonais : trois chiffres (« 7 » donne « 007 »), sinon tel quel."""
    stripped = number.strip()
    return stripped.zfill(3) if stripped.isdigit() else stripped


def _limitless_image_urls(image_xs: str | None) -> CardImageUrls | None:
    """Vignette (SM) et grande image (LG) Limitless déduites de l'aperçu XS de la liste."""
    if not image_xs or not image_xs.endswith("_XS.png"):
        return None
    return CardImageUrls(low=image_xs.replace("_XS.png", "_SM.png"), high=image_xs.replace("_XS.png", "_LG.png"))
