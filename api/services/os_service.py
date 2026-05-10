"""Filesystem path helpers for resolving project-relative files."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class OsService:
    """Project paths and Chromium profile dirs for local automation."""

    @staticmethod
    def get_project_root() -> Path:
        """
        Return the repository root directory (parent of ``services/``).

        Returns:
            Absolute path to the project root.
        """
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def resolve_vinted_nodriver_user_data_dir(explicit: str | None) -> Path:
        """
        Chromium profile directory for nodriver (reusable Vinted cookies / session).

        Default: user local data (outside the repo), e.g. ``%LOCALAPPDATA%\\GoupixDex\\…`` on Windows.

        Args:
            explicit: If set (non-empty), absolute or relative path (``~`` allowed).

        Returns:
            Resolved path (caller may create the parent).
        """
        if explicit is not None and str(explicit).strip():
            return Path(str(explicit).strip()).expanduser().resolve()
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA")
            if local:
                return Path(local) / "GoupixDex" / "vinted-nodriver-profile"
            return Path.home() / "GoupixDex" / "vinted-nodriver-profile"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "GoupixDex" / "vinted-nodriver-profile"
        return Path.home() / ".local" / "share" / "GoupixDex" / "vinted-nodriver-profile"

    @staticmethod
    def resolve_amazon_nodriver_user_data_dir(explicit: str | None) -> Path:
        """
        Profil Chromium dédié aux invitations Amazon (nodriver, cookies persistants).

        Surcharge : ``GOUPIX_AMAZON_USER_DATA_DIR`` ou ``AMAZON_USER_DATA_DIR``.

        Args:
            explicit: Chemin non vide depuis l’environnement.

        Returns:
            Répertoire du profil (le parent peut être créé par l’appelant).
        """
        if explicit is not None and str(explicit).strip():
            return Path(str(explicit).strip()).expanduser().resolve()
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA")
            if local:
                return Path(local) / "GoupixDex" / "amazon-nodriver-profile"
            return Path.home() / "GoupixDex" / "amazon-nodriver-profile"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "GoupixDex" / "amazon-nodriver-profile"
        return Path.home() / ".local" / "share" / "GoupixDex" / "amazon-nodriver-profile"

    @staticmethod
    def resolve_cardmarket_nodriver_user_data_dir(explicit: str | None) -> Path:
        """
        Chromium profile for Cardmarket product scraping (nodriver).

        Override: ``GOUPIX_CARDMARKET_USER_DATA_DIR``.
        """
        if explicit is not None and str(explicit).strip():
            return Path(str(explicit).strip()).expanduser().resolve()
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA")
            if local:
                return Path(local) / "GoupixDex" / "cardmarket-nodriver-profile"
            return Path.home() / "GoupixDex" / "cardmarket-nodriver-profile"
        if sys.platform == "darwin":
            return (
                Path.home()
                / "Library"
                / "Application Support"
                / "GoupixDex"
                / "cardmarket-nodriver-profile"
            )
        return Path.home() / ".local" / "share" / "GoupixDex" / "cardmarket-nodriver-profile"


get_project_root = OsService.get_project_root
resolve_vinted_nodriver_user_data_dir = OsService.resolve_vinted_nodriver_user_data_dir
resolve_amazon_nodriver_user_data_dir = OsService.resolve_amazon_nodriver_user_data_dir
resolve_cardmarket_nodriver_user_data_dir = OsService.resolve_cardmarket_nodriver_user_data_dir
