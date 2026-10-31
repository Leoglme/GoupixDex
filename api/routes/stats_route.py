"""Dashboard statistics."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User
from services.stats_service import compute_dashboard_stats, list_sold_sales

router = APIRouter(prefix="/stats", tags=["stats"])


def _parse_iso(value: str | None) -> dt.datetime | None:
    if value is None:
        return None
    try:
        # ``fromisoformat`` accepts both date and datetime strings (Py 3.11+).
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ISO date: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def _parse_range_end(value: str | None) -> dt.datetime | None:
    """Range end: a bare date (``2026-10-31``) covers that whole day, a datetime is kept as is."""
    parsed = _parse_iso(value)
    is_bare_date = value is not None and len(value.strip()) == len("YYYY-MM-DD")
    if parsed is None or not is_bare_date:
        return parsed
    return parsed + dt.timedelta(days=1) - dt.timedelta(microseconds=1)


@router.get("/dashboard")
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    start: str | None = Query(None, description="Range start (ISO date or datetime)."),
    end: str | None = Query(None, description="Range end (ISO date or datetime)."),
    period: Literal["daily", "weekly", "monthly"] | None = Query(
        None,
        description="Bucket size for the revenue timeline; omitted = picked from the range length.",
    ),
    timezone: str | None = Query(
        None,
        max_length=64,
        description="Browser IANA time zone (e.g. Europe/Paris) used to cut the timeline into local days and months.",
    ),
) -> dict[str, Any]:
    return compute_dashboard_stats(
        db,
        user.id,
        range_start=_parse_iso(start),
        range_end=_parse_range_end(end),
        period=period,
        timezone=timezone,
    )


@router.get("/sold-sales")
def sold_sales(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    sale_source: Literal["vinted", "ebay", "leboncoin"] | None = Query(
        None,
        description="Filter by channel; omit for all sold articles.",
    ),
) -> dict[str, Any]:
    """All sold articles (Vinted, eBay and/or Leboncoin), same row shape as dashboard ``recent_sales``."""
    return list_sold_sales(db, user.id, sale_source=sale_source)
