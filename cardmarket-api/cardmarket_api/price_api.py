"""Facade: local Cardmarket price lookups backed by the public daily data files."""

from __future__ import annotations

from pathlib import Path

from cardmarket_api.clients.price_guide_download_client import PriceGuideDownloadClient
from cardmarket_api.services.card_price_service import CardPriceService
from cardmarket_api.services.price_guide_refresh_service import (
    DEFAULT_MAX_AGE_HOURS,
    PriceGuideRefreshService,
)
from cardmarket_api.stores.price_guide_store import PriceGuideStore
from cardmarket_api.types import CardmarketCardPrices, PriceGuideRefreshReport, PriceGuideRow


class CardmarketPriceApi:
    """
    Entry point for consumers.

    Construction loads any snapshot cached on disk; :meth:`refresh` is the only
    method that may hit the network. Lookups are pure in-RAM reads and safe to
    call from request paths.
    """

    def __init__(self, cache_dir: Path | str, game_id: int = 6) -> None:
        self._store = PriceGuideStore(cache_dir, game_id=game_id)
        self._refresh_service = PriceGuideRefreshService(
            PriceGuideDownloadClient(game_id=game_id),
            self._store,
        )
        self._store.load_from_disk()

    def refresh(
        self,
        *,
        force: bool = False,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    ) -> PriceGuideRefreshReport:
        """
        Download the latest guide when the current snapshot is stale (or ``force``).

        Raises:
            CardmarketDataUnavailableError: when a required download fails.
        """
        return self._refresh_service.refresh(force=force, max_age_hours=max_age_hours)

    def get_row(self, id_product: int) -> PriceGuideRow | None:
        """Raw guide row for a Cardmarket product id, or ``None`` when unknown."""
        return self._store.get(id_product)

    def get_card_prices(self, id_product: int) -> CardmarketCardPrices | None:
        """Consumer view (reference EUR & friends) for a Cardmarket product id."""
        row = self._store.get(id_product)
        if row is None:
            return None
        return CardPriceService.build_card_prices(row, self._store.created_at)

    @property
    def row_count(self) -> int:
        return self._store.row_count

    @property
    def guide_created_at(self) -> str | None:
        return self._store.created_at

    def guide_age_hours(self) -> float | None:
        return self._store.age_hours()
