"""Dashboard statistics."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User
from services.stats_service import compute_dashboard_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    include_market: bool = Query(
        False,
        description="If true, sums Cardmarket EUR per article via PokéWallet (slower).",
    ),
) -> dict[str, Any]:
    return compute_dashboard_stats(db, user.id, include_market=include_market)
