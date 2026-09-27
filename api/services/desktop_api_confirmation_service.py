"""Confirmations the desktop workers send to the GoupixDex API after a real marketplace action."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Pauses between attempts: during a redeploy the API answers 502 or refuses connections for about a minute.
_RETRY_DELAYS_S: tuple[float, ...] = (3.0, 6.0, 12.0, 24.0, 48.0)


async def post_confirmation_to_api(url: str, headers: dict[str, str], payload: dict[str, Any]) -> None:
    """
    POST a confirmation to the API, retried while it answers 5xx or cannot be reached.

    Raises:
        httpx.HTTPError: The API refused the call (4xx) or was still unavailable after the last attempt.
    """
    for retry_delay_s in (*_RETRY_DELAYS_S, None):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TransportError as exc:
            if retry_delay_s is None:
                raise
            logger.warning("POST %s unreachable (%s), retrying in %.0fs", url, exc, retry_delay_s)
        else:
            if response.status_code < 500 or retry_delay_s is None:
                response.raise_for_status()
                return
            logger.warning("POST %s answered %s, retrying in %.0fs", url, response.status_code, retry_delay_s)
        await asyncio.sleep(retry_delay_s)
