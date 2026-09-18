"""HTTP client for the PokéWallet Pokémon card API (https://api.pokewallet.io)."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from typing import Any, cast
from urllib.parse import quote, urlencode

import httpx

from config import get_settings
from app_types.pokewallet import (
    PokeWalletCard,
    PokeWalletGetCardOptions,
    PokeWalletSearchOptions,
    PokeWalletSearchResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.pokewallet.io"
ENV_API_KEY = "POKE_WALLET_API_KEY"
DEFAULT_USER_AGENT = "GoupixDex/1.0 (+https://goupixdex.dibodev.fr)"
SEARCH_LIMIT_MAX = 100
SEARCH_LIMIT_MIN = 1
SEARCH_PAGE_MIN = 1

#: The API key runs on the free plan (100 req/hour, 1000 req/day — see the
#: ``X-RateLimit-*`` response headers). A cash-register scan session fires 1–4
#: searches per card, so the same lookups repeat a lot: cache every successful
#: response for a while (Cardmarket reference prices only move daily).
_CACHE_TTL_SEC = 30 * 60.0
_CACHE_MAX_ENTRIES = 512

#: Transient statuses worth retrying (rate limit + upstream hiccups).
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
_RETRY_DELAYS_SEC = (2.0, 5.0)

#: Log a warning when the remaining quota gets this low.
_LOW_QUOTA_HOUR_WARN = 10
_LOW_QUOTA_DAY_WARN = 50


class _ResponseCache:
    """Thread-safe TTL cache of parsed response bodies, keyed by request path."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > _CACHE_TTL_SEC:
                self._entries.pop(key, None)
                return None
        # Deep copy: callers may enrich/mutate the payload in place.
        return copy.deepcopy(value)

    def store(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._entries) >= _CACHE_MAX_ENTRIES:
                # Drop the oldest half — simple and rare enough at this size.
                oldest = sorted(self._entries.items(), key=lambda kv: kv[1][0])
                for stale_key, _ in oldest[: _CACHE_MAX_ENTRIES // 2]:
                    self._entries.pop(stale_key, None)
            self._entries[key] = (time.time(), copy.deepcopy(value))


_RESPONSE_CACHE = _ResponseCache()


def _warn_when_quota_low(response: httpx.Response) -> None:
    """Surface the free-plan quota in the logs before lookups start failing."""
    try:
        remaining_hour = int(response.headers.get("X-RateLimit-Remaining-Hour", ""))
    except ValueError:
        remaining_hour = -1
    try:
        remaining_day = int(response.headers.get("X-RateLimit-Remaining-Day", ""))
    except ValueError:
        remaining_day = -1
    if 0 <= remaining_hour <= _LOW_QUOTA_HOUR_WARN or 0 <= remaining_day <= _LOW_QUOTA_DAY_WARN:
        logger.warning(
            "PokeWallet quota low: %s left this hour, %s left today (free plan).",
            remaining_hour if remaining_hour >= 0 else "?",
            remaining_day if remaining_day >= 0 else "?",
        )


class PokeWalletClientService:
    """
    HTTP service for the `PokéWallet <https://api.pokewallet.io>`_ Pokémon card API.
    Loads ``POKE_WALLET_API_KEY`` from the environment (e.g. via ``.env`` and ``python-dotenv``)
    unless an explicit key is passed.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        """
        Args:
            api_key: Optional API key (required unless ``POKE_WALLET_PROXY_SECRET`` is set:
                the key may then live only on the proxy).
            base_url: Base URL; if omitted, uses ``poke_wallet_base_url`` from settings.

        Raises:
            ValueError: When no API key is available and proxy secret is not configured.
        """
        settings = get_settings()
        self._base_url = (base_url if base_url is not None else settings.poke_wallet_base_url).rstrip(
            "/"
        )
        self._proxy_secret = (settings.poke_wallet_proxy_secret or "").strip()
        self._user_agent = (settings.poke_wallet_user_agent or DEFAULT_USER_AGENT).strip()

        env_value = os.environ.get(ENV_API_KEY)
        resolved = api_key if api_key is not None else env_value
        trimmed_key = (resolved or "").strip()

        if self._proxy_secret:
            self._api_key = trimmed_key
        elif trimmed_key == "":
            msg = (
                f"Missing API key: set {ENV_API_KEY} in the environment or pass it to the constructor, "
                "or set POKE_WALLET_PROXY_SECRET to use a proxy that holds the key."
            )
            raise ValueError(msg)
        else:
            self._api_key = trimmed_key

    def search(
        self,
        query: str,
        options: PokeWalletSearchOptions | None = None,
    ) -> PokeWalletSearchResponse:
        """
        Search cards by free-text ``q`` (name, set code, number, etc.).
        Prefer :meth:`search_by_set_code_and_number` when you know set code + card number.

        Args:
            query: Raw search string passed as ``q``.
            options: Optional ``page`` and ``limit`` (limit clamped to 1–100).
        """
        params = self._build_search_params(query, options)
        path = f"/search?{params}"
        raw = self._fetch_response_body(path)
        return cast(PokeWalletSearchResponse, raw)

    def search_by_set_code_and_number(
        self,
        set_code: str,
        card_number: str,
        options: PokeWalletSearchOptions | None = None,
    ) -> PokeWalletSearchResponse:
        """
        Search using **set code + card number** (e.g. ``SV3`` + ``118`` → query ``SV3 118``).
        Matches the API's set-code + number style; preserve case for codes like ``SV2a``.

        Args:
            set_code: Set code (e.g. SV3, SWSH3, CBB3C).
            card_number: Card number (e.g. 118, 148/165).
            options: Optional pagination and ``pokemonName`` (prepended to ``q`` when set).
        """
        normalized_set = set_code.strip()
        normalized_number = card_number.strip()
        if normalized_set == "" or normalized_number == "":
            msg = "search_by_set_code_and_number: set_code and card_number must be non-empty after trim."
            raise ValueError(msg)
        name_raw = (options or {}).get("pokemonName")
        name_part = name_raw.strip() if name_raw else None
        segments: list[str] = []
        if name_part:
            segments.append(name_part)
        segments.extend([normalized_set, normalized_number])
        q = " ".join(segments)
        return self.search(q, options)

    def search_by_set_id_and_number(
        self,
        set_id: str,
        card_number: str,
        options: PokeWalletSearchOptions | None = None,
    ) -> PokeWalletSearchResponse:
        """
        Precise lookup using **numeric set_id + card number** (e.g. ``23609`` + ``118`` as in API docs).
        Use when you already have ``set_id`` from ``/sets`` or a previous card payload.

        Args:
            set_id: Canonical numeric set id string.
            card_number: Card number (e.g. 118 or 118/108).
            options: Optional pagination.
        """
        normalized_set_id = set_id.strip()
        normalized_number = card_number.strip()
        if normalized_set_id == "" or normalized_number == "":
            msg = "search_by_set_id_and_number: set_id and card_number must be non-empty after trim."
            raise ValueError(msg)
        q = f"{normalized_set_id} {normalized_number}"
        return self.search(q, options)

    def get_card_by_id(
        self,
        card_id: str,
        options: PokeWalletGetCardOptions | None = None,
    ) -> PokeWalletCard:
        """
        Fetch a card by id (``pk_…`` or CardMarket-only hex id).
        Optional ``setCode`` maps to query ``set_code`` for disambiguation.
        """
        encoded = quote(card_id, safe="")
        path_base = f"/cards/{encoded}"
        set_code_raw = (options or {}).get("setCode")
        set_code_stripped = set_code_raw.strip() if set_code_raw else ""
        if set_code_stripped:
            path = f"{path_base}?set_code={quote(set_code_stripped, safe='')}"
        else:
            path = path_base
        raw = self._fetch_response_body(path)
        return cast(PokeWalletCard, raw)

    def _build_search_params(self, q: str, options: PokeWalletSearchOptions | None) -> str:
        params: dict[str, str] = {"q": q}
        if options:
            if options.get("page") is not None:
                page = max(SEARCH_PAGE_MIN, int(options["page"]))
                params["page"] = str(page)
            if options.get("limit") is not None:
                raw_limit = int(options["limit"])
                clamped = min(SEARCH_LIMIT_MAX, max(SEARCH_LIMIT_MIN, raw_limit))
                params["limit"] = str(clamped)
        return urlencode(params)

    def _fetch_response_body(self, path: str) -> Any:
        normalized_path = path if path.startswith("/") else f"/{path}"
        cached = _RESPONSE_CACHE.get(normalized_path)
        if cached is not None:
            return cached

        url = f"{self._base_url}{normalized_path}"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if self._proxy_secret:
            headers["X-Proxy-Secret"] = self._proxy_secret
        else:
            headers["X-API-Key"] = self._api_key

        # One attempt + up to len(_RETRY_DELAYS_SEC) retries on 429 / 5xx.
        # This runs in worker threads (executor), so time.sleep is fine.
        response: httpx.Response | None = None
        last_exc: httpx.HTTPError | None = None
        for attempt in range(len(_RETRY_DELAYS_SEC) + 1):
            if attempt > 0:
                delay = _RETRY_DELAYS_SEC[attempt - 1]
                logger.warning(
                    "PokeWallet retry %s/%s in %.0fs (path=%s, reason=%s)",
                    attempt,
                    len(_RETRY_DELAYS_SEC),
                    delay,
                    normalized_path.split("?", 1)[0],
                    response.status_code if response is not None else type(last_exc).__name__,
                )
                time.sleep(delay)
            try:
                response = httpx.get(url, headers=headers, timeout=60.0)
            except httpx.HTTPError as exc:
                last_exc = exc
                response = None
                continue
            if response.status_code not in _RETRYABLE_STATUS:
                break

        if response is None:
            msg = f"PokeWallet request failed after retries: {last_exc}"
            raise RuntimeError(msg)

        _warn_when_quota_low(response)
        body_text = response.text
        if not response.is_success:
            if response.status_code == 429:
                limit_hour = response.headers.get("X-RateLimit-Limit-Hour", "?")
                msg = (
                    f"PokeWallet rate limit reached ({limit_hour} req/h, free plan) — "
                    "retried without success, try again in a few minutes."
                )
                raise RuntimeError(msg)
            msg = (
                f"PokeWallet request failed ({response.status_code} {response.reason_phrase}): "
                f"{body_text}"
            )
            raise RuntimeError(msg)

        parsed = self._parse_json_body(body_text)
        _RESPONSE_CACHE.store(normalized_path, parsed)
        return parsed

    @staticmethod
    def _parse_json_body(body_text: str) -> Any:
        try:
            return json.loads(body_text)
        except json.JSONDecodeError as exc:
            msg = "PokeWallet response was not valid JSON."
            raise RuntimeError(msg) from exc
