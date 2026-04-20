"""
Wrapper around the eBay **Browse API** ``item_summary/search`` endpoint.

Active-listings search only (Marketplace Insights is required for sold items).
Results are filtered for the French marketplace by default and normalized into
:class:`MarketListing` objects ready for the GoupixDex frontend.
"""

from __future__ import annotations

import logging
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app_types.ebay_browse import (
    ConditionFilter,
    EbayBrowseResponse,
    EbayItemSummary,
    GradedFilter,
    MarketGradedInfo,
    MarketListing,
    SortOrder,
)
from config import AppSettings, get_settings
from services.ebay_app_oauth_service import (
    get_app_access_token,
    invalidate_cached_app_token,
)

logger = logging.getLogger(__name__)

BROWSE_API_PATH = "/buy/browse/v1/item_summary/search"

#: eBay limits ``limit`` to [1, 200] for Browse API; pick a reasonable default.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

_GRADED_KEYWORDS: dict[GradedFilter, tuple[str, ...]] = {
    "psa": ("PSA",),
    "cgc": ("CGC",),
    "bgs": ("BGS", "Beckett"),
}

#: Map our sort keys to eBay Browse API ``sort`` values.
_SORT_MAP: dict[SortOrder, str | None] = {
    "price_asc": "price",
    "price_desc": "-price",
    "newly_listed": "newlyListed",
    "relevance": None,  # Browse API default = best match.
}


def _api_host(app: AppSettings) -> str:
    return "https://api.sandbox.ebay.com" if app.ebay_use_sandbox else "https://api.ebay.com"


def _pick_image_url(item: EbayItemSummary) -> str | None:
    image = item.get("image") or {}
    url = str(image.get("imageUrl") or "").strip()
    if url:
        return url
    for key in ("thumbnailImages", "additionalImages"):
        rows = item.get(key) or []
        for r in rows:
            candidate = str((r or {}).get("imageUrl") or "").strip()
            if candidate:
                return candidate
    return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n <= 0 or n != n:  # ``n != n`` catches NaN
        return None
    return n


def _match_graded(title: str, graded: GradedFilter) -> MarketGradedInfo | None:
    """Extract grading info by scanning the title (Browse summaries don't expose item aspects)."""
    if graded == "all":
        keywords = ("PSA", "CGC", "BGS", "Beckett")
    elif graded == "raw":
        return None
    else:
        keywords = _GRADED_KEYWORDS[graded]
    upper_title = title.upper()
    for kw in keywords:
        if kw.upper() in upper_title:
            return {"grader": kw.upper().replace("BECKETT", "BGS"), "grade": _extract_grade(upper_title, kw)}
    return None


def _extract_grade(upper_title: str, grader_kw: str) -> str:
    """Naive grade extractor: find digit/float right after ``grader_kw``."""
    idx = upper_title.find(grader_kw.upper())
    if idx == -1:
        return ""
    chunk = upper_title[idx + len(grader_kw) : idx + len(grader_kw) + 8]
    digits: list[str] = []
    has_digit = False
    for ch in chunk:
        if ch.isdigit():
            digits.append(ch)
            has_digit = True
        elif has_digit and ch in (".", ","):
            digits.append(".")
        elif has_digit:
            break
    return "".join(digits).strip(".")


def _is_raw_listing(title: str) -> bool:
    upper = title.upper()
    return all(kw not in upper for kw in ("PSA", "CGC", "BGS", "BECKETT"))


def _normalize_item(item: EbayItemSummary) -> MarketListing | None:
    price_block = item.get("price") or {}
    price_value = _safe_float(price_block.get("value"))
    if price_value is None:
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    location = item.get("itemLocation") or {}
    seller = item.get("seller") or {}
    listing: MarketListing = {
        "item_id": str(item.get("itemId") or "").strip(),
        "title": title,
        "price_eur": round(price_value, 2),
        "currency": str(price_block.get("currency") or "EUR"),
        "condition": str(item.get("condition") or "").strip(),
        "seller_username": str(seller.get("username") or "").strip(),
        "seller_country": str(location.get("country") or "").strip(),
        "seller_feedback_score": (
            int(seller["feedbackScore"]) if isinstance(seller.get("feedbackScore"), int) else None
        ),
        "image_url": _pick_image_url(item),
        "listing_url": str(item.get("itemWebUrl") or "").strip(),
        "buying_options": list(item.get("buyingOptions") or []),
        "graded": None,
    }
    graded_info = _match_graded(title, "all")
    listing["graded"] = graded_info
    return listing


def _build_filter_clause(
    *,
    condition: ConditionFilter,
    min_price: float | None,
    max_price: float | None,
    period_days: int,
) -> str:
    """Build the ``filter`` query-string for Browse API (``,`` joined clauses)."""
    clauses: list[str] = []
    if condition == "new":
        clauses.append("conditions:{NEW}")
    elif condition == "used":
        clauses.append("conditions:{USED}")

    if min_price is not None and max_price is not None:
        clauses.append(f"price:[{min_price}..{max_price}],priceCurrency:EUR")
    elif min_price is not None:
        clauses.append(f"price:[{min_price}..],priceCurrency:EUR")
    elif max_price is not None:
        clauses.append(f"price:[..{max_price}],priceCurrency:EUR")

    if period_days > 0:
        import datetime as dt

        start = (dt.datetime.now(dt.UTC) - dt.timedelta(days=period_days)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z",
        )
        clauses.append(f"itemStartDate:[{start}]")
    return ",".join(clauses)


def _build_query_string(
    *,
    q: str,
    limit: int,
    sort: SortOrder,
    filter_clause: str,
    fr_only: bool,
) -> str:
    params: list[tuple[str, str]] = [
        ("q", q),
        ("limit", str(min(max(limit, 1), MAX_LIMIT))),
    ]
    sort_value = _SORT_MAP.get(sort)
    if sort_value:
        params.append(("sort", sort_value))
    if filter_clause:
        params.append(("filter", filter_clause))
    if fr_only:
        params.append(("filter", "itemLocationCountry:FR"))
    return urlencode(params, doseq=True)


def _build_effective_query(q: str, exclude_keywords: list[str] | None) -> str:
    """
    Combine the free-text query with keyword exclusions (eBay ``-word`` syntax).

    eBay Browse API honors negative tokens directly inside ``q`` (e.g.
    ``Charizard -sleeve -étui``). We strip duplicates and tokens already
    present/excluded in ``q`` to keep the request short.
    """
    base = q.strip()
    if not exclude_keywords:
        return base
    existing_tokens = {tok.lstrip("-").lower() for tok in base.split() if tok.strip()}
    extras: list[str] = []
    seen: set[str] = set()
    for kw in exclude_keywords:
        token = kw.strip().lstrip("-").lower()
        if not token or token in seen or token in existing_tokens:
            continue
        seen.add(token)
        safe = token.replace('"', "").strip()
        if " " in safe:
            extras.append(f'-"{safe}"')
        else:
            extras.append(f"-{safe}")
    if not extras:
        return base
    return f"{base} {' '.join(extras)}".strip()


async def browse_search(
    *,
    q: str,
    period_days: int = 30,
    condition: ConditionFilter = "new",
    graded: GradedFilter = "all",
    sort: SortOrder = "relevance",
    min_price: float | None = None,
    max_price: float | None = None,
    fr_only: bool = False,
    limit: int = DEFAULT_LIMIT,
    exclude_keywords: list[str] | None = None,
    app: AppSettings | None = None,
) -> tuple[list[MarketListing], int, list[str], str]:
    """
    Search eBay France active listings and return normalized market listings.

    Args:
        q: Free-text query (the title field).
        period_days: Only return items listed in the last N days (0 disables the filter).
        condition: Restrict to ``new`` / ``used`` or ``all``.
        graded: Post-filter the results on grading keywords (``raw`` = non-graded only).
        sort: Sort order requested to eBay.
        min_price: Lower EUR bound (inclusive).
        max_price: Upper EUR bound (inclusive).
        fr_only: When ``True``, only return listings located in France.
        limit: Upper bound on returned items (capped at 200).
        exclude_keywords: Tokens to exclude from the search (appended as ``-token``).
        app: Optional settings override (testing).

    Returns:
        Tuple ``(listings, total_matches, warnings, effective_query)``. ``warnings``
        reflects the non-blocking warnings the eBay API may emit (e.g. taxonomy
        suggestions). ``effective_query`` is the query string actually sent to eBay,
        including any negative tokens.
    """
    s = app or get_settings()
    token = await get_app_access_token(app=s)
    effective_q = _build_effective_query(q, exclude_keywords)
    filter_clause = _build_filter_clause(
        condition=condition,
        min_price=min_price,
        max_price=max_price,
        period_days=period_days,
    )
    qs = _build_query_string(
        q=effective_q,
        limit=limit,
        sort=sort,
        filter_clause=filter_clause,
        fr_only=fr_only,
    )
    url = f"{_api_host(s)}{BROWSE_API_PATH}?{qs}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR",
        "Accept-Language": "fr-FR",
        "Accept": "application/json",
    }
    try:
        payload = await _fetch(url, headers)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            # Token may have expired between the cache and the call; force refresh once.
            invalidate_cached_app_token()
            token = await get_app_access_token(app=s, force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            payload = await _fetch(url, headers)
        else:
            raise

    payload_t = cast(EbayBrowseResponse, payload)
    summaries = payload_t.get("itemSummaries") or []
    total = int(payload_t.get("total") or 0)
    warnings_raw = payload_t.get("warnings") or []
    warnings: list[str] = []
    for w in warnings_raw:
        msg = str((w or {}).get("message") or "").strip()
        if msg:
            warnings.append(msg)

    listings: list[MarketListing] = []
    for raw in summaries:
        norm = _normalize_item(raw)
        if norm is None:
            continue
        if graded == "raw":
            if norm.get("graded"):
                continue
            if not _is_raw_listing(norm["title"]):
                continue
        elif graded != "all":
            info = norm.get("graded")
            if not info or info["grader"] != graded.upper().replace("BECKETT", "BGS"):
                continue
        listings.append(norm)
    return listings, total, warnings, effective_q


async def _fetch(url: str, headers: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay Browse API error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
    return resp.json()
