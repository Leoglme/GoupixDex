"""Publish an article to Vinted using the existing nodriver ``VintedService``."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from collections.abc import Awaitable, Callable
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
from services.vinted_service import VintedService

logger = logging.getLogger(__name__)

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


def _vinted_condition(app_condition: str) -> str:
    return _CONDITION_TO_VINTED.get(app_condition.strip(), "Neuf sans étiquette")


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
    Prépare des fichiers locaux pour nodrive : URLs HTTPS téléchargées, chemins locaux copiés.
    Renvoie les noms de fichiers (basename) dans ``images_dir``.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    basenames: list[str] = []

    async def _one_http(src: str, client: httpx.AsyncClient) -> str:
        try:
            resp = await client.get(src)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Téléchargement image Vinted échoué %s: %s", src, exc)
            raise RuntimeError(f"Téléchargement image impossible: {src}") from exc
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
            raise RuntimeError(f"Fichier image introuvable pour Vinted: {src}")
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
) -> dict[str, Any]:
    """
    Une annonce complète sur la page Vinted déjà ouverte dans le navigateur :
    matérialise les images, ouvre « vendre », remplit, publie.
    Ne démarre ni ne ferme Chrome (session réutilisée par l'appelant).
    """
    _ = user  # réservé (symétrie avec l'API publique)
    prefix = f"{batch_label} — " if batch_label else ""

    root = get_project_root()
    images_dir = root / "images"

    await _emit(
        progress,
        "start",
        f"{prefix}Préparation des images (article #{article.id})…",
        form_step="prep",
    )

    basenames = await _materialize_listing_images(article.id, stored_image_sources, images_dir)

    await _emit(
        progress,
        "images",
        f"{prefix}{len(basenames)} image(s) prête(s) pour l'annonce.",
        form_step="images_copy",
        detail=f"{len(basenames)} fichier(s)",
    )

    price = float(article.sell_price if article.sell_price is not None else article.purchase_price)
    payload: ItemPayload = {
        "title": article.title,
        "description": article.description,
        "price": price,
        "condition": _vinted_condition(article.condition),
        "images": basenames,
    }

    await _emit(progress, "page", f"{prefix}Ouverture de la page « vendre »…", form_step="sell_page")
    await VintedService.open_sell_item_page()
    await _emit(
        progress,
        "form",
        f"{prefix}Remplissage du formulaire Vinted…",
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
    await _emit(progress, "publish", f"{prefix}Envoi de l'annonce…", form_step="publish_click")
    await VintedService.publish(progress=progress)
    await TimerService.wait(500)
    return {"published": True, "detail": "published", "article_id": article.id}


async def publish_article_to_vinted(
    article: Article,
    user: User,
    stored_image_sources: list[str],
    *,
    progress: ProgressFn | None = None,
    vinted_password_plain: str | None = None,
) -> dict[str, object]:
    """
    Attempt to list an article on Vinted. Does not raise on failure; returns status dict.

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
        await _emit(progress, "auth", "Identifiants Vinted manquants — abandon.", form_step="auth_missing")
        return {"published": False, "detail": "missing_vinted_credentials"}

    await _emit(progress, "start", "Préparation des images et du navigateur…", form_step="prep")

    browser_started = False
    try:
        await _emit(progress, "browser", "Démarrage de Chrome…", form_step="browser_start")
        await VintedService.init_browser()
        browser_started = True
        await _emit(progress, "browser", "Navigateur prêt.", form_step="browser_ready")
        await VintedService.init_page()
        await TimerService.wait(80)
        await _emit(progress, "auth", "Connexion à Vinted…", form_step="auth_start")
        await VintedService.ensure_sign_in(email, password, form_progress=progress)
        await _emit(progress, "auth", "Connecté.", form_step="auth_ok")
        await run_single_vinted_listing(article, user, stored_image_sources, progress)
        await _emit(progress, "browser", "Fermeture du navigateur…", form_step="browser_close")
        return {"published": True, "detail": "published"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vinted publish failed article_id=%s", article.id)
        await _emit(progress, "error", f"Erreur : {exc}", form_step="failed", detail=str(exc))
        return {"published": False, "detail": str(exc)}
    finally:
        if browser_started:
            VintedService.close_browser()
