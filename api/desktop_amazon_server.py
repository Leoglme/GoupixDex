"""
Local HTTP worker (127.0.0.1): Amazon invites / session (nodriver).

``POST /amazon/invites/refresh`` calls ``AmazonScraper.search_invitation_items``
(same pipeline as ``integrations/amazon-pokemon-scelled``: HTTP + nodriver fallback).

Run from the ``api/`` folder (venv active)::

    python desktop_amazon_server.py

Useful env: ``GOUPIX_AMAZON_LOCAL_PORT`` (default 18768), ``GOUPIX_REMOTE_API``,
header ``X-Goupix-Remote-Api`` (same as the Vinted worker).

After route changes, rebuild the PyInstaller sidecar::
``pyinstaller desktop_amazon_server.spec --noconfirm --clean`` (from ``api/``),
then copy ``dist/goupix-amazon-worker(.exe)`` into ``web/src-tauri/binaries/``.
In Tauri dev, if ``api/`` is found next to the repo, the worker is started with
``python desktop_amazon_server.py`` (always picks up source changes).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, List

import httpx
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, field_validator
from worker_env_bootstrap import load_worker_dotenv

load_worker_dotenv()

from core.deps import get_bearer_or_query_token
from core.win32_asyncio import ensure_proactor_event_loop
from services.amazon_profile_session_service import detect_amazon_session_from_profile
from services.os_service import OsService

ensure_proactor_event_loop()

logger = logging.getLogger("goupixdex.amazon_local")

# Same flow as ``integrations/amazon-pokemon-scelled``: amazon.fr homepage → click « Sign in »,
# else ``/ap/signin?openid.return_to=...`` (opening ``/ap/signin`` alone often shows an error page).
# ``GOUPIX_AMAZON_BASE_URL`` (default https://www.amazon.fr), or ``GOUPIX_AMAZON_SIGNIN_URL`` to force a full URL.

_amazon_browser = None
_amazon_tab = None
_amazon_browser_lock = asyncio.Lock()

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
    """
    Resolve JWT to user id via remote ``GET /users/me`` (same cache as HTTP dependency chain).
    """
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


_progress_ws_clients: set[WebSocket] = set()


async def _broadcast_amazon_progress(payload: dict[str, Any]) -> None:
    """Push JSON to every connected ``/ws/progress`` client (best-effort)."""
    if not _progress_ws_clients:
        return
    weak = list(_progress_ws_clients)
    dead: list[WebSocket] = []
    for ws in weak:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _progress_ws_clients.discard(ws)


def _run_search_with_progress(
    query_arg: str,
    max_pages: int,
    loop: asyncio.AbstractEventLoop,
) -> list[dict[str, Any]]:
    scraper = _get_amazon_scraper()

    def progress_cb(**kw: Any) -> None:
        pl: dict[str, Any] = dict(kw)
        item_data = pl.pop("item_data", None)
        if isinstance(item_data, dict):
            pl["item_title"] = item_data.get("title")
            pl["asin"] = item_data.get("asin")
            try:
                pl["invite_preview"] = _integration_item_to_goupix_invite(dict(item_data))
            except Exception:
                logger.debug("invite_preview (search) skipped", exc_info=True)
        try:
            asyncio.run_coroutine_threadsafe(_broadcast_amazon_progress(pl), loop)
        except Exception:
            pass

    raw = scraper.search_invitation_items(
        query=query_arg,
        max_pages=max_pages,
        progress_callback=progress_cb,
    )
    return [dict(x) for x in raw]


def _merge_search_rows_with_checked(
    search_rows: list[dict[str, Any]],
    checked_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge search rows with ``/dp`` check results (invitation_status, can_order, richer fields)."""
    by_asin: dict[str, dict[str, Any]] = {}
    for c in checked_rows:
        a = str(c.get("asin") or "").strip().upper()
        if a:
            by_asin[a] = c
    out: list[dict[str, Any]] = []
    for s in search_rows:
        row = dict(s)
        a = str(s.get("asin") or "").strip().upper()
        if a and a in by_asin:
            ck = by_asin[a]
            row["invitation_status"] = ck.get("invitation_status")
            row["invitation_requested"] = ck.get("invitation_requested")
            row["can_order"] = ck.get("can_order")
            if ck.get("title"):
                row["title"] = ck["title"]
            if ck.get("price") is not None:
                row["price"] = ck["price"]
            if ck.get("image"):
                row["image"] = ck["image"]
            if ck.get("url"):
                row["url"] = ck["url"]
        out.append(row)
    return out


def _run_check_invites_with_progress(
    asins: List[str],
    loop: asyncio.AbstractEventLoop,
) -> list[dict[str, Any]]:
    scraper = _get_amazon_scraper()

    def progress_cb(**kw: Any) -> None:
        pl: dict[str, Any] = dict(kw)
        item_data = pl.pop("item_data", None)
        if isinstance(item_data, dict):
            pl["item_title"] = item_data.get("title")
            pl["asin"] = item_data.get("asin")
            try:
                pl["invite_preview"] = _integration_item_to_goupix_invite(dict(item_data))
            except Exception:
                logger.debug("invite_preview (check) skipped", exc_info=True)
        try:
            asyncio.run_coroutine_threadsafe(_broadcast_amazon_progress(pl), loop)
        except Exception:
            pass

    raw = scraper.check_invitation_status(asins, progress_callback=progress_cb)
    return [dict(x) for x in raw]


# In-memory cache filled by ``AmazonScraper.search_invitation_items`` (same logic as the integration app).
_invites_cache: list[dict[str, object]] = []
_refreshed_at: str | None = None
_amazon_scraper = None


def _get_amazon_scraper():
    """Lazy import: ``scraper`` pulls in nodriver / bs4."""
    global _amazon_scraper
    if _amazon_scraper is None:
        from scraper import AmazonScraper

        _amazon_scraper = AmazonScraper()
    return _amazon_scraper


def _integration_item_to_goupix_invite(item: dict[str, object]) -> dict[str, object]:
    """Map integration scraper product dict to the shape expected by the GoupixDex frontend."""
    asin = str(item.get("asin") or "").strip()
    st_raw = str(item.get("invitation_status") or "").strip().lower()
    can_order = bool(item.get("can_order"))

    if can_order:
        status = "accepted"
    elif st_raw in ("accepted", "approved"):
        status = "accepted"
    elif st_raw == "expired":
        status = "expired"
    elif st_raw == "requested":
        status = "requested"
    elif st_raw == "not_requested":
        status = "not_requested"
    elif not st_raw:
        status = "listing_only"
    else:
        status = "unknown"

    row_id = asin if asin else f"h{hash((item.get('url'), item.get('title'))) & 0xFFFFFFFFFFFF:x}"
    invited_at = item.get("date_found")
    if invited_at is not None and not isinstance(invited_at, str):
        invited_at = None

    return {
        "id": row_id,
        "title": str(item.get("title") or "Product"),
        "asin": asin or None,
        "image_url": item.get("image") if item.get("image") else None,
        "product_url": item.get("url") if item.get("url") else None,
        "status": status,
        "invited_at": invited_at,
        "price_hint": item.get("price") if item.get("price") else None,
    }


class AmazonRefreshBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = None
    max_pages: int = Field(default=2, ge=1, le=50)


class AmazonRequestInviteBody(BaseModel):
    """Body for ``POST /amazon/invites/request`` (same flow as the browser « Demander une invitation »)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asin: str

    @field_validator("asin", mode="after")
    @classmethod
    def _asin_upper_alnum10(cls, v: str) -> str:
        t = (v or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", t):
            raise ValueError("ASIN invalide (10 caractères alphanumériques).")
        return t


def _norm_q(q: str | None) -> str | None:
    if not q or not str(q).strip():
        return None
    return str(q).strip()


def _amazon_profile_dir() -> Path:
    explicit = os.environ.get("GOUPIX_AMAZON_USER_DATA_DIR") or os.environ.get("AMAZON_USER_DATA_DIR")
    return OsService.resolve_amazon_nodriver_user_data_dir(explicit)


def _amazon_base_url() -> str:
    return os.environ.get("GOUPIX_AMAZON_BASE_URL", "https://www.amazon.fr").rstrip("/")


# Same approach as ``integrations/amazon-pokemon-scelled`` (amazon_nodriver.login_to_amazon_async):
# load the homepage, then click the Sign-in link. Do **not** ``tab.get(.../ap/signin...)``:
# Amazon often shows an error page if /ap/signin is opened directly in the address bar.
_SIGNIN_NAV_SELECTORS: tuple[str, ...] = (
    'a[data-nav-role="signin"]',
    '#nav-link-accountList a[data-nav-role="signin"]',
    "a#nav-signin-tooltip",
    "a.nav-action-signin-header",
)


def _url_is_amazon_auth_flow(url: str) -> bool:
    """True when Amazon has already opened the sign-in / OTP / registration flow."""
    u = (url or "").lower()
    if "amazon." not in u:
        return False
    return any(
        m in u
        for m in (
            "/ap/signin",
            "/ap/cvf",
            "/ap/mfa",
            "/ap/register",
            "/ap/challenge",
            "/ap/dcq",
        )
    )


async def _amazon_click_connexion_depuis_accueil(tab: Any, base: str) -> tuple[bool, str]:
    """
    Returns (True, url_after_click) if a « Sign in / Hello » click succeeded, else (False, base).

    Two passes: multiple selectors, then reload homepage and retry (cookie banner, etc.).
    """
    for attempt in range(2):
        if attempt > 0:
            logger.info("Amazon: reloading homepage then retrying Sign-in click (%s/2)", attempt + 1)
            await tab.get(base)
            await asyncio.sleep(4)
        for sel in _SIGNIN_NAV_SELECTORS:
            try:
                btn = await tab.select(sel, timeout=12)
                if btn:
                    await btn.click()
                    await asyncio.sleep(3)
                    try:
                        loc = (tab.target.url or "")[:400]
                    except Exception:
                        loc = base
                    return True, loc or base
            except Exception as exc:
                logger.debug("Amazon selector %s: %s", sel, exc)
    return False, base


router = APIRouter(prefix="/amazon", tags=["amazon-local"])


@router.get("/session")
async def amazon_session(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    profile = _amazon_profile_dir()
    det = detect_amazon_session_from_profile(profile)
    if det == "busy":
        return {
            "state": "busy",
            "message": "Amazon Chrome appears open — close the window or wait, then try again.",
            "last_sync_at": _refreshed_at,
        }
    if det == "ready":
        return {
            "state": "ready",
            "message": None,
            "last_sync_at": _refreshed_at,
        }
    return {
        "state": "needs_login",
        "message": (
            "Use « Open Chrome » in marketplace settings, sign in, then refresh status."
        ),
        "last_sync_at": _refreshed_at,
    }


async def _amazon_browser_open_login_impl() -> dict[str, object]:
    """Start Chromium (nodriver) with the persistent Amazon profile and open the sign-in flow."""
    global _amazon_browser, _amazon_tab

    import nodriver as uc

    profile = _amazon_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    base = _amazon_base_url()
    signin_override = os.environ.get("GOUPIX_AMAZON_SIGNIN_URL", "").strip()
    if signin_override:
        logger.warning(
            "Amazon open-login: GOUPIX_AMAZON_SIGNIN_URL is set — forcing navigation to this URL. "
            "For homepage-then-Sign-in only, remove it from .env (see worker_env_bootstrap). "
            "Value: %s",
            signin_override[:120],
        )
    last_opened = base
    clicked_flag: list[bool] = [False]
    diag: dict[str, object] = {}

    async with _amazon_browser_lock:

        async def _after_homepage_then_maybe_click(tab: Any) -> None:
            """Homepage already loaded: wait, then click Sign-in unless Amazon already redirected to /ap/."""
            nonlocal last_opened
            await asyncio.sleep(5)
            url0 = ""
            try:
                url0 = (tab.target.url or "").strip()
            except Exception:
                pass
            diag["url_after_homepage"] = url0[:600]
            logger.info("Amazon URL after homepage wait (before optional click): %s", url0[:220])
            if url0 and _url_is_amazon_auth_flow(url0):
                diag["skip_click_reason"] = (
                    "Amazon already opened the sign-in flow (auto redirect, cookies, or session)."
                )
                last_opened = url0
                clicked_flag[0] = False
                return
            clicked, loc = await _amazon_click_connexion_depuis_accueil(tab, base)
            clicked_flag[0] = clicked
            last_opened = loc
            if clicked:
                diag["note_final_url"] = (
                    "If the address bar shows /ap/signin after this step, that is normal redirect "
                    "after clicking Sign in — not a « direct » open via tab.get."
                )
            else:
                logger.warning(
                    "Amazon: automatic Sign-in click failed — use Account & Lists then Sign in manually."
                )

        async def _start_browser() -> None:
            global _amazon_browser
            global _amazon_tab
            nonlocal last_opened
            _amazon_browser = await uc.start(
                headless=False,
                user_data_dir=str(profile),
                sandbox=False,
                browser_args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--disable-dev-shm-usage",
                ],
            )
            if _amazon_browser is None:
                raise RuntimeError("nodriver.start() returned None")
            if signin_override:
                _amazon_tab = await _amazon_browser.get(signin_override)
                last_opened = signin_override
                diag["skip_click_reason"] = "GOUPIX_AMAZON_SIGNIN_URL set — forced navigation to this URL."
                return
            _amazon_tab = await _amazon_browser.get(base)
            await _after_homepage_then_maybe_click(_amazon_tab)

        async def _reuse_tab_navigate() -> None:
            nonlocal last_opened
            if _amazon_tab is None:
                return
            if signin_override:
                await _amazon_tab.get(signin_override)
                last_opened = signin_override
                diag["skip_click_reason"] = "GOUPIX_AMAZON_SIGNIN_URL set."
                return
            await _amazon_tab.get(base)
            await _after_homepage_then_maybe_click(_amazon_tab)

        try:
            if _amazon_browser is None:
                await _start_browser()
            elif _amazon_tab is None:
                if signin_override:
                    _amazon_tab = await _amazon_browser.get(signin_override)
                    last_opened = signin_override
                    diag["skip_click_reason"] = "GOUPIX_AMAZON_SIGNIN_URL set."
                else:
                    _amazon_tab = await _amazon_browser.get(base)
                    await _after_homepage_then_maybe_click(_amazon_tab)
            else:
                await _reuse_tab_navigate()
        except Exception as first_exc:  # noqa: BLE001
            logger.warning("Amazon browser restart after error: %s", first_exc)
            try:
                if _amazon_browser is not None:
                    _amazon_browser.stop()
            except Exception:  # noqa: BLE001
                pass
            _amazon_browser = None
            _amazon_tab = None
            try:
                await _start_browser()
            except Exception as second_exc:  # noqa: BLE001
                logger.exception("Amazon browser could not start")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Could not open Chrome for Amazon: {second_exc}",
                ) from second_exc

    out: dict[str, object] = {
        "opened": True,
        "url": last_opened,
        "base_url": base,
        "signin_clicked": clicked_flag[0],
        "flow": ("url_override" if signin_override else "homepage_then_click_signin"),
    }
    out.update(diag)
    return out


@router.post("/browser/open-login")
async def amazon_browser_open_login(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    """e.g. POST /amazon/browser/open-login (JWT required)."""
    return await _amazon_browser_open_login_impl()


@router.post("/open-login")
async def amazon_open_login_short(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    """e.g. POST /amazon/open-login — same handler (client compatibility)."""
    return await _amazon_browser_open_login_impl()


@router.get("/invites")
async def amazon_invites_list(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
    q: Annotated[str | None, Query(description="Optional Amazon-side search query")] = None,
    max_pages: Annotated[int, Query(ge=1, le=50, description="Number of result pages to scan")] = 2,
) -> dict[str, object]:
    return {
        "items": list(_invites_cache),
        "refreshed_at": _refreshed_at,
        "params": {"q": _norm_q(q), "max_pages": max_pages},
    }


@router.post("/invites/refresh")
async def amazon_invites_refresh(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
    body: AmazonRefreshBody,
) -> dict[str, object]:
    global _invites_cache, _refreshed_at  # noqa: PLW0603

    qn = _norm_q(body.q)
    query_arg = qn if qn else ""
    loop = asyncio.get_running_loop()

    try:
        search_rows = await asyncio.to_thread(
            _run_search_with_progress,
            query_arg,
            body.max_pages,
            loop,
        )
        merged_rows: list[dict[str, Any]] = list(search_rows)
        asins_ordered: list[str] = []
        seen_asin: set[str] = set()
        for x in search_rows:
            a = str(x.get("asin") or "").strip().upper()
            if a and a not in seen_asin:
                seen_asin.add(a)
                asins_ordered.append(a)
        if asins_ordered:
            try:
                await _broadcast_amazon_progress(
                    {
                        "status": "checking_phase",
                        "message": (
                            f"Verifying {len(asins_ordered)} product page(s) for invitation status…"
                        ),
                        "total_pages": len(asins_ordered),
                        "current_page": 0,
                    }
                )
            except Exception:  # noqa: BLE001
                pass
            checked_rows = await asyncio.to_thread(
                _run_check_invites_with_progress,
                asins_ordered,
                loop,
            )
            merged_rows = _merge_search_rows_with_checked(search_rows, checked_rows)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Amazon search_invitation_items")
        try:
            await _broadcast_amazon_progress({"status": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Amazon fetch failed: {exc}",
        ) from exc

    _invites_cache = [_integration_item_to_goupix_invite(x) for x in merged_rows]
    _refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    n = len(_invites_cache)
    if n == 0:
        msg = (
            "No « invite-only » products found on the scanned pages. "
            "Try a broader query or more pages, or check your Amazon session."
        )
    else:
        msg = f"{n} invite-only product(s) found."

    try:
        await _broadcast_amazon_progress(
            {
                "status": "completed",
                "message": msg,
                "items_found": n,
            }
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "items": list(_invites_cache),
        "refreshed_at": _refreshed_at,
        "message": msg,
        "params": {"q": qn, "max_pages": body.max_pages},
    }


@router.post("/invites/request")
async def amazon_invites_request(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
    body: AmazonRequestInviteBody,
) -> dict[str, object]:
    """
    POST Amazon ``request-invite`` for one ASIN (session cookies), then refresh that row in the local cache.
    """
    global _invites_cache  # noqa: PLW0603

    asin = body.asin
    try:
        result = await asyncio.to_thread(_get_amazon_scraper().request_invitation_for_asin, asin)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Amazon request_invitation_for_asin")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Worker error: {exc}",
        ) from exc

    if not result.get("success"):
        return {
            "success": False,
            "message": str(result.get("message") or "La demande a échoué."),
        }

    raw_item = result.get("item")
    goupix: dict[str, object] | None = None
    if isinstance(raw_item, dict):
        goupix = _integration_item_to_goupix_invite(raw_item)
        new_cache: list[dict[str, object]] = []
        replaced = False
        for row in _invites_cache:
            r_asin = str(row.get("asin") or "").strip().upper()
            if r_asin == asin:
                new_cache.append(goupix)
                replaced = True
            else:
                new_cache.append(dict(row))
        if replaced:
            _invites_cache = new_cache

    return {
        "success": True,
        "message": str(result.get("message") or "Invitation demandée."),
        "invite": goupix,
    }


app = FastAPI(title="GoupixDex Amazon local", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.websocket("/ws/progress")
async def amazon_progress_websocket(websocket: WebSocket) -> None:
    """
    Real-time JSON events during ``POST /amazon/invites/refresh`` (search progress).
    Connect with ``?token=JWT&remote_api=https://...`` (same token and API as local workers).
    """
    raw_token = websocket.query_params.get("token")
    remote_raw = websocket.query_params.get("remote_api") or os.environ.get("GOUPIX_REMOTE_API", "")
    remote = str(remote_raw).strip().rstrip("/") if remote_raw else ""
    if not raw_token or not remote:
        await websocket.close(code=1008)
        return
    try:
        await introspect_user_id(raw_token.strip(), remote)
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    _progress_ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _progress_ws_clients.discard(websocket)


@app.get("/health")
def health() -> dict[str, object]:
    """Smoke check for running build (curl http://127.0.0.1:18768/health)."""
    return {
        "status": "ok",
        "service": "goupixdex-amazon-local",
        "routes_revision": 9,
        "has_ws_progress": True,
        "has_post_open_login": True,
    }


def _tcp_port_has_listener(host: str, port: int) -> bool:
    """True if something already listens on host:port (avoid duplicate worker startup)."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


if __name__ == "__main__":
    port = int(os.environ.get("GOUPIX_AMAZON_LOCAL_PORT", "18768"))
    host = "127.0.0.1"
    if _tcp_port_has_listener(host, port):
        print(
            f"\n[goupix-amazon-worker] Port {port} is already in use.\n"
            "  Another instance is running (often a manually started ``python desktop_amazon_server.py``).\n"
            "  Stop it before restarting Tauri or this script.\n"
            "  PowerShell: Get-NetTCPConnection -LocalPort "
            f"{port} | Select-Object LocalPort, OwningProcess\n"
            f"  then: Stop-Process -Id <PID> -Force\n",
            flush=True,
        )
        raise SystemExit(1)
    uvicorn.run(app, host=host, port=port, log_level="info")
