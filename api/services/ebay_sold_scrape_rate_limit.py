"""In-memory per-user rate limit for eBay « vendus » HTML scrape (reduces bot flags on eBay)."""

from __future__ import annotations

import asyncio
import time

_lock = asyncio.Lock()
_last: dict[int, float] = {}


async def acquire_sold_scrape_slot(user_id: int, min_interval_sec: float) -> int:
    """
    Enforce at most one allowed request per ``min_interval_sec`` per user (monotonic clock).

    :returns: ``0`` if the caller may proceed; else whole seconds to wait (for ``Retry-After``).
    """
    if min_interval_sec <= 0:
        return 0
    now = time.monotonic()
    async with _lock:
        last = _last.get(user_id)
        if last is not None and (now - last) < min_interval_sec:
            wait = min_interval_sec - (now - last)
            return max(1, int(wait + 0.999))
        _last[user_id] = now
        return 0
