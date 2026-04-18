"""Chain several Vinted listings in a single Chrome session."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from core.security import decrypt_vinted_credential
from models.article import Article
from models.user import User
from services import article_service
from services.timer_service import TimerService
from services.vinted_batch_session_service import VintedBatchSessionService as batch_hub
from services.vinted_publish_service import run_single_vinted_listing
from services.vinted_service import VintedService

logger = logging.getLogger(__name__)


class VintedBatchOrchestratorService:
    """One browser session for multiple Vinted listings."""

    @staticmethod
    async def _emit_job(
        job_id: str, step: str, message: str, *, form_step: str | None = None
    ) -> None:
        ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
        if form_step is not None:
            ev["form_step"] = form_step
        await batch_hub.emit_event(job_id, ev)

    @staticmethod
    async def run_vinted_batch_job(
        job_id: str,
        user_id: int,
        items: list[tuple[Article, list[str]]],
        user: User,
        *,
        vinted_password_plain: str | None = None,
        mark_published: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> None:
        """
        One browser session: sign in to Vinted once, then ``run_single_vinted_listing`` for each article.
        """
        email = user.vinted_email or os.environ.get("VINTED_EMAIL_OR_USERNAME")
        if vinted_password_plain is not None:
            password = vinted_password_plain
        else:
            password = decrypt_vinted_credential(user.vinted_password) or os.environ.get("VINTED_PASSWORD")
        if not email or not password:
            await VintedBatchOrchestratorService._emit_job(
                job_id,
                "auth",
                "Missing Vinted credentials — aborting batch.",
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
            await VintedBatchOrchestratorService._emit_job(
                job_id, "prep", "Preparing browser for batch…", form_step="prep"
            )
            await VintedBatchOrchestratorService._emit_job(
                job_id, "browser", "Starting Chrome…", form_step="browser_start"
            )
            await VintedService.init_browser()
            browser_started = True
            await VintedBatchOrchestratorService._emit_job(
                job_id, "browser", "Browser ready.", form_step="browser_ready"
            )
            await VintedService.init_page()
            await TimerService.wait(80)
            await VintedBatchOrchestratorService._emit_job(
                job_id, "auth", "Signing in to Vinted…", form_step="auth_start"
            )
            await VintedService.ensure_sign_in(email, password, form_progress=forward_progress)
            await VintedBatchOrchestratorService._emit_job(
                job_id, "auth", "Signed in — processing listings.", form_step="auth_ok"
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("Vinted batch aborted before or during listings job_id=%s", job_id)
            await VintedBatchOrchestratorService._emit_job(
                job_id,
                "error",
                f"Batch stopped: {exc}",
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
                        if mark_published is not None:
                            await mark_published(article.id, user_id)
                        else:
                            article_service.mark_article_published_on_vinted(article.id, user_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Vinted batch item failed article_id=%s", article.id)
                    await VintedBatchOrchestratorService._emit_job(
                        job_id,
                        "error",
                        f"[{label}] Erreur article #{article.id} : {exc}",
                        form_step="failed",
                    )
                    summary.append(
                        {"article_id": article.id, "published": False, "detail": str(exc)},
                    )

            await VintedBatchOrchestratorService._emit_job(
                job_id, "browser", "Fermeture du navigateur…", form_step="browser_close"
            )
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
