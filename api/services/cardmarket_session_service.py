"""Cardmarket session helpers (DOM parsing + on-disk persistence next to the nodriver profile)."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CardmarketSessionState = Literal["ready", "needs_login", "busy", "error"]

SESSION_FILE_NAME = "goupix-session.json"


def session_file_path(profile_dir: Path) -> Path:
    return profile_dir / SESSION_FILE_NAME


def read_session_info(profile_dir: Path) -> dict[str, Any] | None:
    """Return the persisted session JSON ({username, credit_eur, last_seen}) or ``None`` when absent/invalid."""
    path = session_file_path(profile_dir)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:  # noqa: BLE001
        logger.debug("read_session_info: %s", exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_session_info(profile_dir: Path, info: dict[str, Any]) -> None:
    """Persist ``{username, credit_eur, last_seen}`` next to the nodriver profile (best-effort)."""
    path = session_file_path(profile_dir)
    payload = dict(info)
    payload.setdefault("last_seen", dt.datetime.now(dt.UTC).isoformat())
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        logger.warning("write_session_info: %s", exc)


def clear_session_info(profile_dir: Path) -> None:
    """Remove the persisted session JSON; ignore missing file."""
    path = session_file_path(profile_dir)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:  # noqa: BLE001
        logger.debug("clear_session_info: %s", exc)


_CREDIT_PATTERN = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*€")


def _parse_credit_eur(text: str | None) -> float | None:
    """Extract the EUR amount from a Cardmarket credit string (``"( 73,65 € )"`` -> ``73.65``)."""
    if not text:
        return None
    m = _CREDIT_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_account_info_from_html(html: str | None) -> dict[str, Any]:
    """
    Parse the Cardmarket header to detect the logged-in user.

    Returns:
        ``{logged_in: bool, username: str | None, credit_eur: float | None}``.
    """
    out: dict[str, Any] = {"logged_in": False, "username": None, "credit_eur": None}
    if not html:
        return out
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001
        logger.debug("parse_account_info_from_html: BS4 failed: %s", exc)
        return out

    dropdown = soup.select_one("#account-dropdown")
    if dropdown is not None:
        username_node = dropdown.select_one("span.d-none.d-lg-block")
        username = username_node.get_text(strip=True) if username_node else None
        if not username:
            lh = dropdown.select_one("div.line-height115")
            if lh is not None:
                for span in lh.find_all("span"):
                    txt = span.get_text(strip=True)
                    if (
                        txt
                        and "€" not in txt
                        and not txt.startswith("(")
                        and txt.lower() != "particulier"
                        and len(txt) < 60
                    ):
                        username = txt
                        break
        if not username:
            mobile = soup.select_one("a#account-dropdown + ul.dropdown-menu h6.dropdown-header span")
            if mobile is not None:
                t = mobile.get_text(strip=True)
                if t and "€" not in t and "(" not in t and len(t) < 60:
                    username = t
        if not username:
            for span in dropdown.find_all("span"):
                txt = span.get_text(strip=True)
                if (
                    txt
                    and "€" not in txt
                    and not txt.startswith("(")
                    and txt.lower() != "particulier"
                    and len(txt) < 60
                ):
                    username = txt
                    break
        if username:
            out["username"] = username
            out["logged_in"] = True

    credit_node = soup.select_one("#totalCreditMainNav")
    if credit_node is not None:
        out["credit_eur"] = _parse_credit_eur(credit_node.get_text(" ", strip=True))
    elif dropdown is not None:
        out["credit_eur"] = _parse_credit_eur(dropdown.get_text(" ", strip=True))

    if not out["logged_in"]:
        login_form = soup.select_one("#login-signup form#header-login")
        if login_form is not None:
            out["logged_in"] = False

    return out


def is_logged_in_html(html: str | None) -> bool:
    return bool(parse_account_info_from_html(html)["logged_in"])
