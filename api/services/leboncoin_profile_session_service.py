"""Detect Leboncoin session state from the nodriver Chromium profile (Cookies DB)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

LeboncoinDetectState = Literal["ready", "needs_login", "busy", "unreadable"]

# Session JWT cookie name (see community reverse-engineering of Leboncoin auth).
_LBC_AUTH_COOKIE_NAMES = frozenset({"luat", "access_token", "lbc_session"})


def is_signed_in_leboncoin_cookie(name: str, domain: str, value: str | None) -> bool:
    dom = (domain or "").lower().lstrip(".")
    if "leboncoin" not in dom:
        return False
    cookie_name = (name or "").strip()
    if cookie_name not in _LBC_AUTH_COOKIE_NAMES or value is None:
        return False
    val = str(value).strip()
    return len(val) >= 24


def detect_leboncoin_session_from_profile(profile_dir: Path) -> LeboncoinDetectState:
    """Inspect Chromium cookies to infer whether the user is signed in on leboncoin.fr."""
    profile_dir = profile_dir.resolve()
    network = profile_dir / "Default" / "Network" / "Cookies"
    legacy = profile_dir / "Default" / "Cookies"
    cookie_db = network if network.is_file() else legacy
    if not cookie_db.is_file():
        return "needs_login"

    local_state = profile_dir / "Local State"
    key_file = str(local_state) if local_state.is_file() else None

    try:
        import browser_cookie3 as bc3
    except ImportError:
        logger.warning("browser_cookie3 missing — Leboncoin session detection disabled.")
        return "needs_login"

    try:
        jar = bc3.chromium(
            cookie_file=str(cookie_db),
            domain_name="leboncoin",
            key_file=key_file,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "locked" in msg or "unable to open" in msg or "disk i/o" in msg:
            logger.info("Leboncoin Cookies DB locked (browser likely open): %s", exc)
            return "busy"
        logger.warning("Leboncoin cookie DB unreadable: %s", exc)
        return "unreadable"

    for c in jar:
        if is_signed_in_leboncoin_cookie(c.name, c.domain, c.value):
            return "ready"
    return "needs_login"
