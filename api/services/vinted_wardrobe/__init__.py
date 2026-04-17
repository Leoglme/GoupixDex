"""Vinted wardrobe sync (catalog + sold + descriptions) — wired into GoupixDex without the standalone ``vinted-sync`` folder."""

from __future__ import annotations

from services.vinted_wardrobe.goupix_vinted_wardrobe_sync_service import (
    GoupixVintedWardrobeSyncService,
)

__all__ = ["GoupixVintedWardrobeSyncService"]
