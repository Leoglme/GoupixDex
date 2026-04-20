"""Run Vinted then eBay after article creation — shared SSE session."""

from __future__ import annotations

import logging
from typing import Any

from services.ebay_background_service import EbayBackgroundService, _ebay_sse_payload
from services.vinted_background_service import VintedBackgroundService
from services.vinted_progress_session_service import VintedProgressSessionService as progress_hub

logger = logging.getLogger(__name__)


class CombinedMarketplaceService:
    """Vinted then eBay in the same ``/articles/{id}/listing-progress`` session."""

    @staticmethod
    async def run_vinted_then_ebay(article_id: int, user_id: int, image_sources: list[str]) -> None:
        progress_hub.register(article_id)
        v_result: dict[str, Any] = {"published": False, "detail": "not_started"}
        try:
            v_result = await VintedBackgroundService.run_vinted_publish_job(
                article_id,
                user_id,
                image_sources,
                finish_session=False,
            )
            await progress_hub.emit(
                article_id,
                {
                    "type": "log",
                    "step": "chain",
                    "message": "Vinted step finished. Starting eBay publish…",
                },
            )
            e_result = await EbayBackgroundService.run_ebay_publish_job(
                article_id,
                user_id,
                finish_session=False,
            )
            await progress_hub.finish(
                article_id,
                {"vinted": v_result, "ebay": _ebay_sse_payload(e_result)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("combined marketplace job article_id=%s", article_id)
            await progress_hub.finish(
                article_id,
                {
                    "vinted": v_result,
                    "ebay": _ebay_sse_payload({"ok": False, "detail": str(exc)}),
                },
            )
        finally:
            progress_hub.cleanup_later(article_id)
