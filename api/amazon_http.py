"""
HTTP client (httpx) + cookies: sync from nodriver (CDP) or Chromium profile (fallback).
"""
from __future__ import annotations

import json
import os
import warnings
from typing import Any, Dict, List, Optional

import httpx
from httpx import Cookies

from amazon_config import AMAZON_BASE_URL

# Browser-like headers (aligned with a working Firefox/Chrome curl capture)
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}


def requests_cookiejar_to_httpx_cookies(jar: Any) -> Cookies:
    """Convert RequestsCookieJar / http.cookiejar to httpx.Cookies."""
    hc = Cookies()
    try:
        for c in jar:
            domain = getattr(c, "domain", "") or ""
            path = getattr(c, "path", "/") or "/"
            name = getattr(c, "name", "")
            value = getattr(c, "value", "")
            if name:
                hc.set(name=name, value=value, domain=domain, path=path)
    except TypeError:
        try:
            for c in jar:
                hc.set(c.name, c.value, domain=c.domain, path=c.path)
        except Exception:
            pass
    return hc


def nodriver_cookies_to_client(cookie_objects: List[Any]) -> httpx.Client:
    """cookie_objects = result of await browser.cookies.get_all(requests_cookie_format=True)."""
    import requests.cookies

    jar = requests.cookies.RequestsCookieJar()
    for c in cookie_objects:
        jar.set_cookie(c)
    return httpx.Client(
        headers=DEFAULT_HEADERS,
        cookies=requests_cookiejar_to_httpx_cookies(jar),
        follow_redirects=True,
        timeout=30.0,
    )


def write_amazon_cookies_json_from_profile(user_data_dir: str, out_path: str) -> bool:
    """
    After **closing** Chrome: read ``Default/Network/Cookies`` (SQLite) and write ``amazon_cookies.json``.

    Same strategy as GoupixDex / Vinted: avoids CDP ``Storage.getCookies`` which can hang forever.
    """
    try:
        import browser_cookie3
    except ImportError:
        warnings.warn(
            "browser_cookie3 missing — pip install browser-cookie3",
            stacklevel=2,
        )
        return False

    cookie_file = os.path.join(user_data_dir, "Default", "Network", "Cookies")
    if not os.path.isfile(cookie_file):
        cookie_file = os.path.join(user_data_dir, "Default", "Cookies")
    if not os.path.isfile(cookie_file):
        return False

    local_state = os.path.join(user_data_dir, "Local State")
    key_file = local_state if os.path.isfile(local_state) else None

    try:
        cj = browser_cookie3.chromium(
            cookie_file=cookie_file,
            key_file=key_file,
        )
    except Exception as e:
        warnings.warn(f"Lecture cookies SQLite profil: {e}", stacklevel=2)
        return False

    host = AMAZON_BASE_URL.replace("https://", "").replace("http://", "").split("/")[0].lower()
    serializable: List[Dict[str, Any]] = []
    for c in cj:
        dom = (getattr(c, "domain", "") or "").lower()
        if "amazon" not in dom and host not in dom:
            continue
        name = getattr(c, "name", "") or ""
        if not name:
            continue
        serializable.append(
            {
                "name": name,
                "value": getattr(c, "value", "") or "",
                "domain": getattr(c, "domain", "") or "",
                "path": getattr(c, "path", "/") or "/",
                "secure": bool(getattr(c, "secure", False)),
            }
        )

    if not serializable:
        return False

    try:
        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f)
    except OSError:
        return False
    return True


def cookies_from_chromium_profile(user_data_dir: str) -> Optional[httpx.Client]:
    """
    Plan B : lire les cookies depuis le fichier SQLite du profil (sans navigateur ouvert).
    """
    try:
        import browser_cookie3
    except ImportError:
        return None

    cookie_file = os.path.join(user_data_dir, "Default", "Network", "Cookies")
    if not os.path.isfile(cookie_file):
        cookie_file = os.path.join(user_data_dir, "Default", "Cookies")
    if not os.path.isfile(cookie_file):
        return None

    local_state = os.path.join(user_data_dir, "Local State")
    try:
        cj = browser_cookie3.chromium(
            cookie_file=cookie_file,
            key_file=local_state if os.path.isfile(local_state) else None,
        )
    except Exception as e:
        warnings.warn(f"browser_cookie3 (profil Chromium): {e}", stacklevel=2)
        return None

    import requests.cookies

    jar = requests.cookies.RequestsCookieJar()
    host = AMAZON_BASE_URL.replace("https://", "").replace("http://", "").split("/")[0]
    for c in cj:
        try:
            dom = getattr(c, "domain", "") or ""
            if "amazon" in dom or host in dom:
                jar.set_cookie(c)
        except Exception:
            continue

    if not jar:
        return None

    return httpx.Client(
        headers=DEFAULT_HEADERS,
        cookies=requests_cookiejar_to_httpx_cookies(jar),
        follow_redirects=True,
        timeout=30.0,
    )


def cookies_from_legacy_json_export(path: str) -> Optional[httpx.Client]:
    """
    Charge `amazon_cookies.json` (export nodriver ou ancien format Selenium : liste de dicts).
    """
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, list):
        return None
    hc = Cookies()
    n = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not name:
            continue
        value = row.get("value") or ""
        domain = row.get("domain") or ""
        path_c = row.get("path") or "/"
        hc.set(name=name, value=value, domain=domain, path=path_c)
        n += 1
    if n == 0:
        return None
    return httpx.Client(
        headers=DEFAULT_HEADERS,
        cookies=hc,
        follow_redirects=True,
        timeout=30.0,
    )


def looks_like_blocked_or_bot(html: str) -> bool:
    if len(html) < 2500:
        if "productTitle" not in html and "s-search-result" not in html:
            return True
    low = html.lower()
    if "robot check" in low or "enter the characters you see" in low:
        return True
    if "sorry, we just need to make sure you're not a robot" in low:
        return True
    return False


def fetch_html_http(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def post_hdp_request_invite(
    client: httpx.Client,
    *,
    post_url: str,
    csrf_token: str,
    slate_token: Optional[str],
    referer_dp_url: str,
    origin_base: str,
) -> httpx.Response:
    """
    POST an empty body to `data.amazon.fr/.../request-invite/{uuid}` (same contract as the browser).
    """
    headers: dict[str, str] = {
        "Accept": (
            'application/vnd.com.amazon.api+json; type="aapi.highdemandproductcontracts.request-invite/v1"'
        ),
        "Accept-Language": "fr-FR",
        "Content-Type": (
            'application/vnd.com.amazon.api+json; type="aapi.highdemandproductcontracts.request-invite.request/v1"'
        ),
        "Origin": origin_base.rstrip("/"),
        "Referer": referer_dp_url,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "x-api-csrf-token": csrf_token,
    }
    if slate_token:
        headers["x-amzn-encrypted-slate-token"] = slate_token
    return client.post(post_url, headers=headers, content="{}")
