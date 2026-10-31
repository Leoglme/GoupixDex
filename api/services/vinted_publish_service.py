"""Publish an article to Vinted using the existing nodriver ``VintedService``."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app_types.payload import ItemPayload
from config import config
from core.security import decrypt_vinted_credential
from models.article import Article
from models.user import User
from services.os_service import get_project_root
from services.timer_service import TimerService
from services.vinted_service import VintedPublishNotConfirmedError, VintedService

logger = logging.getLogger(__name__)

_WARDROBE_LOOKUPS_AFTER_UNCONFIRMED_PUBLISH = 3
_WARDROBE_LOOKUP_INTERVAL_MS = 4000

_CONDITION_TO_VINTED: dict[str, str] = {
    "Mint": "Neuf sans étiquette",
    "Near Mint": "Neuf sans étiquette",
    "NM": "Neuf sans étiquette",
    "Excellent": "Très bon état",
    "Good": "Bon état",
    "Played": "Satisfaisant",
    "Lightly Played": "Bon état",
    "Poor": "Satisfaisant",
}


def _vinted_condition(article: Article) -> str:
    if article.is_graded:
        return "Neuf avec étiquette"
    key = (article.condition or "").strip()
    return _CONDITION_TO_VINTED.get(key, "Neuf sans étiquette")


def listed_vinted_price(article: Article) -> Decimal:
    """
    Prix affiché sur l’annonce Vinted : prix de vente, à défaut prix d’achat.

    Args:
        article: Article publié (ou à publier) sur Vinted.

    Returns:
        Le prix saisi dans le formulaire Vinted.
    """
    return article.sell_price if article.sell_price is not None else article.purchase_price


async def _resolve_published_vinted_id(article: Article, price: float) -> int | None:
    """
    Lit sur le dressing l’id Vinted de l’annonce tout juste publiée, tant que l’onglet est encore ouvert.

    Args:
        article: Article qui vient d’être publié.
        price: Prix saisi sur Vinted.

    Returns:
        L’id Vinted, ou ``None`` s’il n’a pas pu être lu (la publication reste valide).
    """
    try:
        return await VintedService.find_member_listing_item_id_for_match(
            VintedService._require_tab(),
            title=article.title or "",
            sell_price=price,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("vinted_id resolve after publish failed article_id=%s: %s", article.id, exc)
        return None


async def _find_listing_created_without_confirmation(
    article: Article, price: float, other_articles_listing_ids: frozenset[int]
) -> int | None:
    """
    Cherche sur le dressing l'annonce que Vinted a créée sans afficher de confirmation ; elle peut mettre quelques secondes à y apparaître.

    Args:
        article: Article qui vient d'être soumis.
        price: Prix saisi sur Vinted.
        other_articles_listing_ids: Annonces déjà reliées à d'autres articles, jamais retenues.

    Returns:
        L'id Vinted de l'annonce, ou ``None`` si le dressing ne la montre pas.
    """
    for lookup_index in range(_WARDROBE_LOOKUPS_AFTER_UNCONFIRMED_PUBLISH):
        if lookup_index:
            await TimerService.wait(_WARDROBE_LOOKUP_INTERVAL_MS)
        listing_id = await VintedService.find_unclaimed_wardrobe_listing(
            title=article.title or "",
            sell_price=price,
            other_articles_listing_ids=other_articles_listing_ids,
        )
        if listing_id is not None:
            return listing_id
    return None


ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit(
    progress: ProgressFn | None,
    step: str,
    message: str,
    *,
    form_step: str | None = None,
    detail: str | None = None,
    screenshot: str | None = None,
) -> None:
    if progress is None:
        return
    ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
    if form_step is not None:
        ev["form_step"] = form_step
    if detail is not None:
        ev["detail"] = detail
    if screenshot:
        ev["screenshot"] = screenshot
    await progress(ev)


async def _materialize_listing_images(
    article_id: int,
    sources: list[str],
    images_dir: Path,
) -> list[str]:
    """
    Prepare local files for nodriver: download HTTPS URLs, copy local paths.
    Returns basenames in ``images_dir``.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    basenames: list[str] = []

    async def _one_http(src: str, client: httpx.AsyncClient) -> str:
        try:
            resp = await client.get(src)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Vinted image download failed %s: %s", src, exc)
            raise RuntimeError(f"Image download failed: {src}") from exc
        path_part = urlparse(src).path
        ext = Path(path_part).suffix or ".jpg"
        if not ext.startswith("."):
            ext = f".{ext}"
        name = f"listing_{article_id}_{uuid.uuid4().hex[:10]}{ext}"
        dst = images_dir / name
        dst.write_bytes(resp.content)
        return name

    def _one_local(src: str) -> str:
        p = Path(src)
        if not p.is_file():
            raise RuntimeError(f"Image file not found for Vinted: {src}")
        ext = p.suffix or ".jpg"
        name = f"listing_{article_id}_{uuid.uuid4().hex[:10]}{ext}"
        dst = images_dir / name
        shutil.copy2(p, dst)
        return name

    http_sources = [s for s in sources if s.startswith("http://") or s.startswith("https://")]
    if http_sources:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            for src in sources:
                if src.startswith("http://") or src.startswith("https://"):
                    basenames.append(await _one_http(src, client))
                else:
                    basenames.append(_one_local(src))
    else:
        for src in sources:
            basenames.append(_one_local(src))

    return basenames


async def run_single_vinted_listing(
    article: Article,
    user: User,
    stored_image_sources: list[str],
    progress: ProgressFn | None,
    *,
    batch_label: str | None = None,
    other_articles_listing_ids: frozenset[int] = frozenset(),
    may_reuse_wardrobe_listing: bool = False,
) -> dict[str, Any]:
    """
    Full listing flow on an already-open Vinted page:
    materialize images, open sell, fill, publish.
    Does not start or stop Chrome (caller reuses the session).

    Args:
        other_articles_listing_ids: Annonces reliées à d'autres articles, jamais reprises.
        may_reuse_wardrobe_listing: Reprend l'annonce du dressing portant ce titre (créée par un essai que Vinted n'a pas confirmé) au lieu de publier deux fois.
    """
    _ = user  # reserved (symmetry with public API)
    prefix = f"{batch_label} — " if batch_label else ""
    price = float(listed_vinted_price(article))

    if may_reuse_wardrobe_listing:
        listing_already_online = await VintedService.find_unclaimed_wardrobe_listing(
            title=article.title or "",
            sell_price=price,
            other_articles_listing_ids=other_articles_listing_ids,
        )
        if listing_already_online is not None:
            await _emit(
                progress,
                "publish",
                f"{prefix}Already on your Vinted wardrobe (listing #{listing_already_online}): not listed twice.",
                form_step="publish_confirmed",
            )
            return {
                "published": True,
                "detail": "already_listed",
                "article_id": article.id,
                "vinted_id": listing_already_online,
            }

    root = get_project_root()
    images_dir = root / "images"

    await _emit(
        progress,
        "start",
        f"{prefix}Preparing images (article #{article.id})…",
        form_step="prep",
    )

    basenames = await _materialize_listing_images(article.id, stored_image_sources, images_dir)

    await _emit(
        progress,
        "images",
        f"{prefix}{len(basenames)} image(s) ready for the listing.",
        form_step="images_copy",
        detail=f"{len(basenames)} file(s)",
    )

    payload: ItemPayload = {
        "title": article.title,
        "description": article.description,
        "price": price,
        "condition": _vinted_condition(article),
        "images": basenames,
    }

    await _emit(progress, "page", f"{prefix}Opening the sell page…", form_step="sell_page")
    await VintedService.open_sell_item_page()
    await _emit(
        progress,
        "form",
        f"{prefix}Filling the Vinted listing form…",
        form_step="form_batch",
    )

    async def _form_payload(ev: dict[str, Any]) -> None:
        if progress:
            await progress(ev)

    await VintedService.fill_item_details(
        payload,
        config["category_path"],
        config["brand"],
        config["package_size"],
        progress=_form_payload,
    )
    await TimerService.wait(400)
    await _emit(progress, "publish", f"{prefix}Submitting the listing…", form_step="publish_click")
    try:
        await VintedService.publish(progress=progress)
    except VintedPublishNotConfirmedError:
        created_listing_id = (
            await _find_listing_created_without_confirmation(article, price, other_articles_listing_ids)
            if may_reuse_wardrobe_listing
            else None
        )
        if created_listing_id is None:
            raise
        await _emit(
            progress,
            "publish",
            f"{prefix}Listing found on your Vinted wardrobe (#{created_listing_id}).",
            form_step="publish_confirmed",
        )
        return {"published": True, "detail": "published", "article_id": article.id, "vinted_id": created_listing_id}
    await TimerService.wait(500)
    vinted_id = await _resolve_published_vinted_id(article, price)
    return {"published": True, "detail": "published", "article_id": article.id, "vinted_id": vinted_id}


async def publish_article_to_vinted(
    article: Article,
    user: User,
    stored_image_sources: list[str],
    *,
    progress: ProgressFn | None = None,
    vinted_password_plain: str | None = None,
    other_articles_listing_ids: frozenset[int] = frozenset(),
    may_reuse_wardrobe_listing: bool = False,
) -> dict[str, object]:
    """
    Attempt to list an article on Vinted. Does not raise on failure; returns status dict.
    ``other_articles_listing_ids`` / ``may_reuse_wardrobe_listing`` : voir :func:`run_single_vinted_listing`.

    Password: decrypted ``user.vinted_password`` (Fernet), else ``VINTED_PASSWORD`` env.
    Legacy bcrypt rows cannot be recovered; use env or re-save Vinted password in user settings.
    """
    email = user.vinted_email or os.environ.get("VINTED_EMAIL_OR_USERNAME")
    if vinted_password_plain is not None:
        password = vinted_password_plain
    else:
        password = decrypt_vinted_credential(user.vinted_password) or os.environ.get(
            "VINTED_PASSWORD"
        )

    if not email or not password:
        logger.warning("Vinted publish skipped: missing credentials article_id=%s", article.id)
        await _emit(progress, "auth", "Missing Vinted credentials — aborting.", form_step="auth_missing")
        return {"published": False, "detail": "missing_vinted_credentials"}

    await _emit(progress, "start", "Preparing images and browser…", form_step="prep")

    browser_started = False
    try:
        await _emit(progress, "browser", "Starting Chrome…", form_step="browser_start")
        await VintedService.init_browser()
        browser_started = True
        await _emit(progress, "browser", "Browser ready.", form_step="browser_ready")
        await VintedService.init_page()
        await TimerService.wait(80)
        await _emit(progress, "auth", "Signing in to Vinted…", form_step="auth_start")
        await VintedService.ensure_sign_in(email, password, form_progress=progress)
        await _emit(progress, "auth", "Signed in.", form_step="auth_ok")
        listing = await run_single_vinted_listing(
            article,
            user,
            stored_image_sources,
            progress,
            other_articles_listing_ids=other_articles_listing_ids,
            may_reuse_wardrobe_listing=may_reuse_wardrobe_listing,
        )
        await _emit(progress, "browser", "Closing browser…", form_step="browser_close")
        return {"published": True, "detail": listing.get("detail", "published"), "vinted_id": listing.get("vinted_id")}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vinted publish failed article_id=%s", article.id)
        await _emit(progress, "error", f"Error: {exc}", form_step="failed", detail=str(exc))
        return {"published": False, "detail": str(exc)}
    finally:
        if browser_started:
            await VintedService.shutdown_browser()
