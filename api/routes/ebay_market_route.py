"""Market price lookup on eBay France (public Browse API)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

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
from services.ebay_sold_scrape_rate_limit import acquire_sold_scrape_slot
from services.ebay_sold_scrape_service import ebay_fr_sold_search_url, scrape_sold_listings
from services.ebay_sold_top_service import aggregate_top_sold

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
    items_response = kept
    outliers_response: list = outliers
    if stats["count"] == 0 and raw_listings:
        fb_stats = aggregate_prices(raw_listings)
        if fb_stats["count"] > 0:
            stats = fb_stats
            items_response = raw_listings
            outliers_response = []
            warnings = list(warnings)
            warnings.append(
                "Les écarts de prix sont très importants : statistiques calculées sur toutes les annonces "
                "retournées par eBay (filtre anti-prix aberrants désactivé pour cet aperçu)."
            )

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
        "items": items_response,
        "outliers": outliers_response,
        "outliers_excluded": len(outliers_response),
        "total_matches": total,
        "warnings": warnings,
    }


@router.get("/sold-scrape", response_model=None)
async def sold_scrape_html(
    user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=2, max_length=256)],
    window_hours: Annotated[float, Query(ge=1, le=720)] = 168,
    limit: Annotated[int, Query(ge=1, le=60)] = 50,
) -> dict[str, Any]:
    """
    **Completed listings** (sold) via **public eBay HTML search** — no Marketplace Insights OAuth.

    May fail with bot protection (403); optional ``EBAY_SOLD_SCRAPE_PROXY`` in server env.
    Rate-limited per user (default: one call every ``EBAY_SOLD_SCRAPE_MIN_INTERVAL_SECONDS``).
    Window goes up to ``720`` hours (30 days).
    """
    app = get_settings()
    retry_after = await acquire_sold_scrape_slot(user.id, app.ebay_sold_scrape_min_interval_seconds)
    if retry_after > 0:
        iv = app.ebay_sold_scrape_min_interval_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite : une recherche « vendus eBay » toutes les {iv:g} s "
                f"(réessayez dans {retry_after} s)."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    items, err = await scrape_sold_listings(q=q.strip(), window_hours=window_hours, limit=limit, app=app)
    return {
        "query": q.strip(),
        "window_hours": window_hours,
        "items": items,
        "error": err,
        "ebay_sold_search_url": ebay_fr_sold_search_url(q=q.strip(), page_size=min(60, max(limit, 10))),
        "source": "ebay_html_scrape",
    }


@router.get("/sold-top", response_model=None)
async def sold_top(
    user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=2, max_length=256)],
    window_hours: Annotated[float, Query(ge=1, le=720)] = 168,
    pages: Annotated[int, Query(ge=1, le=5)] = 2,
    scrape_limit: Annotated[int, Query(ge=10, le=300)] = 180,
    top_limit: Annotated[int, Query(ge=1, le=100)] = 30,
    min_count: Annotated[int, Query(ge=1, le=20)] = 1,
) -> dict[str, Any]:
    """
    Top des cartes les plus vendues dans la fenêtre, agrégées depuis le
    scrape HTML public eBay.fr.

    Le résultat est trié par ``count`` (puis valeur cumulée). Fenêtre par
    défaut : 7 jours (168 h) ; valeurs autorisées de 1 h à 720 h (30 j).
    ``pages`` (1-5) déclenche autant de requêtes paginées vers eBay (60
    annonces / page), avec déduplication par ``item_id``. Même rate-limit
    utilisateur que ``/sold-scrape`` — un appel utilisateur peut donc
    générer plusieurs requêtes vers eBay.
    """
    app = get_settings()
    retry_after = await acquire_sold_scrape_slot(user.id, app.ebay_sold_scrape_min_interval_seconds)
    if retry_after > 0:
        iv = app.ebay_sold_scrape_min_interval_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite : une recherche « vendus eBay » toutes les {iv:g} s "
                f"(réessayez dans {retry_after} s)."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    items, err = await scrape_sold_listings(
        q=q.strip(),
        window_hours=window_hours,
        limit=scrape_limit,
        pages=pages,
        app=app,
    )
    grouped = aggregate_top_sold(items, min_count=min_count, limit_per_category=top_limit)
    return {
        "query": q.strip(),
        "window_hours": window_hours,
        "pages_requested": pages,
        "total_observed": len(items),
        "cards": grouped["cards"],
        "graded": grouped["graded"],
        "sealed": grouped["sealed"],
        "groups_count": {
            "cards": len(grouped["cards"]),
            "graded": len(grouped["graded"]),
            "sealed": len(grouped["sealed"]),
        },
        "error": err,
        "ebay_sold_search_url": ebay_fr_sold_search_url(q=q.strip(), page_size=60),
        "source": "ebay_html_scrape_aggregated",
    }
