"""
nodriver: start Chrome (persistent profile), sign-in, CDP cookie export, tab-based HTML fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict

import nodriver as uc

from amazon_config import (
    AMAZON_BASE_URL,
    AMAZON_CHROME_EXECUTABLE,
    AMAZON_COOKIES_EXPORT_FILE,
    AMAZON_USER_DATA_DIR,
)
from amazon_http import write_amazon_cookies_json_from_profile
from nodriver_executor import DedicatedAsyncLoop

_browser_holder: dict[str, Any] = {"browser": None}
COOKIES_EXPORT_FILE = AMAZON_COOKIES_EXPORT_FILE


def _ensure_profile_dir() -> None:
    os.makedirs(AMAZON_USER_DATA_DIR, exist_ok=True)


async def _ensure_browser_async():
    _ensure_profile_dir()
    b = _browser_holder["browser"]
    if b is not None and not b.stopped:
        return b
    kwargs: dict[str, Any] = {
        "user_data_dir": AMAZON_USER_DATA_DIR,
        "headless": False,
        "sandbox": True,
    }
    if AMAZON_CHROME_EXECUTABLE:
        kwargs["browser_executable_path"] = AMAZON_CHROME_EXECUTABLE
    browser = await uc.start(**kwargs)
    _browser_holder["browser"] = browser
    return browser


def _schedule_close_browser_after_login() -> None:
    """Close Chrome without blocking the end of ``login_to_amazon_async``: otherwise the HTTP
    POST /api/login response would only leave after ``browser.stop()`` (can hang on Windows)."""

    async def _runner() -> None:
        try:
            await close_browser_async()
        except Exception as e:
            print(f"[nodriver] browser close after login (background): {e!r}")

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        try:
            close_browser_sync()
        except Exception as e:
            print(f"[nodriver] synchronous close after login: {e!r}")


def _force_kill_browser_process(b: Any) -> None:
    """Last resort if ``Browser.stop()`` hangs (nodriver + Chrome on Windows)."""
    proc = getattr(b, "_process", None)
    pid = getattr(b, "_process_pid", None)
    if proc is not None:
        for action in ("terminate", "kill"):
            fn = getattr(proc, action, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=15,
                text=True,
            )
        except Exception as e:
            print(f"[nodriver] taskkill PID {pid}: {e!r}")
    else:
        try:
            os.kill(int(pid), 15)
        except Exception:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass


async def close_browser_async() -> None:
    """Close Chrome with timeout: if the window was closed manually, stop() may hang forever."""
    b = _browser_holder["browser"]
    if b is None:
        return

    def _sync_stop() -> None:
        try:
            if not getattr(b, "stopped", True):
                b.stop()
        except Exception:
            pass

    try:
        await asyncio.wait_for(asyncio.to_thread(_sync_stop), timeout=25.0)
    except asyncio.TimeoutError:
        print("[nodriver] browser.stop() timeout - attempting taskkill", flush=True)
        _force_kill_browser_process(b)
    except Exception as e:
        print(f"[nodriver] browser.stop(): {e}", flush=True)
    finally:
        _browser_holder["browser"] = None


def run_browser(coro, timeout: float = 600):
    return DedicatedAsyncLoop.instance().run(coro, timeout=timeout)


def close_browser_sync() -> None:
    """Same logic as close_browser_async (timeout on stop, holder cleared)."""
    try:
        DedicatedAsyncLoop.instance().run(close_browser_async(), timeout=90)
    except Exception as e:
        print(f"[nodriver] close_browser_sync: {e}")
    finally:
        _browser_holder["browser"] = None


async def export_cookies_requests_format():
    browser = await _ensure_browser_async()
    return await browser.cookies.get_all(requests_cookie_format=True)


async def prime_session_and_export_cookies_async():
    """Open the homepage then return cookies (CDP) for httpx."""
    browser = await _ensure_browser_async()
    await browser.get(AMAZON_BASE_URL)
    await browser.sleep(2)
    return await browser.cookies.get_all(requests_cookie_format=True)


async def fetch_html_via_tab(url: str) -> str:
    browser = await _ensure_browser_async()
    tab = await browser.get(url)
    await browser.sleep(1.2)
    await tab
    return await tab.get_content()


async def login_to_amazon_async() -> Dict[str, Any]:
    """Manual sign-in (like legacy Selenium); cookies exported to JSON at the end."""
    # Reset a zombie session (Chrome closed manually, or stop() stuck).
    await close_browser_async()
    await asyncio.sleep(0.6)

    base_url = AMAZON_BASE_URL
    browser = await _ensure_browser_async()
    tab = await browser.get(base_url)
    await browser.sleep(3)

    try:
        btn = await tab.select('a[data-nav-role="signin"]', timeout=12)
        if btn:
            await btn.click()
            await browser.sleep(3)
    except Exception:
        login_url = f"{base_url}/ap/signin?openid.return_to={base_url}/"
        await tab.get(login_url)
        await browser.sleep(2)

    max_wait = 600
    start_time = time.time()
    error_redirect_count = 0
    max_error_redirects = 3
    last_status_time = time.time()
    logged_in_ready = False

    try:
        while time.time() - start_time < max_wait:
            await tab
            page_source = await tab.get_content()
            current_url = (tab.target.url or "") if tab.target else ""
            page_title = ""
            try:
                page_title = await tab.evaluate("document.title")
            except Exception:
                pass

            if time.time() - last_status_time > 10:
                elapsed = int(time.time() - start_time)
                remaining = int(max_wait - elapsed)
                print(f"   [time] Elapsed: {elapsed}s | Remaining: {remaining}s")
                print(f"   Current URL: {current_url[:80]}...")
                print(f"   Title: {str(page_title)[:50]}...")
                last_status_time = time.time()

            is_error_page = (
                "ne correspond à aucune page active" in page_source
                or "Vous recherchez quelque chose" in page_source
                or "ap_error_page" in page_source
                or ("404" in str(page_title) if page_title else False)
            )

            if is_error_page and error_redirect_count < max_error_redirects:
                print("   [warn] Error page detected, redirecting to homepage...")
                await tab.get(base_url)
                error_redirect_count += 1
                await browser.sleep(3)
                continue

            if error_redirect_count >= max_error_redirects and is_error_page:
                raise RuntimeError("Too many error pages after authentication")

            is_on_amazon_page = (
                "amazon.fr" in current_url
                and "/ap/" not in current_url
                and not is_error_page
            )

            has_amazon_elements = any(
                x in page_source
                for x in (
                    "nav-link-accountList",
                    "nav-cart",
                    "Bonjour,",
                    "Retours et Commandes",
                )
            )

            if is_on_amazon_page and has_amazon_elements:
                logged_in_ready = True
                print(f"   [ok] Sign-in success! Amazon page detected: {current_url}")
                break

            auth_url_keywords = [
                "/ap/signin",
                "/ap/cvf",
                "/ap/mfa",
                "/ap/register",
                "/ap/challenge",
                "/ap/dcq",
            ]
            is_auth_url = any(k in current_url for k in auth_url_keywords)
            has_auth_form = any(
                x in page_source
                for x in (
                    "ap_signin_form",
                    "ap_password",
                    "auth-mfa-form",
                    "cvf-widget-form",
                )
            )

            if is_auth_url or has_auth_form:
                if "qr" in page_source.lower() and "scan" in page_source.lower():
                    print("   [qr] QR code detected - scan with your phone...")
                elif "cvf" in current_url or "mfa" in current_url:
                    print("   [mfa] Two-factor authentication in progress...")
                else:
                    print("   Sign-in page - enter your credentials...")
                await browser.sleep(5)
                continue

            print(f"   Waiting for redirect... (URL: {current_url[:50]}...)")
            await browser.sleep(5)
        else:
            raise TimeoutError("Wait time exceeded (10 minutes)")

        if not logged_in_ready:
            raise RuntimeError("Inconsistent login state after wait loop")

        # Do not call CDP ``Storage.getCookies``: with nodriver it can hang forever and never
        # finish POST /api/login (GoupixDex: close Chrome then read SQLite from profile).
        print(
            "[nodriver] Short pause then close Chrome -> export cookies from on-disk SQLite...",
            flush=True,
        )
        await asyncio.sleep(1.0)

        print("[nodriver] Closing browser (unlock Cookies SQLite file)...", flush=True)
        await close_browser_async()
        await asyncio.sleep(0.6)

        ok_file = await asyncio.to_thread(
            write_amazon_cookies_json_from_profile,
            AMAZON_USER_DATA_DIR,
            COOKIES_EXPORT_FILE,
        )
        if ok_file:
            print(
                f"\nSIGN-IN OK - cookies written from profile -> {COOKIES_EXPORT_FILE}",
                flush=True,
            )
            return {
                "success": True,
                "message": "Sign-in successful. Cookies saved.",
            }

        print(
            "\nSIGN-IN OK - JSON export failed; session still in Chromium profile "
            f"({AMAZON_USER_DATA_DIR}).",
            flush=True,
        )
        return {
            "success": True,
            "message": (
                "Sign-in successful. JSON file could not be generated; "
                "HTTP session will use the Chrome profile (SQLite) if needed."
            ),
        }

    except Exception as wait_error:
        print(f"\nTIMEOUT or ERROR: {wait_error}")
        return {"success": False, "message": str(wait_error)}
    finally:
        _schedule_close_browser_after_login()


def login_to_amazon() -> Dict[str, Any]:
    return run_browser(login_to_amazon_async(), timeout=620)
