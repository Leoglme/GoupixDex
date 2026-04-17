"""HTTP client for the PokéWallet Pokémon card API (https://api.pokewallet.io)."""

from __future__ import annotations

import json
import os
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

DEFAULT_BASE_URL = "https://api.pokewallet.io"
ENV_API_KEY = "POKE_WALLET_API_KEY"
DEFAULT_USER_AGENT = "GoupixDex/1.0 (+https://goupixdex.dibodev.fr)"
SEARCH_LIMIT_MAX = 100
SEARCH_LIMIT_MIN = 1
SEARCH_PAGE_MIN = 1


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
        url = f"{self._base_url}{normalized_path}"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if self._proxy_secret:
            headers["X-Proxy-Secret"] = self._proxy_secret
        else:
            headers["X-API-Key"] = self._api_key
        response = httpx.get(url, headers=headers, timeout=60.0)
        body_text = response.text
        if not response.is_success:
            msg = (
                f"PokeWallet request failed ({response.status_code} {response.reason_phrase}): "
                f"{body_text}"
            )
            raise RuntimeError(msg)
        return self._parse_json_body(body_text)

    @staticmethod
    def _parse_json_body(body_text: str) -> Any:
        try:
            return json.loads(body_text)
        except json.JSONDecodeError as exc:
            msg = "PokeWallet response was not valid JSON."
            raise RuntimeError(msg) from exc
