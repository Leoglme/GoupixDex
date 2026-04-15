"""Enchaîne plusieurs mises en ligne Vinted dans une seule session Chrome."""

from __future__ import annotations

import logging
import os
from typing import Any

from core.security import decrypt_vinted_credential
from models.article import Article
from models.user import User
from services import article_service
from services import vinted_batch_progress as batch_hub
from services.timer_service import TimerService
from services.vinted_publish_service import run_single_vinted_listing
from services.vinted_service import VintedService

logger = logging.getLogger(__name__)


async def _emit_job(job_id: str, step: str, message: str, *, form_step: str | None = None) -> None:
    ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
    if form_step is not None:
        ev["form_step"] = form_step
    await batch_hub.emit_event(job_id, ev)


async def run_vinted_batch_job(
    job_id: str,
    user_id: int,
    items: list[tuple[Article, list[str]]],
    user: User,
) -> None:
    """
    Une session navigateur : connexion Vinted une fois, puis ``run_single_vinted_listing`` pour chaque article.
    """
    email = user.vinted_email or os.environ.get("VINTED_EMAIL_OR_USERNAME")
    password = decrypt_vinted_credential(user.vinted_password) or os.environ.get("VINTED_PASSWORD")
    if not email or not password:
        await _emit_job(
            job_id,
            "auth",
            "Identifiants Vinted manquants — abandon du lot.",
            form_step="auth_missing",
        )
        await batch_hub.finish_job(
            job_id,
            {
                "summary": [],
                "vinted": {"published": False, "detail": "missing_vinted_credentials"},
            },
        )
        batch_hub.clear_active_job_for_user(user_id)
        batch_hub.cleanup_later(job_id)
        return

    async def forward_progress(ev: dict[str, Any]) -> None:
        await batch_hub.emit_event(job_id, ev)

    summary: list[dict[str, Any]] = []
    browser_started = False
    n = len(items)
    try:
        await _emit_job(job_id, "prep", "Préparation du navigateur pour le lot…", form_step="prep")
        await _emit_job(job_id, "browser", "Démarrage de Chrome…", form_step="browser_start")
        await VintedService.init_browser()
        browser_started = True
        await _emit_job(job_id, "browser", "Navigateur prêt.", form_step="browser_ready")
        await VintedService.init_page()
        await TimerService.wait(80)
        await _emit_job(job_id, "auth", "Connexion à Vinted…", form_step="auth_start")
        await VintedService.ensure_sign_in(email, password, form_progress=forward_progress)
        await _emit_job(job_id, "auth", "Connecté — enchaînement des annonces.", form_step="auth_ok")

    except Exception as exc:  # noqa: BLE001
        logger.exception("Vinted batch aborted before or during listings job_id=%s", job_id)
        await _emit_job(
            job_id,
            "error",
            f"Arrêt du lot : {exc}",
            form_step="failed",
        )
    else:
        for i, (article, sources) in enumerate(items):
            await batch_hub.emit_event(
                job_id,
                {
                    "type": "progress",
                    "current": i + 1,
                    "total": n,
                    "article_id": article.id,
                    "title": article.title,
                },
            )
            label = f"{i + 1}/{n}"
            try:
                r = await run_single_vinted_listing(
                    article,
                    user,
                    sources,
                    forward_progress,
                    batch_label=label,
                )
                summary.append({"article_id": article.id, **r})
                if bool(r.get("published")):
                    article_service.mark_article_published_on_vinted(article.id, user_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Vinted batch item failed article_id=%s", article.id)
                await _emit_job(
                    job_id,
                    "error",
                    f"[{label}] Erreur article #{article.id} : {exc}",
                    form_step="failed",
                )
                summary.append(
                    {"article_id": article.id, "published": False, "detail": str(exc)},
                )

        await _emit_job(job_id, "browser", "Fermeture du navigateur…", form_step="browser_close")
    finally:
        if browser_started:
            VintedService.close_browser()
        await batch_hub.finish_job(
            job_id,
            {
                "summary": summary,
                "vinted": {
                    "published": all(s.get("published") for s in summary) if summary else False,
                    "detail": "batch_complete",
                },
            },
        )
        batch_hub.clear_active_job_for_user(user_id)
        batch_hub.cleanup_later(job_id)
