"""Publish a GoupixDex article on Leboncoin (desktop nodriver worker)."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from models.article import Article
from services.leboncoin_listing_copy import build_leboncoin_listing_copy
from services.leboncoin_listing_maps import leboncoin_listing_fields_from_article
from services.leboncoin_service import LeboncoinService
from services.os_service import get_project_root
from services.timer_service import TimerService
from services.vinted_publish_service import _materialize_listing_images

logger = logging.getLogger(__name__)

ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]
DepositedFn = Callable[[], Awaitable[None]]


def _submit_final_enabled() -> bool:
    """``LEBONCOIN_DRY_RUN=1`` remplit l’assistant sans cliquer sur « Déposer mon annonce »."""
    return os.environ.get("LEBONCOIN_DRY_RUN", "").strip().lower() not in ("1", "true", "yes", "on")


async def _emit(progress: ProgressFn | None, step: str, message: str, *, form_step: str | None = None) -> None:
    if progress is None:
        return
    ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
    if form_step:
        ev["form_step"] = form_step
    await progress(ev)


async def _signal_deposit_and_find_listing_id(
    title: str, progress: ProgressFn | None, on_deposited: DepositedFn | None
) -> str | None:
    """
    Signale le dépôt puis cherche le lien de l'annonce dans « Mes annonces », sans jamais faire échouer la publication.

    Returns:
        L'identifiant de l'annonce, ou None quand Leboncoin ne l'y affiche pas encore.
    """
    listing_id: str | None = None
    try:
        if on_deposited is not None:
            await on_deposited()
        await _emit(progress, "listing_link", "Annonce déposée — récupération de son lien dans « Mes annonces »…")
        listing_id = await LeboncoinService.find_listing_id_in_my_ads(title)
    except Exception:
        logger.warning("Leboncoin listing lookup failed", exc_info=True)
    if listing_id:
        await _emit(progress, "listing_link", "Lien de l’annonce Leboncoin récupéré.")
    else:
        await _emit(
            progress,
            "listing_link",
            "Annonce pas encore visible dans « Mes annonces » (validation Leboncoin) : "
            "« Voir sur Leboncoin » ouvrira vos annonces.",
        )
    return listing_id


async def publish_article_to_leboncoin(
    article: Article,
    stored_image_sources: list[str],
    *,
    postal_code: str,
    sender_line1: str,
    sender_city: str,
    progress: ProgressFn | None = None,
    submit_final: bool | None = None,
    on_deposited: DepositedFn | None = None,
) -> dict[str, Any]:
    """
    List one article on Leboncoin using a logged-in Chromium profile.
    Does not raise on failure; returns a status dict for SSE ``done``.
    ``on_deposited`` est appelé dès le dépôt de l'annonce, avant la recherche de son lien dans « Mes annonces ».
    """
    line1 = sender_line1.strip()
    pc = postal_code.strip()
    town = sender_city.strip()

    if not pc or not line1 or not town:
        await _emit(
            progress,
            "config",
            "Adresse expéditeur incomplète (Paramètres → Adresse d’expédition).",
            form_step="address_missing",
        )
        return {"published": False, "detail": "missing_sender_address"}

    if submit_final is None:
        submit_final = _submit_final_enabled()

    root = get_project_root()
    images_dir = root / "images"

    title, description = build_leboncoin_listing_copy(article)
    listing_fields = leboncoin_listing_fields_from_article(article)

    await _emit(progress, "start", "Préparation des photos…", form_step="prep")
    basenames = await _materialize_listing_images(article.id, stored_image_sources, images_dir)

    price = float(article.sell_price if article.sell_price is not None else article.purchase_price)

    async with LeboncoinService.browser_job_lock:
        browser_started = False
        try:
            await _emit(progress, "browser", "Ouverture de Chrome (profil Leboncoin)…", form_step="browser_start")
            await LeboncoinService.init_browser()
            browser_started = True
            await LeboncoinService.init_page()
            await TimerService.wait(100)

            result = await LeboncoinService.publish_pokemon_listing(
                title=title,
                description=description,
                price_eur=price,
                postal_code=pc,
                address_line1=line1,
                city=town,
                photo_basenames=basenames,
                listing_fields=listing_fields,
                progress=progress,
                submit_final=submit_final,
            )
            if result.get("dry_run"):
                return {
                    "published": False,
                    "detail": "dry_run_ready",
                    "url": result.get("url"),
                }
            listing_id = result.get("listing_id")
            if not listing_id:
                listing_id = await _signal_deposit_and_find_listing_id(title, progress, on_deposited)
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
            for name in basenames:
                try:
                    p = images_dir / name
                    if p.is_file() and name.startswith(f"listing_{article.id}_"):
                        p.unlink(missing_ok=True)
                except OSError:
                    pass
