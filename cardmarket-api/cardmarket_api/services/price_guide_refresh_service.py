"""Staleness rules and refresh orchestration for the price guide store."""

from __future__ import annotations

from cardmarket_api.clients.price_guide_download_client import PriceGuideDownloadClient
from cardmarket_api.stores.price_guide_store import PriceGuideStore
from cardmarket_api.types import PriceGuideRefreshReport

#: Cardmarket regenerates the guide nightly; below this age a snapshot is
#: considered current and no network round-trip is made unless forced.
DEFAULT_MAX_AGE_HOURS = 20.0


class PriceGuideRefreshService:
    """Decides between serving the current snapshot and hitting the network."""

    def __init__(self, client: PriceGuideDownloadClient, store: PriceGuideStore) -> None:
        self._client = client
        self._store = store

    def refresh(
        self,
        *,
        force: bool = False,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    ) -> PriceGuideRefreshReport:
        """
        Ensure the store holds a usable snapshot, downloading only when needed.

        Raises:
            CardmarketDataUnavailableError: network refresh was required (or
                forced) and failed — the caller decides whether stale data is
                acceptable.
        """
        age = self._store.age_hours()
        if not force and self._store.row_count > 0 and age is not None and age < max_age_hours:
            return PriceGuideRefreshReport(
                refreshed=False,
                source="memory",
                row_count=self._store.row_count,
                created_at=self._store.created_at,
            )

        download = self._client.download(
            etag=self._store.etag,
            last_modified=self._store.last_modified,
        )
        if download is None:
            # 304 — the snapshot we already hold is still the latest one.
            self._store.touch()
            return PriceGuideRefreshReport(
                refreshed=False,
                source="not-modified",
                row_count=self._store.row_count,
                created_at=self._store.created_at,
            )

        row_count = self._store.replace(
            download.payload,
            etag=download.etag,
            last_modified=download.last_modified,
        )
        return PriceGuideRefreshReport(
            refreshed=True,
            source="network",
            row_count=row_count,
            created_at=self._store.created_at,
        )
