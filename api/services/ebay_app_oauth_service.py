"""
eBay OAuth 2.0 **Client Credentials** flow (application token).

Used for server-to-server APIs that don't need a user context, such as the
public Browse API (``/buy/browse/v1``). The returned token is cached in-memory
until close to expiry to avoid hammering the token endpoint.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import logging
from typing import Any

import httpx

from config import AppSettings, get_settings

logger = logging.getLogger(__name__)

#: Scope needed for the public Browse API (read-only marketplace search).
BROWSE_API_SCOPE = "https://api.ebay.com/oauth/api_scope"

#: Renew the token slightly before expiry to avoid mid-request invalidation.
_EXPIRY_SKEW_SECONDS = 120

_cached_token: str | None = None
_cached_expires_at: dt.datetime | None = None
_cache_lock = asyncio.Lock()


def _token_url(app: AppSettings) -> str:
    host = "api.sandbox.ebay.com" if app.ebay_use_sandbox else "api.ebay.com"
    return f"https://{host}/identity/v1/oauth2/token"


def _basic_auth_header(app: AppSettings) -> str:
    raw = f"{(app.ebay_client_id or '').strip()}:{(app.ebay_client_secret or '').strip()}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def ebay_app_oauth_configured(app: AppSettings | None = None) -> bool:
    s = app or get_settings()
    return bool((s.ebay_client_id or "").strip() and (s.ebay_client_secret or "").strip())


async def _request_app_token(app: AppSettings) -> dict[str, Any]:
    data = {"grant_type": "client_credentials", "scope": BROWSE_API_SCOPE}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_basic_auth_header(app)}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_token_url(app), data=data, headers=headers)
    if resp.status_code >= 400:
        logger.warning(
            "eBay app token request failed: %s %s",
            resp.status_code,
            resp.text[:500],
        )
        resp.raise_for_status()
    return resp.json()


async def get_app_access_token(*, app: AppSettings | None = None, force_refresh: bool = False) -> str:
    """
    Return a valid application access token for Browse API.

    Caches the token across calls; refreshes a bit before its natural expiry.

    Raises:
        RuntimeError: if client id/secret are not configured in the environment.
        httpx.HTTPStatusError: if eBay rejected the token request.
    """
    global _cached_token, _cached_expires_at  # noqa: PLW0603
    s = app or get_settings()
    if not ebay_app_oauth_configured(s):
        raise RuntimeError(
            "ebay_app_oauth_not_configured: set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in the environment.",
        )
    now = dt.datetime.now(dt.UTC)
    if not force_refresh and _cached_token and _cached_expires_at and _cached_expires_at > now:
        return _cached_token

    async with _cache_lock:
        if not force_refresh and _cached_token and _cached_expires_at and _cached_expires_at > now:
            return _cached_token
        payload = await _request_app_token(s)
        access = str(payload.get("access_token") or "").strip()
        if not access:
            raise RuntimeError("eBay app token response is missing ``access_token``.")
        expires_in = int(payload.get("expires_in") or 7200)
        _cached_token = access
        _cached_expires_at = now + dt.timedelta(seconds=max(60, expires_in - _EXPIRY_SKEW_SECONDS))
        return access


def invalidate_cached_app_token() -> None:
    """Forget the cached token (useful after a 401)."""
    global _cached_token, _cached_expires_at  # noqa: PLW0603
    _cached_token = None
    _cached_expires_at = None
