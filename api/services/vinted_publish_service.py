"""Publish an article to Vinted using the existing nodriver ``VintedService``."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path

from app_types.payload import ItemPayload
from config import config, get_settings
from core.security import decrypt_vinted_credential
from models.article import Article
from models.user import User
from services.os_service import get_project_root
from services.timer_service import TimerService
from services.vinted_service import VintedService

logger = logging.getLogger(__name__)

_CONDITION_TO_VINTED: dict[str, str] = {
    "Near Mint": "Très bon état",
    "NM": "Très bon état",
    "Mint": "Neuf sans étiquette",
    "Lightly Played": "Bon état",
    "Played": "Satisfaisant",
    "Poor": "Satisfaisant",
}


def _vinted_condition(app_condition: str) -> str:
    return _CONDITION_TO_VINTED.get(app_condition.strip(), "Très bon état")


async def publish_article_to_vinted(
    article: Article,
    user: User,
    stored_image_paths: list[Path],
) -> dict[str, object]:
    """
    Attempt to list an article on Vinted. Does not raise on failure; returns status dict.

    Password: decrypted ``user.vinted_password`` (Fernet), else ``VINTED_PASSWORD`` env.
    Legacy bcrypt rows cannot be recovered; use env or re-save Vinted password in user settings.
    """
    settings = get_settings()
    if settings.vinted_publish_stub:
        logger.info("Vinted publish stub: skip article_id=%s", article.id)
        return {"published": False, "stub": True, "detail": "stub mode"}

    email = user.vinted_email or os.environ.get("VINTED_EMAIL_OR_USERNAME")
    password = decrypt_vinted_credential(user.vinted_password) or os.environ.get(
        "VINTED_PASSWORD"
    )

    if not email or not password:
        logger.warning("Vinted publish skipped: missing credentials article_id=%s", article.id)
        return {"published": False, "detail": "missing_vinted_credentials"}

    root = get_project_root()
    images_dir = root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    basenames: list[str] = []
    for src in stored_image_paths:
        ext = src.suffix or ".jpg"
        name = f"listing_{article.id}_{uuid.uuid4().hex[:10]}{ext}"
        dst = images_dir / name
        shutil.copy2(src, dst)
        basenames.append(name)

    price = float(article.sell_price if article.sell_price is not None else article.purchase_price)
    payload: ItemPayload = {
        "title": article.title,
        "description": article.description,
        "price": price,
        "condition": _vinted_condition(article.condition),
        "images": basenames,
    }

    try:
        await VintedService.init_browser()
        await VintedService.init_page()
        await TimerService.wait(400)
        await VintedService.ensure_sign_in(email, password)
        await VintedService.open_sell_item_page()
        await TimerService.wait(2500)
        await VintedService.fill_item_details(
            payload,
            config["category_path"],
            config["brand"],
            config["package_size"],
        )
        await TimerService.wait(2000)
        return {"published": True, "detail": "form_filled"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vinted publish failed article_id=%s", article.id)
        return {"published": False, "detail": str(exc)}
