"""
Background worker for the eBay « top sold » scrape.

The synchronous scrape can take 5-15 s (2-3 paginated GETs against eBay.fr,
plus a polite pause between pages). This module fronts that work with an
in-memory job queue: callers submit a job, get a ``job_id`` back, then poll
``GET /ebay/market/sold-top/{job_id}`` until ``status == "completed"``.

A short TTL cache keyed on ``(q, window_hours, pages, top_limit, min_count)``
short-circuits identical submissions while the data is fresh, drastically
reducing the load eBay sees from the VPS IP when several users search for
the same popular keywords (« carte pokemon », « charizard », …).

State is process-local (a plain ``dict``). For a single Uvicorn / Gunicorn
worker this is fine; if we ever scale to N workers we'll need to either pin
job ids to a worker (sticky session) or move state to Redis.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from config import AppSettings
from services.ebay_sold_scrape_service import scrape_sold_listings
from services.ebay_sold_top_service import aggregate_top_sold

logger = logging.getLogger(__name__)


JobStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class EbaySoldTopJob:
    """A single « top sold » scrape, with progress + result fields."""

    job_id: str
    user_id: int
    q: str
    window_hours: float
    pages: int
    scrape_limit: int
    top_limit: int
    min_count: int
    status: JobStatus = "pending"
    pages_done: int = 0
    total_observed: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    def to_public(self) -> dict[str, Any]:
        """Shape returned to the API client (excludes internal-only fields)."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "query": self.q,
            "window_hours": self.window_hours,
            "pages_requested": self.pages,
            "pages_done": self.pages_done,
            "total_observed": self.total_observed,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


#: Job TTL after last update — long enough for a slow client to finish polling.
_JOB_TTL_SECONDS = 600.0
#: Cache TTL on the result body. Tuned to absorb traffic spikes on popular
#: queries (« carte pokemon », « charizard ») without hammering eBay.
_RESULT_CACHE_TTL_SECONDS = 15 * 60.0

_JOBS: dict[str, EbaySoldTopJob] = {}
_RESULT_CACHE: dict[tuple[str, float, int, int, int], tuple[float, dict[str, Any]]] = {}


def _gc_jobs(now: float | None = None) -> None:
    """Drop jobs whose last update is older than the TTL."""
    n = now if now is not None else time.time()
    stale = [jid for jid, job in _JOBS.items() if n - job.updated_at > _JOB_TTL_SECONDS]
    for jid in stale:
        _JOBS.pop(jid, None)


def _gc_cache(now: float | None = None) -> None:
    """Drop expired entries from the result cache."""
    n = now if now is not None else time.time()
    stale = [k for k, (ts, _) in _RESULT_CACHE.items() if n - ts > _RESULT_CACHE_TTL_SECONDS]
    for k in stale:
        _RESULT_CACHE.pop(k, None)


def _cache_key(
    *, q: str, window_hours: float, pages: int, top_limit: int, min_count: int,
) -> tuple[str, float, int, int, int]:
    return (q.strip().lower(), float(window_hours), int(pages), int(top_limit), int(min_count))


def _peek_cached_result(
    *, q: str, window_hours: float, pages: int, top_limit: int, min_count: int,
) -> dict[str, Any] | None:
    """Return a cached top-sold result body if still fresh, else ``None``."""
    _gc_cache()
    key = _cache_key(
        q=q, window_hours=window_hours, pages=pages,
        top_limit=top_limit, min_count=min_count,
    )
    entry = _RESULT_CACHE.get(key)
    if entry is None:
        return None
    ts, body = entry
    if time.time() - ts > _RESULT_CACHE_TTL_SECONDS:
        _RESULT_CACHE.pop(key, None)
        return None
    return body


def _store_cached_result(
    *,
    q: str,
    window_hours: float,
    pages: int,
    top_limit: int,
    min_count: int,
    body: dict[str, Any],
) -> None:
    key = _cache_key(
        q=q, window_hours=window_hours, pages=pages,
        top_limit=top_limit, min_count=min_count,
    )
    _RESULT_CACHE[key] = (time.time(), body)


async def _run_job(job: EbaySoldTopJob, app: AppSettings) -> None:
    """Execute the scrape + aggregation for ``job``, mutating it in place."""
    job.status = "running"
    job.started_at = time.time()
    job.updated_at = job.started_at

    async def _on_page_done(page_num: int, total_observed: int) -> None:
        job.pages_done = page_num
        job.total_observed = total_observed
        job.updated_at = time.time()

    try:
        items, err = await scrape_sold_listings(
            q=job.q,
            window_hours=job.window_hours,
            limit=job.scrape_limit,
            pages=job.pages,
            app=app,
            on_page_done=_on_page_done,
        )
    except Exception as exc:
        logger.exception("eBay sold-top job %s crashed during scrape", job.job_id)
        job.status = "failed"
        job.error = f"Erreur interne pendant le scrape : {exc}"
        job.completed_at = time.time()
        job.updated_at = job.completed_at
        return

    grouped = aggregate_top_sold(items, min_count=job.min_count, limit_per_category=job.top_limit)

    # Return the full window-filtered listings (already capped at scrape_limit
    # by ``_filter_window``). The frontend renders these as the « Liste des
    # ventes » view, so the user gets list + tops from a single scrape — no
    # second eBay roundtrip when switching tabs.
    body = {
        "query": job.q,
        "window_hours": job.window_hours,
        "pages_requested": job.pages,
        "total_observed": len(items),
        "items": items,
        "cards": grouped["cards"],
        "graded": grouped["graded"],
        "sealed": grouped["sealed"],
        "groups_count": {
            "cards": len(grouped["cards"]),
            "graded": len(grouped["graded"]),
            "sealed": len(grouped["sealed"]),
        },
        "source": "ebay_html_scrape_aggregated",
    }
    job.result = body
    job.error = err
    job.total_observed = len(items)
    if err is not None and not items:
        job.status = "failed"
    else:
        job.status = "completed"
        # Only cache full successes — partial scrapes (with err set) shouldn't
        # be served to other users until eBay un-blocks us.
        if err is None:
            _store_cached_result(
                q=job.q,
                window_hours=job.window_hours,
                pages=job.pages,
                top_limit=job.top_limit,
                min_count=job.min_count,
                body=body,
            )
    job.completed_at = time.time()
    job.updated_at = job.completed_at


def submit_job(
    *,
    user_id: int,
    q: str,
    window_hours: float,
    pages: int,
    scrape_limit: int,
    top_limit: int,
    min_count: int,
    app: AppSettings,
) -> EbaySoldTopJob:
    """
    Create a job and schedule its execution on the running event loop.

    If a fresh cached result exists for the same parameters, the returned
    job is created already in ``completed`` state with the cached body —
    the caller can short-circuit polling and surface it immediately.
    """
    _gc_jobs()

    job = EbaySoldTopJob(
        job_id=secrets.token_urlsafe(12),
        user_id=user_id,
        q=q.strip(),
        window_hours=window_hours,
        pages=pages,
        scrape_limit=scrape_limit,
        top_limit=top_limit,
        min_count=min_count,
    )

    cached = _peek_cached_result(
        q=q, window_hours=window_hours, pages=pages,
        top_limit=top_limit, min_count=min_count,
    )
    if cached is not None:
        now = time.time()
        job.status = "completed"
        job.result = cached
        job.pages_done = pages
        job.total_observed = int(cached.get("total_observed") or 0)
        job.started_at = now
        job.completed_at = now
        job.updated_at = now
        _JOBS[job.job_id] = job
        return job

    _JOBS[job.job_id] = job
    asyncio.create_task(_run_job(job, app))
    return job


def get_job(job_id: str) -> EbaySoldTopJob | None:
    """Return the job by id, or ``None`` if expired / unknown."""
    _gc_jobs()
    return _JOBS.get(job_id)


def peek_items_sample(*, q: str, window_hours: float) -> list[dict[str, Any]] | None:
    """
    Look up any fresh cached top result matching ``(q, window_hours)`` and
    return its ``items`` payload, regardless of which ``pages`` /
    ``top_limit`` / ``min_count`` was used.

    Kept for the legacy ``/sold-scrape`` route, which is no longer driven by
    the frontend but still reachable; once that route is removed entirely
    this helper can go too.
    """
    _gc_cache()
    target_q = q.strip().lower()
    target_window = float(window_hours)
    best_ts = 0.0
    best_sample: list[dict[str, Any]] | None = None
    for (cq, cw, _pages, _top, _min), (ts, body) in _RESULT_CACHE.items():
        if cq != target_q or cw != target_window:
            continue
        if ts <= best_ts:
            continue
        sample = body.get("items")
        if not isinstance(sample, list) or not sample:
            continue
        best_ts = ts
        best_sample = sample
    return best_sample
