"""
Vinted sync — JSON API headers and session cookie resolution.

This module defines a single class, ``VintedHttpService``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from http.cookiejar import CookieJar
from typing import Any, Optional


def _cookie_load_error_types() -> tuple[type[BaseException], ...]:
    """Exceptions raised when reading local browser cookie stores (e.g. Chrome not installed)."""
    seq: list[type[BaseException]] = [OSError]
    try:
        from browser_cookie3 import BrowserCookieError

        seq.append(BrowserCookieError)
    except ImportError:
        pass
    return tuple(seq)


COOKIE_LOAD_ERRORS: tuple[type[BaseException], ...] = _cookie_load_error_types()


class VintedHttpService:
    """@description Headers for Vinted JSON APIs + ``VINTED_COOKIE`` / browser cookies."""

    @staticmethod
    def _browser_cookie3() -> Any:
        try:
            import browser_cookie3 as bc3  # type: ignore[import-untyped]

            return bc3
        except ImportError:
            return None

    @staticmethod
    def build_json_request_headers(
        base_url: str,
        cookie_header: str | None = None,
    ) -> dict[str, str]:
        """
        @description Headers for same-origin JSON calls (catalog, transactions).

        Args:
            base_url: Site origin, e.g. ``https://www.vinted.fr``.
            cookie_header: Raw ``Cookie`` value, or ``None`` for anonymous calls.
        """
        base: str = base_url.rstrip("/")
        headers: dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
                "Gecko/20100101 Firefox/131.0"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Referer": f"{base}/",
            "Origin": base,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if cookie_header:
            headers["Cookie"] = cookie_header
        return headers

    @staticmethod
    def cookie_from_environment() -> Optional[str]:
        """@description Returns ``VINTED_COOKIE`` when set and non-blank."""
        raw: str = os.environ.get("VINTED_COOKIE", "").strip()
        return raw or None

    @staticmethod
    def _jar_to_header(cookie_jar: CookieJar, domain_substring: str = "vinted") -> str:
        parts: list[str] = []
        for cookie in cookie_jar:
            dom: str = (cookie.domain or "").lower()
            if domain_substring in dom.replace(".", ""):
                parts.append(f"{cookie.name}={cookie.value}")
        return "; ".join(parts)

    @classmethod
    def cookie_from_firefox(cls, domain: str = "vinted.fr") -> Optional[str]:
        bc3 = cls._browser_cookie3()
        if bc3 is None:
            return None
        override: str = os.environ.get("VINTED_FIREFOX_COOKIE_FILE", "").strip()
        try:
            if override:
                jar: CookieJar = bc3.firefox(cookie_file=override, domain_name=domain)
            else:
                jar = bc3.firefox(domain_name=domain)
        except COOKIE_LOAD_ERRORS:
            return None
        return cls._jar_to_header(jar) or None

    @classmethod
    def cookie_from_chrome(cls, domain: str = "vinted.fr") -> Optional[str]:
        bc3 = cls._browser_cookie3()
        if bc3 is None:
            return None
        try:
            jar = bc3.chrome(domain_name=domain)
        except COOKIE_LOAD_ERRORS:
            return None
        return cls._jar_to_header(jar) or None

    @classmethod
    def cookie_from_edge(cls, domain: str = "vinted.fr") -> Optional[str]:
        bc3 = cls._browser_cookie3()
        if bc3 is None:
            return None
        try:
            jar = bc3.edge(domain_name=domain)
        except COOKIE_LOAD_ERRORS:
            return None
        return cls._jar_to_header(jar) or None

    @classmethod
    def preferred_cookie_header(cls) -> tuple[Optional[str], str]:
        """@description First non-empty browser cookie (no API check). Prefer ``preferred_session_cookie_header``."""
        env_cookie: Optional[str] = cls.cookie_from_environment()
        if env_cookie:
            return env_cookie, "environment:VINTED_COOKIE"

        forced: str = os.environ.get("VINTED_BROWSER", "").strip().lower()
        order: list[tuple[str, Callable[[], Optional[str]]]]
        if forced == "chrome":
            order = [
                ("chrome", cls.cookie_from_chrome),
                ("firefox", cls.cookie_from_firefox),
                ("edge", cls.cookie_from_edge),
            ]
        elif forced == "edge":
            order = [
                ("edge", cls.cookie_from_edge),
                ("firefox", cls.cookie_from_firefox),
                ("chrome", cls.cookie_from_chrome),
            ]
        else:
            order = [
                ("firefox", cls.cookie_from_firefox),
                ("chrome", cls.cookie_from_chrome),
                ("edge", cls.cookie_from_edge),
            ]

        for label, fn in order:
            try:
                out: Optional[str] = fn()
            except COOKIE_LOAD_ERRORS:
                out = None
            if out:
                return out, f"browser:{label}"

        return None, "none"

    @classmethod
    def my_orders_session_ok(cls, base_url: str, cookie_header: str | None) -> bool:
        """@description True if ``GET /api/v2/my_orders`` returns 200 with these cookies (seller session)."""
        if not cookie_header or not str(cookie_header).strip():
            return False
        try:
            import requests
        except ImportError:
            return True
        base: str = base_url.rstrip("/")
        headers: dict[str, str] = cls.build_json_request_headers(base_url, cookie_header)
        try:
            r = requests.get(
                f"{base}/api/v2/my_orders",
                params={"page": 1, "per_page": 1},
                headers=headers,
                timeout=30,
            )
        except OSError:
            return False
        return r.status_code == 200

    @classmethod
    def preferred_session_cookie_header(cls, base_url: str) -> tuple[Optional[str], str]:
        """
        @description Cookie header that actually works for seller APIs (``my_orders``).

        Tries ``VINTED_COOKIE``, then each browser in order, and **keeps** the first
        combination that gets HTTP 200 on a minimal ``my_orders`` call. This avoids
        using a Firefox jar that is locked/partial while another browser has a valid
        session — no manual copy-paste required when at least one browser is logged in.
        """
        if os.environ.get("VINTED_SKIP_SESSION_PROBE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            return cls.preferred_cookie_header()

        env_cookie: Optional[str] = cls.cookie_from_environment()
        if env_cookie and cls.my_orders_session_ok(base_url, env_cookie):
            return env_cookie, "environment:VINTED_COOKIE"

        forced: str = os.environ.get("VINTED_BROWSER", "").strip().lower()
        order: list[tuple[str, Callable[[], Optional[str]]]]
        if forced == "chrome":
            order = [
                ("chrome", cls.cookie_from_chrome),
                ("firefox", cls.cookie_from_firefox),
                ("edge", cls.cookie_from_edge),
            ]
        elif forced == "edge":
            order = [
                ("edge", cls.cookie_from_edge),
                ("firefox", cls.cookie_from_firefox),
                ("chrome", cls.cookie_from_chrome),
            ]
        else:
            order = [
                ("firefox", cls.cookie_from_firefox),
                ("chrome", cls.cookie_from_chrome),
                ("edge", cls.cookie_from_edge),
            ]

        import time

        for attempt in range(2):
            for label, fn in order:
                try:
                    raw: Optional[str] = fn()
                except COOKIE_LOAD_ERRORS:
                    raw = None
                if not raw:
                    continue
                if cls.my_orders_session_ok(base_url, raw):
                    return raw, f"browser:{label}"
            if attempt == 0:
                time.sleep(0.45)

        return None, "none"
