"""Detect Leboncoin session state from the nodriver Chromium profile (Cookies DB)."""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

SESSION_FILE_NAME = "goupix-leboncoin-session.json"


def session_file_path(profile_dir: Path) -> Path:
    return profile_dir / SESSION_FILE_NAME


def read_leboncoin_session_info(profile_dir: Path) -> dict[str, Any] | None:
    path = session_file_path(profile_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # noqa: BLE001
        logger.debug("read_leboncoin_session_info: %s", exc)
        return None
    return data if isinstance(data, dict) else None


def write_leboncoin_session_info(profile_dir: Path, info: dict[str, Any]) -> None:
    payload = dict(info)
    payload.setdefault("last_seen", dt.datetime.now(dt.UTC).isoformat())
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        session_file_path(profile_dir).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:  # noqa: BLE001
        logger.warning("write_leboncoin_session_info: %s", exc)


def clear_leboncoin_session_info(profile_dir: Path) -> None:
    try:
        session_file_path(profile_dir).unlink(missing_ok=True)
    except OSError as exc:  # noqa: BLE001
        logger.debug("clear_leboncoin_session_info: %s", exc)


def persisted_session_is_ready(profile_dir: Path) -> bool:
    data = read_leboncoin_session_info(profile_dir)
    return bool(data and data.get("logged_in"))

LeboncoinDetectState = Literal["ready", "needs_login", "busy", "unreadable"]

# Auth cookies on .leboncoin.fr / auth.leboncoin.fr (names evolve; keep several heuristics).
_LBC_AUTH_COOKIE_NAMES = frozenset(
    {
        "luat",
        "access_token",
        "lbc_session",
        "login",
        "id_token",
        "__Secure-login",
    }
)


def is_signed_in_leboncoin_cookie(name: str, domain: str, value: str | None) -> bool:
    dom = (domain or "").lower().lstrip(".")
    if "leboncoin" not in dom:
        return False
    if value is None:
        return False
    cookie_name = (name or "").strip()
    val = str(value).strip()
    if not val:
        return False
    if cookie_name in _LBC_AUTH_COOKIE_NAMES:
        min_len = 8 if cookie_name in ("__Secure-login", "login") else 16
        return len(val) >= min_len
    lower = cookie_name.lower()
    if lower.endswith("-login") or lower.endswith("_login"):
        return len(val) >= 8
    return False


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
