"""Market price lookup on eBay France (public Browse API)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app_types.ebay_browse import (
    ConditionFilter,
    GradedFilter,
    MarketSearchResponse,
    SortOrder,
)
from config import get_settings
from core.deps import get_current_user
from models.user import User
from services.ebay_app_oauth_service import ebay_app_oauth_configured
from services.ebay_browse_service import DEFAULT_LIMIT, MAX_LIMIT, browse_search
from services.ebay_price_aggregator_service import aggregate_prices, partition_outliers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ebay/market", tags=["ebay-market"])

#: Hardcoded noise-word list appended to every Browse query. These tokens
#: describe **accessories** ("sleeve", "classeur", …) and are unlikely to
#: appear in a user's legitimate sealed-product or card search.
#:
#: Negative tokens are forwarded to eBay as ``-"sleeve"`` so no matching
#: listing is ever returned — this keeps noise out at the source without
#: relying only on statistical outlier filtering.
_DEFAULT_EXCLUDES: tuple[str, ...] = (
    "sleeve",
    "sleeves",
    "protège-cartes",
    "protege-cartes",
    "protège carte",
    "protege carte",
    "étui",
    "etui",
    "classeur",
    "portfolio",
    "binder",
    "album",
    "intercalaire",
    "divider",
    "toploader",
    "top loader",
    "penny sleeve",
    "playmat",
    "tapis de jeu",
    "boîte rangement",
    "boite rangement",
    "storage box",
    "pin's",
    "pin ",
    "badge",
    "sticker",
    "autocollant",
    "poster",
    "affiche",
    "plush",
    "peluche",
    "figurine",
)


@router.get("/search", response_model=None)
async def search_market(
    _user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=2, max_length=256)],
    period_days: Annotated[int, Query(ge=0, le=365)] = 30,
    condition: Annotated[ConditionFilter, Query()] = "new",
    graded: Annotated[GradedFilter, Query()] = "all",
    sort: Annotated[SortOrder, Query()] = "relevance",
    fr_only: Annotated[bool, Query()] = False,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> MarketSearchResponse:
    """
    Search **active** eBay France listings matching ``q`` and return aggregated stats.

    Authentication uses the OAuth Client Credentials flow (application token):
    no user eBay connection required.

    Noise-word exclusions (sleeves, étuis, classeurs, …) and statistical
    outlier filtering are applied **server-side** by default — both are
    relative to the median price, so legitimate low-value cards remain visible.
    """
    app = get_settings()
    if not ebay_app_oauth_configured(app):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eBay app credentials not configured on the server (EBAY_CLIENT_ID, EBAY_CLIENT_SECRET).",
        )
    exclude_list = list(_DEFAULT_EXCLUDES)
    try:
        raw_listings, total, warnings, effective_q = await browse_search(
            q=q.strip(),
            period_days=period_days,
            condition=condition,
            graded=graded,
            sort=sort,
            min_price=min_price,
            max_price=max_price,
            fr_only=fr_only,
            limit=limit,
            exclude_keywords=exclude_list,
            app=app,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # httpx raises HTTPStatusError etc.
        logger.warning("eBay Browse search failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"eBay Browse API error: {exc}",
        ) from exc

    kept, outliers = partition_outliers(raw_listings)
    stats = aggregate_prices(kept)
    return {
        "query": q.strip(),
        "effective_query": effective_q,
        "marketplace_id": "EBAY_FR",
        "period_days": period_days,
        "filters_applied": {
            "condition": condition,
            "graded": graded,
            "sort": sort,
            "fr_only": fr_only,
            "min_price": min_price,
            "max_price": max_price,
            "limit": limit,
            "exclude_keywords": exclude_list,
            "exclude_outliers": True,
        },
        "stats": stats,
        "items": kept,
        "outliers": outliers,
        "outliers_excluded": len(outliers),
        "total_matches": total,
        "warnings": warnings,
    }
