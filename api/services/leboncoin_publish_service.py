"""Publish a GoupixDex article on Leboncoin (desktop nodriver worker)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from models.article import Article
from services.leboncoin_service import LeboncoinService
from services.os_service import get_project_root
from services.timer_service import TimerService
from services.vinted_publish_service import _materialize_listing_images

logger = logging.getLogger(__name__)

ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit(progress: ProgressFn | None, step: str, message: str, *, form_step: str | None = None) -> None:
    if progress is None:
        return
    ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
    if form_step:
        ev["form_step"] = form_step
    await progress(ev)


async def publish_article_to_leboncoin(
    article: Article,
    stored_image_sources: list[str],
    *,
    postal_code: str,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """
    List one article on Leboncoin using a logged-in Chromium profile.
    Does not raise on failure; returns a status dict for SSE ``done``.
    """
    if not postal_code.strip():
        await _emit(progress, "config", "Code postal expéditeur manquant (Paramètres → Expédition).", form_step="postal_missing")
        return {"published": False, "detail": "missing_postal_code"}

    root = get_project_root()
    images_dir = root / "images"

    await _emit(progress, "start", "Préparation des photos…", form_step="prep")
    basenames = await _materialize_listing_images(article.id, stored_image_sources, images_dir)

    price = float(article.sell_price if article.sell_price is not None else article.purchase_price)

    browser_started = False
    try:
        await _emit(progress, "browser", "Ouverture de Chrome (profil Leboncoin)…", form_step="browser_start")
        await LeboncoinService.init_browser()
        browser_started = True
        await LeboncoinService.init_page()
        await TimerService.wait(100)

        result = await LeboncoinService.publish_pokemon_listing(
            title=article.title or "Carte Pokémon",
            description=article.description or "",
            price_eur=price,
            postal_code=postal_code.strip(),
            photo_basenames=basenames,
            progress=progress,
        )
        listing_id = result.get("listing_id")
        return {
            "published": True,
            "detail": "published",
            "listing_id": str(listing_id) if listing_id else None,
            "url": result.get("url"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Leboncoin publish failed article_id=%s", article.id)
        await _emit(progress, "error", f"Erreur : {exc}", form_step="failed")
        return {"published": False, "detail": str(exc)}
    finally:
        if browser_started:
            LeboncoinService.close_browser()
        # Best-effort cleanup of temp listing files
        for name in basenames:
            try:
                p = images_dir / name
                if p.is_file() and name.startswith(f"listing_{article.id}_"):
                    p.unlink(missing_ok=True)
            except OSError:
                pass
