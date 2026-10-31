"""
Libellés latins des séries, extensions et cartes japonaises : l'application n'affiche jamais d'écriture japonaise,
seules les images en gardent.

Nom d'une carte, de la source la plus sûre à la plus lointaine : son nom s'il est déjà latin, les noms anglais de
Limitless puis de TCGplayer pour son numéro, l'énergie de base ou l'espèce de son n° Pokédex, et à défaut
« Carte 012 ». Une série ou une extension sans nom latin connu prend son code.
"""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.database import SessionLocal
from models.collection_card import CollectionCard
from services.card_image_fallback_service import japanese_card_english_name, tcgplayer_japanese_card_names
from services.catalog_limitless_ja_service import latin_display_name_for_ja_set, limitless_en_card_names_for_set
from services.tcgdex_client_service import TcgdexClientService, split_tcgdex_card_id

logger = logging.getLogger(__name__)

_JAPANESE_SCRIPT_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]")
_UNKNOWN_CARD_LABEL = "Carte {local_id}"
_UNKNOWN_CARD_LABEL_RE = re.compile(r"^Carte \S+$")
_LOOKUP_WORKERS = 8
_SERIES_LATIN_NAMES: dict[str, str] = {
    "PMCG": "Pocket Monsters Card Game",
    "neo": "Neo",
    "e": "e-Card",
    "BW": "Black & White",
    "SM": "Sun & Moon",
    "S": "Sword & Shield",
    "M": "MEGA",
    "SV": "Scarlet & Violet",
}


def has_japanese_script(text: str | None) -> bool:
    """Vrai si le texte contient du hiragana, du katakana ou des kanji."""
    return bool(text and _JAPANESE_SCRIPT_RE.search(text))


def latin_series_name(series_id: str, series_name: str | None) -> str:
    """Nom latin d'une série japonaise (« 剣と盾 » donne « Sword & Shield »), son code quand il n'est pas connu."""
    known = _SERIES_LATIN_NAMES.get(series_id)
    if known:
        return known
    return series_name if series_name and not has_japanese_script(series_name) else series_id.upper()


def latin_set_name(set_id: str, set_name: str | None) -> str | None:
    """Nom d'extension sans japonais : le nom s'il est latin, sinon celui de Limitless, sinon le code (« SV2A »)."""
    if not has_japanese_script(set_name):
        return set_name
    return latin_display_name_for_ja_set(set_id) or set_id.upper()


def english_card_name(set_id: str, local_id: str, japanese_name: str, dex_id: int | None = None) -> str | None:
    """Nom anglais d'une carte japonaise d'après son numéro ou son n° Pokédex, sinon ``None``."""
    number = local_id.strip()
    limitless_names = limitless_en_card_names_for_set(set_id)
    padded_number = number.zfill(3) if number.isdigit() else number.upper()
    limitless_name = limitless_names.get(number) or limitless_names.get(padded_number)
    if limitless_name:
        return limitless_name
    tcgplayer_name = tcgplayer_japanese_card_names(set_id).get(number.lstrip("0") or number)
    return tcgplayer_name or japanese_card_english_name(japanese_name, dex_id)


def latin_card_label(set_id: str, local_id: str, name: str | None, dex_id: int | None = None) -> str:
    """Libellé affiché d'une carte : son nom s'il est latin, son nom anglais, sinon « Carte 012 »."""
    if name and not has_japanese_script(name):
        return name
    return english_card_name(set_id, local_id, name or "", dex_id) or _UNKNOWN_CARD_LABEL.format(local_id=local_id)


def _japanese_card_dex_id(card_id: str) -> int | None:
    """N° Pokédex d'une fiche TCGdex japonaise, ``None`` pour un dresseur, une énergie ou une fiche illisible."""
    try:
        dex_ids = TcgdexClientService().get_card("ja", card_id).get("dexId")
    except (RuntimeError, ValueError):
        return None
    return next((dex for dex in dex_ids or [] if isinstance(dex, int) and dex > 0), None)


def attach_latin_card_labels(cards: list[dict[str, Any]]) -> None:
    """Donne un ``display_name`` latin aux cartes TCGdex (``id``, ``localId``, ``name``) au nom japonais."""
    pending = [
        card
        for card in cards
        if isinstance(card.get("id"), str) and has_japanese_script(card.get("display_name") or card.get("name"))
    ]
    if not pending:
        return

    def preload_set_english_names(set_id: str) -> None:
        """Met en cache les noms anglais de Limitless et de TCGplayer d'une extension."""
        limitless_en_card_names_for_set(set_id)
        tcgplayer_japanese_card_names(set_id)

    def english_name(card: dict[str, Any], dex_id: int | None = None) -> str | None:
        """Nom anglais de la carte d'après son numéro et, s'il est connu, son n° Pokédex."""
        set_id, local_id = split_tcgdex_card_id(card["id"])
        return english_card_name(set_id, local_id, str(card.get("name") or ""), dex_id)

    with ThreadPoolExecutor(max_workers=_LOOKUP_WORKERS) as pool:
        list(pool.map(preload_set_english_names, sorted({split_tcgdex_card_id(card["id"])[0] for card in pending})))
        names = {card["id"]: english_name(card) for card in pending}
        unknown_ids = [card_id for card_id, name in names.items() if not name]
        dex_ids = dict(zip(unknown_ids, pool.map(_japanese_card_dex_id, unknown_ids), strict=True))
    for card in pending:
        card_id = card["id"]
        resolved = names[card_id] or english_name(card, dex_ids.get(card_id))
        card["display_name"] = resolved or _UNKNOWN_CARD_LABEL.format(local_id=split_tcgdex_card_id(card_id)[1])


def _needs_latin_label(set_name: str | None, display_name: str | None) -> bool:
    """Vrai pour une carte enregistrée avec un nom japonais, ou « Carte 012 » faute de nom connu à son ajout."""
    is_unknown_card = bool(display_name and _UNKNOWN_CARD_LABEL_RE.match(display_name))
    return has_japanese_script(set_name) or has_japanese_script(display_name) or is_unknown_card


def relabel_japanese_collection_cards() -> int:
    """
    Renomme en latin les cartes japonaises enregistrées en japonais ou en « Carte 012 », et renvoie leur nombre ;
    la connexion est rendue pendant les appels à Limitless et TCGplayer.
    """
    db = SessionLocal()
    try:
        rows = [
            (card.id, card.tcgdex_card_id, card.set_name, card.display_name)
            for card in db.query(CollectionCard).filter(CollectionCard.language == "ja")
            if _needs_latin_label(card.set_name, card.display_name)
        ]
        db.rollback()
        renamed: list[tuple[int, str | None, str]] = []
        for card_id, tcgdex_card_id, set_name, display_name in rows:
            try:
                set_id, local_id = split_tcgdex_card_id(tcgdex_card_id)
            except ValueError:
                continue
            known_name = None if _UNKNOWN_CARD_LABEL_RE.match(display_name or "") else display_name
            latin_set, latin_name = latin_set_name(set_id, set_name), latin_card_label(set_id, local_id, known_name)
            if (latin_set, latin_name) != (set_name, display_name):
                renamed.append((card_id, latin_set, latin_name))
        for card_id, latin_set, latin_name in renamed:
            db.query(CollectionCard).filter(CollectionCard.id == card_id).update(
                {CollectionCard.set_name: latin_set, CollectionCard.display_name: latin_name}
            )
        db.commit()
        return len(renamed)
    finally:
        db.close()


async def relabel_japanese_collection_cards_async() -> None:
    """Au démarrage : les cartes japonaises enregistrées avec un nom en japonais prennent leur libellé latin."""
    try:
        renamed = await asyncio.to_thread(relabel_japanese_collection_cards)
    except Exception:
        logger.exception("Latin relabelling of Japanese collection cards crashed")
        return
    if renamed:
        logger.info("Latin labels: %d Japanese collection cards renamed", renamed)
