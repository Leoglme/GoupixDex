"""Orchestrate a Cardmarket search run on the desktop worker (nodriver + remote API)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from services.cardmarket_product_types import CardmarketCardResult
from services.cardmarket_scraper_service import scrape_urls_to_card_results
from services.cardmarket_seller_aggregator_service import build_run_payload

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def run_cardmarket_search_job(
    search_id: int,
    token: str,
    remote_base: str,
    emit: EmitFn,
) -> None:
    hdrs = _headers(token)
    cards_so_far: list[CardmarketCardResult] = []
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(f"{remote_base}/cardmarket-searches/{search_id}", headers=hdrs)
            r.raise_for_status()
            data = r.json()
        urls_raw = data.get("urls") or []
        urls = [str(u.get("url") or "").strip() for u in sorted(urls_raw, key=lambda x: int(x.get("sort_index") or 0))]
        urls = [u for u in urls if u]
        if not urls:
            await emit({"type": "error", "message": "Aucune URL dans cette recherche."})
            return

        await emit({"type": "log", "message": f"Démarrage — {len(urls)} carte(s) à analyser."})

        async def on_progress(ev: dict[str, Any]) -> None:
            await emit(ev)

        async def on_card_done(cards: list[CardmarketCardResult]) -> None:
            cards_so_far[:] = list(cards)
            try:
                partial = build_run_payload(cards, min_cards_for_lists=2)
            except Exception as build_exc:  # noqa: BLE001
                logger.debug("build_run_payload (partial) failed: %s", build_exc)
                return
            await emit(
                {
                    "type": "partial",
                    "current": len(cards),
                    "total": len(urls),
                    "payload": partial,
                }
            )

        cards = await scrape_urls_to_card_results(
            urls,
            progress=on_progress,
            on_card_done=on_card_done,
        )
        cards_so_far[:] = list(cards)
        payload = build_run_payload(cards, min_cards_for_lists=2)

        await emit({"type": "log", "message": "Analyse terminée — enregistrement du résultat…"})

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            pr = await client.put(
                f"{remote_base}/cardmarket-searches/{search_id}/result",
                headers={**hdrs, "Content-Type": "application/json"},
                json={"payload": payload},
            )
            pr.raise_for_status()

        await emit(
            {
                "type": "done",
                "summary": {
                    "total_cards": len(urls),
                    "scanned_cards": len(cards),
                    "max_coverage": (payload.get("meta") or {}).get("max_coverage"),
                },
            }
        )
    except asyncio.CancelledError:
        logger.info("Cardmarket job cancelled search_id=%s", search_id)
        if cards_so_far:
            try:
                payload = build_run_payload(cards_so_far, min_cards_for_lists=2)
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    await client.put(
                        f"{remote_base}/cardmarket-searches/{search_id}/result",
                        headers={**hdrs, "Content-Type": "application/json"},
                        json={"payload": payload},
                    )
            except (asyncio.CancelledError, Exception) as save_exc:  # noqa: BLE001
                logger.debug("Partial save on cancel failed: %s", save_exc)
        raise
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        logger.exception("Cardmarket job HTTP error search_id=%s", search_id)
        await emit({"type": "error", "message": f"API {exc.response.status_code if exc.response else '?'}: {detail}"})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Cardmarket job failed search_id=%s", search_id)
        await emit({"type": "error", "message": str(exc) or "Erreur inconnue."})
