"""Cartes de collection d'un set dont TCGdex mélange les images : elles prennent l'image Limitless de leur numéro."""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from models.collection_card import CollectionCard
from services.catalog_external_cards_service import SETS_WITH_SHUFFLED_TCGDEX_IMAGES, limitless_image_of_shuffled_set
from services.tcgdex_client_service import split_tcgdex_card_id

logger = logging.getLogger(__name__)


def replace_shuffled_tcgdex_images() -> int:
    """Met l'image Limitless sur les cartes des sets où TCGdex mélange les images (connexion rendue pendant Limitless) ; renvoie leur nombre."""
    shuffled_set_ids = {set_id for _locale, set_id in SETS_WITH_SHUFFLED_TCGDEX_IMAGES}
    db = SessionLocal()
    try:
        rows = [
            (card.id, card.tcgdex_card_id, card.language, card.image_url)
            for card in db.query(CollectionCard).filter(CollectionCard.tcgdex_set_id.in_(shuffled_set_ids))
        ]
        db.rollback()
        replaced_images: list[tuple[int, str]] = []
        for card_id, tcgdex_card_id, language, image_url in rows:
            try:
                set_id, local_id = split_tcgdex_card_id(tcgdex_card_id)
            except ValueError:
                continue
            limitless_image = limitless_image_of_shuffled_set(language, set_id, local_id)
            if limitless_image is not None and limitless_image.low != image_url:
                replaced_images.append((card_id, limitless_image.low))
        for card_id, limitless_image_url in replaced_images:
            db.query(CollectionCard).filter(CollectionCard.id == card_id).update(
                {CollectionCard.image_url: limitless_image_url}
            )
        db.commit()
        return len(replaced_images)
    finally:
        db.close()


async def replace_shuffled_tcgdex_images_async() -> None:
    """Au démarrage : les cartes ajoutées avant de savoir que TCGdex mélange ces images retrouvent la bonne."""
    try:
        replaced = await asyncio.to_thread(replace_shuffled_tcgdex_images)
    except Exception:
        logger.exception("Repair of shuffled TCGdex card images crashed")
        return
    if replaced:
        logger.info("Shuffled TCGdex images: %d collection cards now show their Limitless image", replaced)
