"""
Load Vinted worker environment variables **before** ``config.get_settings`` is imported.

Each file is applied in order; later files override keys from earlier ones:

1. ``worker_bundled.env`` — embedded in the PyInstaller sidecar (or next to this package in dev)
2. ``.env`` in the install directory (next to ``goupix-vinted-worker`` when frozen)
3. ``<user-data>/GoupixDex/.env`` — per-user override (e.g. Windows ``%LOCALAPPDATA%``)
4. ``.env`` in the current working directory — local dev (``python desktop_vinted_server.py`` from ``api/``)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_LOADED_ENV_SOURCES: list[str] = []


def _user_data_env_path() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "GoupixDex" / ".env"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GoupixDex" / ".env"
    return Path.home() / ".local" / "share" / "GoupixDex" / ".env"


def _bundled_env_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "worker_bundled.env"
    return Path(__file__).resolve().parent / "worker_bundled.env"


def _install_dir_env_path() -> Path | None:
    """Optional ``.env`` beside the packaged worker executable (install root)."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent / ".env"


def load_worker_dotenv() -> list[str]:
    """Load dotenv files in order; return the list of paths that were loaded."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return []

    paths: list[Path] = [_bundled_env_path()]
    inst = _install_dir_env_path()
    if inst is not None:
        paths.append(inst)
    paths.append(_user_data_env_path())
    paths.append(Path.cwd() / ".env")

    loaded: list[str] = []
    for p in paths:
        try:
            if p.is_file():
                load_dotenv(p, override=True)
                loaded.append(str(p.resolve()))
        except OSError:
            continue
    global _LOADED_ENV_SOURCES
    _LOADED_ENV_SOURCES = loaded
    return loaded


def loaded_env_sources() -> list[str]:
    return list(_LOADED_ENV_SOURCES)
