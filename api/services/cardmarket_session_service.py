"""Cardmarket session helpers (DOM parsing + on-disk persistence next to the nodriver profile)."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Live DOM probe (``evaluate`` reads the hydrated page; ``get_content()`` can lag).
CM_LOGIN_PROBE_JS = """
(() => {
  const out = { logged_in: false, username: null, credit_eur: null };
  const dd = document.querySelector('#account-dropdown');
  if (!dd) return JSON.stringify(out);
  const line = dd.querySelector('.line-height115');
  if (line) {
    for (const s of line.querySelectorAll('span')) {
      const t = (s.textContent || '').trim();
      if (t && !t.includes('€') && !t.startsWith('(') && t.toLowerCase() !== 'particulier' && t.length < 60) {
        out.username = t;
        out.logged_in = true;
        break;
      }
    }
  }
  if (!out.username) {
    const mheader = document.querySelector('a#account-dropdown + ul.dropdown-menu h6.dropdown-header');
    if (mheader) {
      for (const s of mheader.querySelectorAll('span')) {
        const t = (s.textContent || '').trim();
        if (t && !t.includes('€') && !t.startsWith('(') && t.length < 60) { out.username = t; out.logged_in = true; break; }
      }
    }
  }
  const credit = document.querySelector('#totalCreditMainNav');
  if (credit) {
    const m = (credit.textContent || '').match(/(-?\\d+(?:[.,]\\d+)?)\\s*€/);
    if (m) out.credit_eur = parseFloat(m[1].replace(',', '.'));
  }
  return JSON.stringify(out);
})()
"""

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


def merge_login_probe(js_info: dict[str, Any], html_info: dict[str, Any]) -> dict[str, Any]:
    """Combine JS (live) and HTML (static) probes; prefer JS username when present."""
    u_js = js_info.get("username") if isinstance(js_info.get("username"), str) else None
    u_html = html_info.get("username") if isinstance(html_info.get("username"), str) else None
    username = (u_js or "").strip() or (u_html or "").strip() or None
    credit = js_info.get("credit_eur")
    if credit is None:
        credit = html_info.get("credit_eur")
    logged_in = bool(username) or bool(html_info.get("logged_in")) or bool(js_info.get("logged_in"))
    return {"logged_in": logged_in, "username": username, "credit_eur": credit}


async def read_session_from_tab(tab: Any) -> dict[str, Any]:
    """
    Read login state via live JS (hydrated DOM) and static HTML fallback.

    @returns ``{logged_in, username, credit_eur}``.
    """
    from nodriver.cdp import runtime as cdp_runtime

    js_info: dict[str, Any] = {"logged_in": False, "username": None, "credit_eur": None}
    try:
        raw = await asyncio.wait_for(
            tab.evaluate(CM_LOGIN_PROBE_JS, return_by_value=True),
            timeout=12.0,
        )
        if isinstance(raw, cdp_runtime.ExceptionDetails):
            logger.debug("cm login probe JS: %s", raw)
        elif isinstance(raw, str):
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                js_info = parsed
        elif isinstance(raw, dict):
            js_info = raw
    except (asyncio.TimeoutError, json.JSONDecodeError, TypeError, Exception) as exc:  # noqa: BLE001
        logger.debug("cm login probe JS failed: %s", exc)

    if js_info.get("credit_eur") is not None:
        try:
            js_info["credit_eur"] = float(js_info["credit_eur"])
        except (TypeError, ValueError):
            js_info["credit_eur"] = None

    html_info: dict[str, Any] = {"logged_in": False, "username": None, "credit_eur": None}
    try:
        html = await asyncio.wait_for(tab.get_content(), timeout=10.0)
        html_info = parse_account_info_from_html(html)
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.debug("cm get_content: %s", exc)

    return merge_login_probe(js_info, html_info)


def persist_session_from_probe(
    profile_dir: Path,
    info: dict[str, Any],
    *,
    clear_when_absent: bool = True,
) -> bool:
    """
    Update on-disk session JSON from a live DOM probe.

    When ``clear_when_absent`` is True (scrape / sync warm-up), a probe without a
    username clears the cache. When False (refresh API, closing the login helper),
    an inconclusive probe leaves the existing cache intact.

    @returns True when a username was persisted (signed in).
    """
    username = info.get("username")
    if isinstance(username, str):
        username = username.strip() or None
    else:
        username = None
    logged_in = bool(info.get("logged_in")) or bool(username)
    if logged_in and username:
        write_session_info(
            profile_dir,
            {"username": username, "credit_eur": info.get("credit_eur")},
        )
        logger.info("Cardmarket session persisted for %s", username)
        return True
    if clear_when_absent:
        clear_session_info(profile_dir)
        logger.info("Cardmarket session cleared (not signed in on live page)")
    return False


async def probe_tab_and_persist_session(
    tab: Any,
    profile_dir: Path,
    *,
    clear_when_absent: bool = True,
) -> dict[str, Any]:
    """
    Probe ``tab`` and sync the result to ``goupix-session.json``.

    Call before closing Chrome after a scrape / sync so GoupixDex reflects logout.
    """
    empty: dict[str, Any] = {"logged_in": False, "username": None, "credit_eur": None}
    try:
        info = await read_session_from_tab(tab)
    except Exception as exc:  # noqa: BLE001
        logger.debug("probe_tab_and_persist_session: %s", exc)
        return empty
    persist_session_from_probe(profile_dir, info, clear_when_absent=clear_when_absent)
    return info
