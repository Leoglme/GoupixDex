"""
Amazon / Chrome configuration — aligned with GoupixDex (``OsService`` + ``GOUPIX_*`` env prefixes).

Chromium profile and ``amazon_cookies.json`` live outside the repo under ``…/GoupixDex/``.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(_REPO_ROOT / ".env")
load_dotenv()

from services.os_service import OsService


def _resolved_user_data_dir() -> str:
    raw = os.environ.get("GOUPIX_AMAZON_USER_DATA_DIR") or os.environ.get("AMAZON_USER_DATA_DIR")
    if raw and str(raw).strip():
        return str(Path(str(raw).strip()).expanduser().resolve())
    return str(OsService.resolve_amazon_nodriver_user_data_dir(None))


def _resolved_cookies_export_file() -> str:
    raw = os.environ.get("GOUPIX_AMAZON_COOKIES_JSON") or os.environ.get("AMAZON_COOKIES_JSON")
    if raw and str(raw).strip():
        return str(Path(str(raw).strip()).expanduser().resolve())
    prof = Path(_resolved_user_data_dir())
    return str(prof.parent / "amazon_cookies.json")


AMAZON_BASE_URL = (
    os.getenv("GOUPIX_AMAZON_BASE_URL") or os.getenv("AMAZON_BASE_URL") or "https://www.amazon.fr"
).rstrip("/")
AMAZON_USER_DATA_DIR = _resolved_user_data_dir()
AMAZON_COOKIES_EXPORT_FILE = _resolved_cookies_export_file()

AMAZON_CHROME_EXECUTABLE = (
    os.getenv("AMAZON_CHROME_EXECUTABLE")
    or os.getenv("CHROME_EXECUTABLE")
    or os.getenv("GOOGLE_CHROME_BIN")
)
