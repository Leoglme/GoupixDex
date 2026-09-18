"""Download Cardmarket's daily price guide from its public S3 bucket."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from cardmarket_api.errors import CardmarketDataUnavailableError

DEFAULT_BASE_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide"
DEFAULT_GAME_ID = 6  # Pokémon
DEFAULT_TIMEOUT_SEC = 120.0
DEFAULT_USER_AGENT = "cardmarket-api/0.1 (+https://goupixdex.dibodev.fr)"


@dataclass(frozen=True, slots=True)
class PriceGuideDownload:
    """A freshly downloaded snapshot plus the validators for the next conditional GET."""

    payload: dict[str, Any]
    etag: str | None
    last_modified: str | None


class PriceGuideDownloadClient:
    """
    HTTP client for ``price_guide_{game_id}.json`` (~15 MB, regenerated nightly).

    The bucket is public (no auth, no Cloudflare challenge) and honours
    conditional GETs, so a same-day re-download costs a single 304 round-trip.
    """

    def __init__(
        self,
        game_id: int = DEFAULT_GAME_ID,
        base_url: str = DEFAULT_BASE_URL,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._url = f"{base_url}/price_guide_{game_id}.json"
        self._timeout_sec = timeout_sec
        self._user_agent = user_agent

    @property
    def url(self) -> str:
        return self._url

    def download(
        self,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> PriceGuideDownload | None:
        """
        Fetch the guide, or return ``None`` when the server answers ``304 Not Modified``.

        Raises:
            CardmarketDataUnavailableError: on network failure, non-2xx status
                or an unparsable body.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        try:
            resp = httpx.get(self._url, headers=headers, timeout=self._timeout_sec)
        except httpx.HTTPError as exc:
            msg = f"Cardmarket price guide download failed: {exc}"
            raise CardmarketDataUnavailableError(msg) from exc

        if resp.status_code == httpx.codes.NOT_MODIFIED:
            return None
        if not resp.is_success:
            msg = f"Cardmarket price guide download failed: HTTP {resp.status_code}"
            raise CardmarketDataUnavailableError(msg)

        try:
            payload = resp.json()
        except ValueError as exc:
            msg = "Cardmarket price guide is not valid JSON."
            raise CardmarketDataUnavailableError(msg) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("priceGuides"), list):
            msg = "Cardmarket price guide has an unexpected shape (missing 'priceGuides')."
            raise CardmarketDataUnavailableError(msg)

        return PriceGuideDownload(
            payload=payload,
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )
