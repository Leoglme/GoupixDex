"""Disk-cached, RAM-indexed price guide store (``id_product`` → :class:`PriceGuideRow`)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from cardmarket_api.types import PriceGuideRow

_GUIDE_FILENAME = "price_guide_{game_id}.json"
_META_FILENAME = "price_guide_{game_id}.meta.json"


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _row_from_raw(raw: dict[str, Any]) -> PriceGuideRow | None:
    id_product = raw.get("idProduct")
    id_category = raw.get("idCategory")
    if not isinstance(id_product, int) or not isinstance(id_category, int):
        return None
    return PriceGuideRow(
        id_product=id_product,
        id_category=id_category,
        avg=_float_or_none(raw.get("avg")),
        low=_float_or_none(raw.get("low")),
        trend=_float_or_none(raw.get("trend")),
        avg1=_float_or_none(raw.get("avg1")),
        avg7=_float_or_none(raw.get("avg7")),
        avg30=_float_or_none(raw.get("avg30")),
        avg_holo=_float_or_none(raw.get("avg-holo")),
        low_holo=_float_or_none(raw.get("low-holo")),
        trend_holo=_float_or_none(raw.get("trend-holo")),
        avg1_holo=_float_or_none(raw.get("avg1-holo")),
        avg7_holo=_float_or_none(raw.get("avg7-holo")),
        avg30_holo=_float_or_none(raw.get("avg30-holo")),
    )


class PriceGuideStore:
    """
    Holds the latest price guide snapshot.

    - **RAM**: ``dict[int, PriceGuideRow]`` for O(1) lookups from request paths.
    - **Disk**: raw payload + a small meta file (ETag / Last-Modified /
      download timestamp) so restarts never re-download an unchanged guide.

    Thread-safe: lookups and snapshot swaps share one re-entrant lock; the swap
    replaces the whole index atomically.
    """

    def __init__(self, cache_dir: Path | str, game_id: int = 6) -> None:
        self._cache_dir = Path(cache_dir)
        self._game_id = game_id
        self._lock = threading.RLock()
        self._rows: dict[int, PriceGuideRow] = {}
        self._created_at: str | None = None
        self._etag: str | None = None
        self._last_modified: str | None = None
        self._downloaded_at: float | None = None

    # ------------------------------------------------------------------ paths

    @property
    def _guide_path(self) -> Path:
        return self._cache_dir / _GUIDE_FILENAME.format(game_id=self._game_id)

    @property
    def _meta_path(self) -> Path:
        return self._cache_dir / _META_FILENAME.format(game_id=self._game_id)

    # ---------------------------------------------------------------- lookups

    def get(self, id_product: int) -> PriceGuideRow | None:
        with self._lock:
            return self._rows.get(id_product)

    @property
    def row_count(self) -> int:
        with self._lock:
            return len(self._rows)

    @property
    def created_at(self) -> str | None:
        """``createdAt`` of the loaded snapshot (Cardmarket's own timestamp)."""
        with self._lock:
            return self._created_at

    @property
    def etag(self) -> str | None:
        with self._lock:
            return self._etag

    @property
    def last_modified(self) -> str | None:
        with self._lock:
            return self._last_modified

    def age_hours(self) -> float | None:
        """Hours since the snapshot was last downloaded or confirmed unchanged."""
        with self._lock:
            if self._downloaded_at is None:
                return None
            return (time.time() - self._downloaded_at) / 3600.0

    def touch(self) -> None:
        """Mark the in-memory snapshot as freshly validated (after a 304)."""
        with self._lock:
            self._downloaded_at = time.time()
            self._save_meta_locked()

    # ------------------------------------------------------------ persistence

    def load_from_disk(self) -> bool:
        """Rebuild the RAM index from the cached files; ``False`` when absent/corrupt."""
        try:
            raw_payload = json.loads(self._guide_path.read_text(encoding="utf-8"))
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(raw_payload, dict) or not isinstance(meta, dict):
            return False
        rows = self._index_payload(raw_payload)
        if not rows:
            return False
        with self._lock:
            self._rows = rows
            self._created_at = raw_payload.get("createdAt")
            self._etag = meta.get("etag")
            self._last_modified = meta.get("last_modified")
            downloaded_at = meta.get("downloaded_at")
            self._downloaded_at = float(downloaded_at) if isinstance(downloaded_at, (int, float)) else None
        return True

    def replace(
        self,
        payload: dict[str, Any],
        *,
        etag: str | None,
        last_modified: str | None,
    ) -> int:
        """Swap in a fresh snapshot (RAM + disk). Returns the indexed row count."""
        rows = self._index_payload(payload)
        with self._lock:
            self._rows = rows
            self._created_at = payload.get("createdAt")
            self._etag = etag
            self._last_modified = last_modified
            self._downloaded_at = time.time()
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self._guide_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self._guide_path)
            self._save_meta_locked()
            return len(rows)

    def _save_meta_locked(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "etag": self._etag,
            "last_modified": self._last_modified,
            "downloaded_at": self._downloaded_at,
        }
        self._meta_path.write_text(json.dumps(meta), encoding="utf-8")

    @staticmethod
    def _index_payload(payload: dict[str, Any]) -> dict[int, PriceGuideRow]:
        rows: dict[int, PriceGuideRow] = {}
        for raw in payload.get("priceGuides", []):
            if not isinstance(raw, dict):
                continue
            row = _row_from_raw(raw)
            if row is not None:
                rows[row.id_product] = row
        return rows
