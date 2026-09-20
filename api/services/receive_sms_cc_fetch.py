"""HTTP fetch for receive-sms.cc inbox pages (browser-like User-Agent)."""

from __future__ import annotations

import httpx

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def fetch_receive_sms_cc_html(url: str, *, timeout: float = 25.0) -> str:
    u = (url or "").strip()
    if not u.startswith("https://receive-sms.cc/"):
        raise ValueError("URL receive-sms.cc attendue (https://receive-sms.cc/…).")
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": _BROWSER_UA}) as client:
        resp = client.get(u)
        resp.raise_for_status()
        return resp.text
