"""
Local HTTP worker (127.0.0.1): Cardmarket « panier » (nodriver + agrégation vendeurs).

Run from ``api/``::

    python desktop_cardmarket_server.py

Env: ``GOUPIX_CARDMARKET_LOCAL_PORT`` (default 18770), ``GOUPIX_REMOTE_API``,
header ``X-Goupix-Remote-Api`` (same pattern as Vinted / Amazon workers).

PyInstaller::

    pyinstaller desktop_cardmarket_server.spec --noconfirm --clean
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from typing import Annotated, Any

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from worker_env_bootstrap import load_worker_dotenv

load_worker_dotenv()

from core.deps import get_bearer_or_query_token
from core.nodriver_uvicorn_loop import UVICORN_WINDOWS_NODRIVER_LOOP
from core.win32_asyncio import ensure_proactor_event_loop
from services.cardmarket_session_service import (
    clear_session_info,
    persist_session_from_probe,
    probe_tab_and_persist_session,
    read_session_from_tab,
    read_session_info,
)
from services.cardmarket_scraper_service import HOME_POKEMON_URL, _prepare_clean_main_tab
from services.desktop_cardmarket_orders_sync_service import run_cardmarket_orders_sync_job
from services.desktop_cardmarket_runner_service import run_cardmarket_search_job
from services.os_service import OsService

ensure_proactor_event_loop()

logger = logging.getLogger("goupixdex.cardmarket_local")

CARDMARKET_LOGIN_POLL_INTERVAL_SEC = 2.5
CARDMARKET_LOGIN_POLL_MAX_SEC = 600.0

_INTROSPECT_CACHE_TTL_SEC = 120.0
_introspect_cache: dict[str, tuple[float, int]] = {}


def _introspect_cache_key(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _prune_introspect_cache(now: float) -> None:
    if len(_introspect_cache) < 256:
        return
    cutoff = now - _INTROSPECT_CACHE_TTL_SEC * 2
    dead = [k for k, v in _introspect_cache.items() if v[0] < cutoff]
    for k in dead:
        del _introspect_cache[k]


def get_remote_base_flexible(
    x_goupix_remote_api: Annotated[str | None, Header(alias="X-Goupix-Remote-Api")] = None,
    remote_api: Annotated[str | None, Query(description="URL API (introspection JWT)")] = None,
) -> str:
    for cand in (x_goupix_remote_api, remote_api, os.environ.get("GOUPIX_REMOTE_API", "")):
        if cand and str(cand).strip():
            return str(cand).strip().rstrip("/")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Remote API URL required (header X-Goupix-Remote-Api, query remote_api, or GOUPIX_REMOTE_API)."
        ),
    )


async def introspect_user_id(raw_token: str, remote: str) -> int:
    now = time.monotonic()
    key = _introspect_cache_key(raw_token)
    hit = _introspect_cache.get(key)
    if hit is not None and now - hit[0] < _INTROSPECT_CACHE_TTL_SEC:
        return hit[1]

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{remote}/users/me",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == status.HTTP_401_UNAUTHORIZED:
        _introspect_cache.pop(key, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not r.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the remote API to validate the session.",
        )
    uid = int(r.json()["id"])
    _introspect_cache[key] = (now, uid)
    _prune_introspect_cache(now)
    return uid


async def get_user_id_introspected(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> int:
    return await introspect_user_id(raw_token, remote)


_ws_clients: dict[int, set[WebSocket]] = {}
_ws_lock = asyncio.Lock()
_active_tasks: dict[int, asyncio.Task] = {}

_orders_sync_ws_clients: dict[int, set[WebSocket]] = {}
_orders_sync_ws_lock = asyncio.Lock()
_orders_sync_tasks: dict[int, asyncio.Task] = {}
_orders_sync_last_event: dict[int, dict[str, Any]] = {}


async def _broadcast_search(search_id: int, payload: dict[str, Any]) -> None:
    async with _ws_lock:
        clients = list(_ws_clients.get(search_id, set()))
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if not dead:
        return
    async with _ws_lock:
        for ws in dead:
            _ws_clients.get(search_id, set()).discard(ws)


async def _verify_search_access(raw_token: str, remote: str, search_id: int) -> None:
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.get(
            f"{remote}/cardmarket-searches/{search_id}",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found.")
    if r.status_code == status.HTTP_403_FORBIDDEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    if not r.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load search from remote API.",
        )


app = FastAPI(title="GoupixDex Cardmarket local", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "goupixdex-cardmarket-local"}


@app.get("/cardmarket-searches/{search_id}/run/active")
async def run_active(
    search_id: int,
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, bool]:
    t = _active_tasks.get(search_id)
    active = t is not None and not t.done()
    return {"active": active}


@app.post("/cardmarket-searches/{search_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    search_id: int,
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, str]:
    await introspect_user_id(raw_token, remote)
    await _verify_search_access(raw_token, remote, search_id)

    existing = _active_tasks.get(search_id)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A run is already in progress for this search.",
        )

    await _ensure_cm_login_browser_closed()

    async def emit(ev: dict[str, Any]) -> None:
        await _broadcast_search(search_id, ev)

    async def _job() -> None:
        await run_cardmarket_search_job(search_id, raw_token, remote, emit)

    task = asyncio.create_task(_job())
    _active_tasks[search_id] = task

    def _cleanup(_: asyncio.Task) -> None:
        cur = _active_tasks.get(search_id)
        if cur is task:
            _active_tasks.pop(search_id, None)

    task.add_done_callback(_cleanup)
    return {"status": "started"}


@app.post("/cardmarket-searches/{search_id}/cancel")
async def cancel_run(
    search_id: int,
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, str]:
    """Cancel a running scrape — the browser is closed, partial results may be saved by the runner."""
    task = _active_tasks.get(search_id)
    if task is None or task.done():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active run for this search.")
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=20.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("cancel wait_for: %s", exc)
    await _broadcast_search(
        search_id,
        {"type": "cancelled", "message": "Analyse arrêtée par l’utilisateur."},
    )
    return {"status": "cancelled"}


async def _broadcast_orders_sync(user_id: int, payload: dict[str, Any]) -> None:
    """Broadcast a sync event to every active WS client for ``user_id``."""
    async with _orders_sync_ws_lock:
        clients = list(_orders_sync_ws_clients.get(user_id, set()))
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if not dead:
        return
    async with _orders_sync_ws_lock:
        for ws in dead:
            _orders_sync_ws_clients.get(user_id, set()).discard(ws)


@app.get("/cardmarket/orders/sync/active")
async def cardmarket_orders_sync_active(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, Any]:
    """Whether a sync is currently running for the caller (for the UI to resume)."""
    t = _orders_sync_tasks.get(user_id)
    active = t is not None and not t.done()
    last = _orders_sync_last_event.get(user_id)
    return {"active": active, "last_event": last}


@app.post("/cardmarket/orders/sync", status_code=status.HTTP_202_ACCEPTED)
async def cardmarket_orders_sync_start(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, str]:
    """
    Start the Cardmarket purchases-sync job (scrape ``Orders/Purchases/Sent``, dedup, import).

    Returns immediately with ``status=started``; subscribe to the WebSocket to follow progress.
    """
    existing = _orders_sync_tasks.get(user_id)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une synchronisation Cardmarket est déjà en cours pour ce compte.",
        )

    await _ensure_cm_login_browser_closed()

    async def emit(ev: dict[str, Any]) -> None:
        _orders_sync_last_event[user_id] = ev
        await _broadcast_orders_sync(user_id, ev)

    async def _job() -> None:
        await run_cardmarket_orders_sync_job(user_id, raw_token, remote, emit)

    task = asyncio.create_task(_job())
    _orders_sync_tasks[user_id] = task

    def _cleanup(_: asyncio.Task) -> None:
        cur = _orders_sync_tasks.get(user_id)
        if cur is task:
            _orders_sync_tasks.pop(user_id, None)

    task.add_done_callback(_cleanup)
    return {"status": "started"}


@app.post("/cardmarket/orders/sync/cancel")
async def cardmarket_orders_sync_cancel(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, str]:
    """Cancel the running sync (closes the browser; partially-imported orders are kept)."""
    task = _orders_sync_tasks.get(user_id)
    if task is None or task.done():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune synchronisation active.")
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=20.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("orders sync cancel wait: %s", exc)
    await _broadcast_orders_sync(
        user_id,
        {"type": "cancelled", "message": "Synchronisation arrêtée par l’utilisateur."},
    )
    return {"status": "cancelled"}


@app.websocket("/ws/cardmarket/orders/sync/progress")
async def cardmarket_orders_sync_progress_ws(websocket: WebSocket) -> None:
    """Live progress stream for the orders-sync job (one socket per user)."""
    raw_token = websocket.query_params.get("token")
    remote_raw = websocket.query_params.get("remote_api") or os.environ.get("GOUPIX_REMOTE_API", "")
    remote = str(remote_raw).strip().rstrip("/") if remote_raw else ""
    if not raw_token or not remote:
        await websocket.close(code=1008)
        return
    try:
        user_id = await introspect_user_id(raw_token.strip(), remote)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    last = _orders_sync_last_event.get(user_id)
    if last is not None:
        try:
            await websocket.send_json(last)
        except Exception:
            pass

    async with _orders_sync_ws_lock:
        _orders_sync_ws_clients.setdefault(user_id, set()).add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _orders_sync_ws_lock:
            _orders_sync_ws_clients.get(user_id, set()).discard(websocket)


@app.websocket("/ws/cardmarket-searches/{search_id}/progress")
async def cardmarket_progress_websocket(websocket: WebSocket, search_id: int) -> None:
    raw_token = websocket.query_params.get("token")
    remote_raw = websocket.query_params.get("remote_api") or os.environ.get("GOUPIX_REMOTE_API", "")
    remote = str(remote_raw).strip().rstrip("/") if remote_raw else ""
    if not raw_token or not remote:
        await websocket.close(code=1008)
        return
    try:
        await introspect_user_id(raw_token.strip(), remote)
        await _verify_search_access(raw_token.strip(), remote, search_id)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    async with _ws_lock:
        _ws_clients.setdefault(search_id, set()).add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _ws_lock:
            _ws_clients.get(search_id, set()).discard(websocket)


_cm_browser: Any = None
_cm_tab: Any = None
_cm_browser_lock = asyncio.Lock()
_cm_login_task: asyncio.Task | None = None


def _cardmarket_profile_dir() -> Any:
    explicit = (os.environ.get("GOUPIX_CARDMARKET_USER_DATA_DIR") or "").strip() or None
    return OsService.resolve_cardmarket_nodriver_user_data_dir(explicit)


async def _safe_close_cm_browser() -> None:
    """
    Stop the persistent Cardmarket browser used by ``open-login`` (idempotent).

    Chrome flushes its Cookies SQLite **only on a clean shutdown** — nodriver's
    ``browser.stop()`` simply ``terminate()``\\s the process, which can leave
    cookies obtained during login in memory and never on disk (next scrape run
    starts signed-out). We therefore:

    1. Navigate to ``about:blank`` so no page is busy when we close.
    2. Send the CDP ``Browser.close`` command — Chrome quits gracefully and writes
       its session/cookies to disk.
    3. Fall back to ``stop()`` (terminate/kill) for cleanup.
    """
    global _cm_browser, _cm_tab
    browser = _cm_browser
    tab = _cm_tab
    if browser is None:
        return

    if tab is not None:
        try:
            profile = _cardmarket_profile_dir()
            info = await read_session_from_tab(tab)
            if info.get("logged_in") or info.get("username"):
                persist_session_from_probe(profile, info, clear_when_absent=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cm session probe before close: %s", exc)

    if tab is not None:
        try:
            await asyncio.wait_for(tab.get("about:blank"), timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cm pre-close about:blank: %s", exc)

    try:
        import nodriver.cdp.browser as cdp_browser  # type: ignore

        connection = getattr(browser, "connection", None)
        if connection is not None:
            try:
                await asyncio.wait_for(connection.send(cdp_browser.close()), timeout=5.0)
                logger.info("Cardmarket browser: graceful CDP Browser.close sent")
            except Exception as exc:  # noqa: BLE001
                logger.debug("cm CDP Browser.close: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cm CDP import: %s", exc)

    try:
        await asyncio.sleep(2.0)
    except asyncio.CancelledError:
        pass

    try:
        browser.stop()
    except Exception as exc:  # noqa: BLE001
        logger.debug("cm browser.stop: %s", exc)

    try:
        await asyncio.sleep(0.6)
    except asyncio.CancelledError:
        pass

    _cm_browser = None
    _cm_tab = None


async def _cancel_login_polling() -> None:
    """Cancel the background login-polling task if any (used before scrape runs / logout)."""
    global _cm_login_task
    if _cm_login_task is None:
        return
    if not _cm_login_task.done():
        _cm_login_task.cancel()
        try:
            await asyncio.wait_for(_cm_login_task, timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.debug("cancel login polling: %s", exc)
    _cm_login_task = None


async def _ensure_cm_login_browser_closed() -> None:
    """Make sure the connection-helper browser is fully shut down (used by /run before scraping)."""
    async with _cm_browser_lock:
        await _cancel_login_polling()
        await _safe_close_cm_browser()


def _tab_url_lower(tab: Any) -> str:
    try:
        tgt = getattr(tab, "target", None)
        return (getattr(tgt, "url", None) or "").strip().lower()
    except Exception:  # noqa: BLE001
        return ""


def _pick_cardmarket_tab(browser: Any, preferred: Any | None) -> Any:
    """Prefer an open tab whose URL is on cardmarket.com (user may have opened Cardmarket manually)."""
    tabs = list(getattr(browser, "tabs", []) or [])
    for t in tabs:
        if "cardmarket.com" in _tab_url_lower(t):
            return t
    if preferred is not None:
        return preferred
    try:
        main = browser.main_tab()
        if main is not None:
            return main
    except Exception:  # noqa: BLE001
        pass
    return tabs[0] if tabs else preferred


async def _read_session_from_browser(browser: Any, preferred_tab: Any | None) -> dict[str, Any]:
    try:
        await browser.wait(0.12)
    except Exception:  # noqa: BLE001
        pass
    tab = _pick_cardmarket_tab(browser, preferred_tab)
    if tab is None:
        return {"logged_in": False, "username": None, "credit_eur": None}
    return await read_session_from_tab(tab)


async def _open_login_browser_inner() -> dict[str, Any]:
    """Open Chromium on Cardmarket Pokémon home, ready for the user to sign in."""
    global _cm_browser, _cm_tab

    import nodriver as uc

    profile = _cardmarket_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)

    async def _start_browser() -> None:
        global _cm_browser, _cm_tab
        _cm_browser = await uc.start(
            headless=False,
            user_data_dir=str(profile),
            sandbox=False,
            browser_args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--homepage=about:blank",
            ],
        )
        if _cm_browser is None:
            raise RuntimeError("nodriver.start() returned None")
        try:
            await _cm_browser.wait(0.55)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cm browser.wait: %s", exc)
        working = await _prepare_clean_main_tab(_cm_browser)
        await working.get(HOME_POKEMON_URL)
        await working
        try:
            await working.activate()
        except Exception as exc:  # noqa: BLE001
            logger.debug("cm activate: %s", exc)
        _cm_tab = working

    async def _reuse_browser() -> None:
        global _cm_tab
        assert _cm_browser is not None
        try:
            await _cm_browser.wait(0.35)
        except Exception:  # noqa: BLE001
            pass
        working = await _prepare_clean_main_tab(_cm_browser)
        await working.get(HOME_POKEMON_URL)
        await working
        try:
            await working.activate()
        except Exception as exc:  # noqa: BLE001
            logger.debug("cm activate: %s", exc)
        _cm_tab = working

    try:
        if _cm_browser is None or _cm_tab is None:
            await _start_browser()
        else:
            try:
                await _reuse_browser()
            except Exception as nav_exc:  # noqa: BLE001
                logger.warning("cm reuse tab failed (%s); restarting browser", nav_exc)
                await _safe_close_cm_browser()
                await _start_browser()
    except Exception as exc:  # noqa: BLE001
        await _safe_close_cm_browser()
        try:
            await _start_browser()
        except Exception as second_exc:  # noqa: BLE001
            logger.exception("Cardmarket open-login: nodriver start failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not open Chrome for Cardmarket: {second_exc}",
            ) from second_exc
        logger.debug("cm open-login first-attempt error: %s", exc)

    return {"opened": True, "url": HOME_POKEMON_URL}


async def _login_polling_loop() -> None:
    """
    Poll the Cardmarket window: prefer the tab whose URL is on cardmarket.com.

    As soon as a logged-in DOM is detected, persist ``{username, credit_eur}`` and
    **close Chrome cleanly** so the cookies SQLite is flushed to disk — the next
    scrape run reuses the same profile and starts signed in. Stops on timeout or
    when the browser is gone.
    """
    global _cm_tab
    profile = _cardmarket_profile_dir()
    loop = asyncio.get_event_loop()
    started = loop.time()
    first = True
    while True:
        if loop.time() - started > CARDMARKET_LOGIN_POLL_MAX_SEC:
            return
        if _cm_browser is None:
            return
        if not first:
            await asyncio.sleep(CARDMARKET_LOGIN_POLL_INTERVAL_SEC)
        first = False
        picked = _pick_cardmarket_tab(_cm_browser, _cm_tab)
        if picked is None:
            return
        _cm_tab = picked
        info = await _read_session_from_browser(_cm_browser, _cm_tab)
        username = info.get("username")
        if not (isinstance(username, str) and username.strip()):
            continue
        username = username.strip()
        persist_session_from_probe(
            profile,
            {
                "username": username,
                "credit_eur": info.get("credit_eur"),
                "logged_in": True,
            },
        )
        logger.info("Cardmarket session detected for %s — closing helper browser to flush cookies", username)
        async with _cm_browser_lock:
            await _safe_close_cm_browser()
        return


@app.get("/cardmarket/session")
async def cardmarket_session(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, Any]:
    """
    Returns the current Cardmarket connection state.

    - If the helper browser is open: live-reads the DOM (and refreshes the JSON cache).
    - Otherwise: returns the persisted JSON written by the login polling loop.
    """
    global _cm_tab
    profile = _cardmarket_profile_dir()
    live: dict[str, Any] | None = None
    if _cm_browser is not None:
        try:
            tab = _pick_cardmarket_tab(_cm_browser, _cm_tab)
            if tab is not None:
                await tab.get(HOME_POKEMON_URL)
                await tab
                try:
                    await tab.wait(0.7)
                except Exception:  # noqa: BLE001
                    await asyncio.sleep(0.7)
                _cm_tab = tab
            live = await _read_session_from_browser(_cm_browser, _cm_tab)
            if live.get("logged_in") or live.get("username"):
                persist_session_from_probe(profile, live, clear_when_absent=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("session live read: %s", exc)
            live = None

    persisted = read_session_info(profile)
    username: str | None = None
    if persisted and isinstance(persisted.get("username"), str):
        username = persisted["username"].strip() or None

    credit_eur = persisted.get("credit_eur") if persisted else None
    last_seen = persisted.get("last_seen") if persisted else None

    if username:
        state = "ready"
        message = None
    elif _cm_browser is not None:
        state = "busy"
        message = "Chrome ouvert — connectez-vous puis revenez ici (l’état se met à jour automatiquement)."
    else:
        state = "needs_login"
        message = "Cliquez sur « Ouvrir Chrome » pour vous connecter à Cardmarket."

    return {
        "state": state,
        "message": message,
        "username": username,
        "credit_eur": credit_eur,
        "last_seen": last_seen,
        "browser_open": _cm_browser is not None,
    }


@app.post("/cardmarket/open-login")
async def cardmarket_open_login(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, Any]:
    """Open Chromium with the persistent Cardmarket profile and start a background login watcher."""
    global _cm_login_task
    async with _cm_browser_lock:
        result = await _open_login_browser_inner()
        await _cancel_login_polling()
        new_task = asyncio.create_task(_login_polling_loop())
        _cm_login_task = new_task

        def _cleanup(t: asyncio.Task) -> None:
            global _cm_login_task
            if _cm_login_task is t:
                _cm_login_task = None

        new_task.add_done_callback(_cleanup)
    return result


@app.post("/cardmarket/logout")
async def cardmarket_logout(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, str]:
    """Close the helper browser and forget the persisted username/credit (cookies stay in the profile)."""
    profile = _cardmarket_profile_dir()
    async with _cm_browser_lock:
        await _cancel_login_polling()
        await _safe_close_cm_browser()
    clear_session_info(profile)
    return {"status": "ok"}


def _tcp_port_has_listener(host: str, port: int) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


if __name__ == "__main__":
    port = int(os.environ.get("GOUPIX_CARDMARKET_LOCAL_PORT", "18770"))
    host = "127.0.0.1"
    if _tcp_port_has_listener(host, port):
        print(
            f"\n[goupix-cardmarket-worker] Le port {port} est déjà utilisé.\n"
            "  Arrêtez l’autre instance ou changez GOUPIX_CARDMARKET_LOCAL_PORT.\n",
            flush=True,
        )
        raise SystemExit(1)
    loop = UVICORN_WINDOWS_NODRIVER_LOOP if sys.platform == "win32" else "auto"
    uvicorn.run(app, host=host, port=port, loop=loop, log_level="info")
