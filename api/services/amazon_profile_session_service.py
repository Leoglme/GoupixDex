"""Detect Amazon session state from the nodriver Chromium profile (Cookies DB)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

AmazonDetectState = Literal["ready", "needs_login", "busy", "unreadable"]

# Typical cookies when an Amazon account is signed in on amazon.* (France retail).
_AUTH_COOKIE_NAMES = frozenset({"at-main", "sess-at-main", "session-token"})


def is_signed_in_amazon_cookie(name: str, domain: str, value: str | None) -> bool:
    """
    True when one cookie triple proves an authenticated Amazon session.

    Shared by the on-disk profile detection below and the live-browser (CDP)
    detection in the worker, so both paths agree on what "signed in" means.

    Args:
        name: Cookie name.
        domain: Cookie domain (leading dot tolerated).
        value: Cookie value (may be ``None``).
    """
    dom = (domain or "").lower().lstrip(".")
    if "amazon" not in dom.replace(".", ""):
        return False
    cookie_name = (name or "").strip()
    if cookie_name not in _AUTH_COOKIE_NAMES or value is None:
        return False
    val = str(value).strip()
    if cookie_name == "session-token" and len(val) < 80:
        # Short tokens are often anonymous / pre-login
        return False
    return len(val) >= 20


def detect_amazon_session_from_profile(profile_dir: Path) -> AmazonDetectState:
    """
    Inspect ``Default/Network/Cookies`` (Chromium) to infer whether the user is signed in.

    Returns ``busy`` if the DB is locked (Chrome writing) or unreadable.

    Args:
        profile_dir: Root directory of the nodriver Amazon profile.

    Returns:
        ``ready``, ``needs_login``, or ``busy``.
    """
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
        logger.warning("browser_cookie3 missing — Amazon session detection disabled.")
        return "needs_login"

    try:
        jar = bc3.chromium(
            cookie_file=str(cookie_db),
            domain_name="amazon",
            key_file=key_file,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "locked" in msg or "unable to open" in msg or "disk i/o" in msg:
            logger.info("Amazon Cookies DB locked or unreadable (browser likely open): %s", exc)
            return "busy"
        # Chrome 127+ App-Bound Encryption (or permissions) can make the DB
        # undecryptable ("requires admin"): cookies may well be valid — say so
        # instead of pretending the user is signed out.
        logger.warning("Amazon cookie read failed: %s", exc)
        return "unreadable"

    for c in jar:
        if is_signed_in_amazon_cookie(
            getattr(c, "name", "") or "",
            getattr(c, "domain", "") or "",
            getattr(c, "value", None),
        ):
            return "ready"

    return "needs_login"
