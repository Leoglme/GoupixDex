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
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, List

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
from services.amazon_worker_accounts import (
    bind_amazon_profile_for,
    bind_provision_staging_profile,
    claim_provision_staging_profile,
    discard_provision_staging_profile,
    fetch_account_credentials,
    fetch_active_account_id,
    fetch_vault_account_ids,
    legacy_amazon_profile_dir,
)
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


async def bind_active_amazon_profile(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> int | None:
    """Select Chromium profile for the user's active vault account (legacy path if none)."""
    try:
        account_id = await fetch_active_account_id(raw_token, remote)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    bind_amazon_profile_for(user_id, account_id)
    _reset_amazon_scraper()
    return account_id


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
    max_items: int | None = None,
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
        max_items=max_items,
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
    scraper: Any | None = None,
    account_scope: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vérifie chaque ASIN ; ``scraper`` épinglé et ``account_scope`` (compte i/n) pour la boucle multi-comptes."""
    scraper = scraper if scraper is not None else _get_amazon_scraper()

    def progress_cb(**kw: Any) -> None:
        pl: dict[str, Any] = dict(kw)
        if account_scope:
            pl.update(account_scope)
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


# In-memory cache per (user, active account).
_invites_cache: dict[str, list[dict[str, object]]] = {}
_refreshed_at: dict[str, str | None] = {}
# Last Amazon search rows per user (shared across vault accounts — statuses differ per profile).
_catalog_search_rows: dict[int, list[dict[str, Any]]] = {}
_amazon_scraper = None
# Sérialise les opérations qui lient un profil ou utilisent le scraper global (refresh, reverify, request, verify-all).
_invites_lock = asyncio.Lock()


async def hold_invites_lock() -> AsyncIterator[None]:
    """Dépendance FastAPI : garde le verrou des invites pendant toute l'exécution du handler."""
    async with _invites_lock:
        yield


def _browser_scraper():
    """Scraper qui lit chaque page via le Chrome du profil lié : compte connecté, aucun cookie à extraire."""
    from scraper import AmazonScraper

    return AmazonScraper(prefer_browser=True)


async def _ensure_account_signed_in(
    user_id: int,
    account_id: int,
    raw_token: str,
    remote: str,
    scraper: Any,
) -> None:
    """Vérifie le compte dans Chrome ; s'il n'est pas connecté, connexion automatique avec le coffre."""
    state = await asyncio.to_thread(scraper.session_state_via_browser)
    if state == "ready":
        return
    try:
        email, password = await fetch_account_credentials(raw_token, remote, account_id)
    except (ValueError, PermissionError) as exc:
        raise RuntimeError(f"Identifiants du coffre indisponibles : {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Identifiants du coffre injoignables : {exc}") from exc

    from amazon_nodriver import login_to_amazon

    logger.info("Vault auto-login (multi-comptes) for account %s (%s)", account_id, email[:3] + "***")
    # Même Chrome que la lecture du message d'accueil, gardé ouvert pour la vérification des fiches.
    result = await asyncio.to_thread(
        lambda: login_to_amazon(email, password, reuse_browser=True, keep_browser_open=True)
    )
    if not result.get("success"):
        raise RuntimeError(str(result.get("message") or "Connexion automatique échouée."))
    _write_session_marker()
    state = await asyncio.to_thread(scraper.session_state_via_browser)
    if state != "ready":
        raise RuntimeError("Connexion automatique non confirmée (2FA ou captcha ?).")


def _invites_cache_key(user_id: int, account_id: int | None) -> str:
    return f"{user_id}:{account_id or 0}"


def _reset_amazon_scraper() -> None:
    global _amazon_scraper
    if _amazon_scraper is not None:
        try:
            _amazon_scraper.close_browser()
        except Exception:  # noqa: BLE001
            pass
    _amazon_scraper = None


def _get_amazon_scraper():
    """Lazy import: ``scraper`` pulls in nodriver / bs4."""
    global _amazon_scraper
    if _amazon_scraper is None:
        from scraper import AmazonScraper

        _amazon_scraper = AmazonScraper()
    else:
        _amazon_scraper._invalidate_http()
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
    elif st_raw == "needs_login":
        status = "needs_login"
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
    max_items: int | None = Field(default=None, ge=1, le=500)
    #: False quand le front vérifie ensuite les statuts sur chaque compte (``/invites/verify-all``).
    check_statuses: bool = True


class AmazonReverifyItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    asin: str | None = None
    title: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    price_hint: str | None = None


class AmazonReverifyBody(BaseModel):
    """Re-check invitation status for known ASINs on the active account (no new Amazon search)."""

    model_config = ConfigDict(extra="forbid")

    items: list[AmazonReverifyItem] = Field(default_factory=list, max_length=500)


def _goupix_invites_to_search_rows(items: list[AmazonReverifyItem]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for inv in items:
        asin = str(inv.asin or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", asin):
            continue
        row: dict[str, Any] = {"asin": asin}
        if inv.title:
            row["title"] = inv.title
        if inv.product_url:
            row["url"] = inv.product_url
        if inv.image_url:
            row["image"] = inv.image_url
        if inv.price_hint:
            row["price"] = inv.price_hint
        out.append(row)
    return out


class AmazonRequestInviteBody(BaseModel):
    """Body for ``POST /amazon/invites/request`` (same flow as the browser « Demander une invitation »)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asin: str
    #: Compte du coffre depuis lequel envoyer la demande (sinon : compte actif côté API).
    account_id: int | None = Field(default=None, ge=1)

    @field_validator("asin", mode="after")
    @classmethod
    def _asin_upper_alnum10(cls, v: str) -> str:
        t = (v or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", t):
            raise ValueError("ASIN invalide (10 caractères alphanumériques).")
        return t


class AmazonProvisionRegisterBody(BaseModel):
    """Chrome inscription Amazon sans compte coffre (profil staging local)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str
    password: str
    customer_name: str = "GoupixDex"


class AmazonProvisionEmailCodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=4, max_length=12)


class AmazonProvisionPhoneBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phone_e164: str = Field(min_length=8, max_length=20)


def _norm_q(q: str | None) -> str | None:
    if not q or not str(q).strip():
        return None
    return str(q).strip()


def _resolve_invite_scan_pages(max_pages: int, max_items: int | None, query: str) -> int:
    """
    Invite-only rows are sparse on filtered searches — scan more Amazon pages until
    ``max_items`` is reached (search loop stops early) or this budget is exhausted.
    """
    pages = max(1, min(50, int(max_pages)))
    if not max_items or int(max_items) <= 0:
        return pages
    mi = int(max_items)
    if (query or "").strip():
        sparse_min = min(50, max(3, (mi + 2) // 2))
        pages = max(pages, sparse_min)
    return min(50, pages)


def _amazon_profile_dir() -> Path:
    import amazon_config as ac

    return Path(ac.AMAZON_USER_DATA_DIR or str(legacy_amazon_profile_dir()))


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

# Bump when new local routes are added (UI can warn if the running sidecar is stale).
AMAZON_WORKER_BUILD = "2026-03-21-receive-sms-auto-allocate"


@router.get("/meta")
async def amazon_worker_meta() -> dict[str, object]:
    return {
        "build": AMAZON_WORKER_BUILD,
        "features": [
            "accounts-open-register",
            "provision-open-register",
            "provision-fill-email-code",
            "provision-fill-cvf-phone",
            "provision-receive-sms-inbox",
            "provision-receive-sms-allocate",
            "invites-reverify",
        ],
    }


#: Localized "please sign in" greetings shown in Amazon's nav when signed out.
_SIGNED_OUT_GREETING_MARKERS = ("identifiez", "s'identifier", "s’identifier", "sign in", "connectez")

#: JS snippet returning the nav greeting text ("" outside store pages / during /ap/ flows).
_GREETING_JS = (
    "(() => { const el = document.querySelector('#nav-link-accountList-nav-line-1');"
    " return el && el.textContent ? el.textContent.trim() : ''; })()"
)


async def _detect_session_via_live_browser() -> str | None:
    """
    Ask the *running* login window whether the user is signed in, via the DOM.

    While the window is open, Chromium holds the on-disk Cookies DB locked (and
    Chrome 127+ App-Bound Encryption can even fail with "requires admin"), so
    the profile-file detection is unusable — which used to make "Actualiser
    l'état" look broken right after a successful sign-in.

    We deliberately do NOT read cookies over CDP: the pinned nodriver version
    crashes parsing modern Chrome cookie payloads (``KeyError: 'sameParty'``)
    and that poisons the whole CDP connection. Amazon's nav greeting
    ("Bonjour, <prénom>" vs "Bonjour, Identifiez-vous") is just as decisive.

    Returns ``None`` when no browser is running (caller falls back to the
    profile file), ``ready``/``needs_login`` otherwise.
    """
    tab = _amazon_tab
    if _amazon_browser is None or tab is None:
        return None
    try:
        greeting = await asyncio.wait_for(tab.evaluate(_GREETING_JS), timeout=8)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Amazon live greeting read failed: %s: %s", type(exc).__name__, exc)
        return None
    text = str(greeting or "").strip()
    if not text:
        # Login / OTP pages have no nav greeting — the user is mid sign-in.
        return "needs_login"
    lowered = text.casefold()
    if any(marker in lowered for marker in _SIGNED_OUT_GREETING_MARKERS):
        return "needs_login"
    return "ready"


#: Written next to the profile when a signed-in session was positively seen
#: (live CDP read). Lets the profile detection answer "ready" even when the
#: cookie DB itself is undecryptable (Chrome App-Bound Encryption).
_SESSION_MARKER_NAME = "goupix-session-ok.json"
_SESSION_MARKER_MAX_AGE_SEC = 7 * 24 * 3600


def _write_session_marker() -> None:
    """Persist "a signed-in session was confirmed at <now>" beside the profile."""
    try:
        marker = _amazon_profile_dir() / _SESSION_MARKER_NAME
        marker.write_text(json.dumps({"confirmed_at": time.time()}), encoding="utf-8")
    except OSError as exc:
        logger.debug("Amazon session marker write failed: %s", exc)


def _session_marker_fresh() -> bool:
    """True when a signed-in session was confirmed less than a week ago."""
    try:
        marker = _amazon_profile_dir() / _SESSION_MARKER_NAME
        payload = json.loads(marker.read_text(encoding="utf-8"))
        confirmed_at = float(payload.get("confirmed_at") or 0.0)
        return 0 < time.time() - confirmed_at < _SESSION_MARKER_MAX_AGE_SEC
    except (OSError, ValueError, TypeError):
        return False


@router.get("/session")
async def amazon_session(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
) -> dict[str, object]:
    cache_key = _invites_cache_key(user_id, active_account_id)
    last_sync = _refreshed_at.get(cache_key)
    live = await _detect_session_via_live_browser()
    if live == "ready":
        _write_session_marker()
        return {
            "state": "ready",
            "message": "Session détectée dans la fenêtre Chrome ouverte.",
            "browser_open": True,
            "last_sync_at": last_sync,
            "active_account_id": active_account_id,
        }
    if live == "needs_login":
        return {
            "state": "needs_login",
            "message": "Fenêtre Chrome ouverte — connectez-vous à Amazon, l'état se mettra à jour tout seul.",
            "browser_open": True,
            "last_sync_at": last_sync,
            "active_account_id": active_account_id,
        }

    profile = _amazon_profile_dir()
    det = detect_amazon_session_from_profile(profile)
    if det == "busy":
        return {
            "state": "busy",
            "message": "Un Chrome Amazon semble ouvert — fermez la fenêtre ou attendez, puis réessayez.",
            "browser_open": False,
            "last_sync_at": last_sync,
            "active_account_id": active_account_id,
        }
    if det == "ready":
        _write_session_marker()
        return {
            "state": "ready",
            "message": None,
            "browser_open": False,
            "last_sync_at": last_sync,
            "active_account_id": active_account_id,
        }
    if det == "unreadable" and _session_marker_fresh():
        return {
            "state": "ready",
            "message": "Session confirmée récemment (cookies illisibles sur ce Chrome, comportement normal).",
            "browser_open": False,
            "last_sync_at": last_sync,
            "active_account_id": active_account_id,
        }
    return {
        "state": "needs_login",
        "message": "Utilisez « Connexion auto » ou « Ouvrir Chrome » dans les réglages marketplace.",
        "browser_open": False,
        "last_sync_at": last_sync,
        "active_account_id": active_account_id,
    }


async def _close_all_amazon_chromium() -> None:
    """Fermer le Chrome du worker ET celui de ``amazon_nodriver`` (un seul profil à la fois)."""
    global _amazon_browser, _amazon_tab
    async with _amazon_browser_lock:
        browser = _amazon_browser
        _amazon_browser = None
        _amazon_tab = None
    if browser is not None:
        try:
            browser.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Amazon browser stop before register: %s", exc)
    from amazon_nodriver import close_browser_sync

    try:
        close_browser_sync()
    except Exception as exc:  # noqa: BLE001
        logger.warning("amazon_nodriver close before register: %s", exc)
    await asyncio.sleep(0.5)


@router.post("/browser/close")
async def amazon_browser_close(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    """
    Close the login Chromium cleanly so the profile flushes its cookies to disk
    (the on-disk detection then works without the window in the way).
    """
    global _amazon_browser, _amazon_tab
    async with _amazon_browser_lock:
        browser = _amazon_browser
        _amazon_browser = None
        _amazon_tab = None
    if browser is None:
        return {"closed": False, "message": "Aucune fenêtre Chrome ouverte par le worker."}
    try:
        browser.stop()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Amazon browser close failed: %s", exc)
        return {"closed": False, "message": f"Fermeture incomplète : {exc}"}
    return {"closed": True, "message": None}


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
    _active: Annotated[int | None, Depends(bind_active_amazon_profile)],
) -> dict[str, object]:
    """e.g. POST /amazon/browser/open-login (JWT required)."""
    return await _amazon_browser_open_login_impl()


@router.post("/open-login")
async def amazon_open_login_short(
    _user_id: Annotated[int, Depends(get_user_id_introspected)],
    _active: Annotated[int | None, Depends(bind_active_amazon_profile)],
) -> dict[str, object]:
    """e.g. POST /amazon/open-login — same handler (client compatibility)."""
    return await _amazon_browser_open_login_impl()


async def _try_vault_auto_login_if_needed(
    user_id: int,
    account_id: int,
    raw_token: str,
    remote: str,
    profile: Path,
) -> dict[str, object] | None:
    """
    When the bound profile has no Amazon session, sign in with vault credentials
    (2FA/CAPTCHA may still require manual steps in the Chrome window).
    """
    det = detect_amazon_session_from_profile(profile)
    if det == "ready":
        return {"success": True, "skipped": True, "message": "Session déjà active sur ce profil."}
    try:
        email, password = await fetch_account_credentials(raw_token, remote, account_id)
    except (ValueError, PermissionError) as exc:
        logger.info("Vault auto-login skipped for account %s: %s", account_id, exc)
        return None
    except httpx.HTTPError as exc:
        logger.warning("Vault auto-login credentials fetch failed: %s", exc)
        return None

    from amazon_nodriver import login_to_amazon

    logger.info("Vault auto-login for account %s (%s)", account_id, email[:3] + "***")
    result = await asyncio.to_thread(login_to_amazon, email, password)
    if result.get("success"):
        _write_session_marker()
        _reset_amazon_scraper()
    return dict(result)


@router.post("/accounts/{account_id}/activate")
async def amazon_activate_account(
    account_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    """Set active vault account on the API and bind the local Chromium profile."""
    remote_ok = False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.put(
                f"{remote}/amazon-accounts/active",
                headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
                json={"account_id": account_id},
            )
        if r.status_code == 401:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        remote_ok = r.is_success
        if not remote_ok:
            logger.warning(
                "Remote active Amazon account sync failed (HTTP %s); binding local profile anyway.",
                r.status_code,
            )
    except httpx.HTTPError as exc:
        logger.warning("Remote active Amazon account sync unreachable (%s); binding local profile anyway.", exc)
    # La fenêtre de login encore ouverte appartient à l'ancien compte : la fermer, sinon
    # ``GET /session`` lirait son message d'accueil et marquerait le nouveau profil « connecté ».
    await _close_all_amazon_chromium()
    profile = bind_amazon_profile_for(user_id, account_id)
    _reset_amazon_scraper()
    auto_login = await _try_vault_auto_login_if_needed(
        user_id, account_id, raw_token, remote, profile
    )
    return {
        "ok": True,
        "active_account_id": account_id,
        "remote_sync": remote_ok,
        "auto_login": auto_login,
    }


@router.post("/accounts/{account_id}/auto-login")
async def amazon_auto_login_account(
    account_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    """Open Chromium on the account profile and sign in with stored credentials (2FA may still be required)."""
    bind_amazon_profile_for(user_id, account_id)
    _reset_amazon_scraper()
    try:
        email, password = await fetch_account_credentials(raw_token, remote, account_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not load credentials: {exc}",
        ) from exc

    from amazon_nodriver import login_to_amazon

    result = await asyncio.to_thread(login_to_amazon, email, password)
    if result.get("success"):
        _write_session_marker()
    return {
        "success": bool(result.get("success")),
        "message": str(result.get("message") or ""),
        "active_account_id": account_id,
    }


async def _amazon_register_chrome(
    email: str, password: str, customer_name: str = "GoupixDex"
) -> dict[str, object]:
    await _close_all_amazon_chromium()
    from amazon_nodriver import register_to_amazon

    result = await asyncio.to_thread(register_to_amazon, email, password, customer_name)
    email_prefilled = bool(result.get("email_prefilled"))
    success = bool(result.get("success")) and email_prefilled
    return {
        "success": success,
        "email_prefilled": email_prefilled,
        "message": str(result.get("message") or ""),
        "url": str(result.get("url") or ""),
    }


@router.post("/provision/open-register")
async def amazon_provision_open_register(
    body: AmazonProvisionRegisterBody,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    """Ouvre Chrome et préremplit l’e-mail — **sans** compte enregistré sur l’API."""
    email = body.email.strip()
    if not email or not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email et mot de passe requis.",
        )
    bind_provision_staging_profile(user_id)
    _reset_amazon_scraper()
    logger.info("Amazon provision open-register user_id=%s email=%s…", user_id, email[:8])
    out = await _amazon_register_chrome(email, body.password, body.customer_name)
    out["email"] = email
    return out


@router.post("/provision/discard")
async def amazon_provision_discard(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    discard_provision_staging_profile(user_id)
    return {"discarded": True}


@router.post("/provision/fill-email-verification-code")
async def amazon_provision_fill_email_code(
    body: AmazonProvisionEmailCodeBody,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    del user_id
    from amazon_nodriver import fill_amazon_email_verification_code

    result = await asyncio.to_thread(fill_amazon_email_verification_code, body.code.strip())
    return {
        "success": bool(result.get("success")),
        "message": str(result.get("message") or ""),
    }


@router.post("/provision/fill-cvf-phone")
async def amazon_provision_fill_cvf_phone(
    body: AmazonProvisionPhoneBody,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    del user_id
    from amazon_nodriver import fill_amazon_cvf_phone

    result = await asyncio.to_thread(fill_amazon_cvf_phone, body.phone_e164.strip())
    return {
        "success": bool(result.get("success")),
        "message": str(result.get("message") or ""),
    }


@router.post("/provision/receive-sms/allocate")
async def amazon_provision_receive_sms_allocate(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    count: int = 1,
) -> dict[str, object]:
    del user_id
    from services.receive_sms_cc_catalog import allocate_clean_canada_inboxes

    try:
        items = await asyncio.to_thread(
            allocate_clean_canada_inboxes,
            max(1, min(10, int(count))),
        )
    except Exception as exc:
        return {"ok": False, "message": str(exc), "inboxes": []}
    return {
        "ok": True,
        "message": f"{len(items)} numéro(s) Canada (receive-sms.cc) sans Amazon visible.",
        "inboxes": [
            {
                "inbox_url": i.inbox_url,
                "phone_e164": i.phone_e164,
                "message_count": i.message_count,
            }
            for i in items
        ],
    }


@router.get("/provision/receive-sms/inbox")
async def amazon_provision_receive_sms_inbox(
    url: str,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    del user_id
    from services.receive_sms_cc_fetch import fetch_receive_sms_cc_html
    from services.receive_sms_cc_parser import (
        amazon_history_on_inbox,
        latest_amazon_otp,
        parse_receive_sms_cc_html,
    )

    try:
        html = await asyncio.to_thread(fetch_receive_sms_cc_html, url.strip())
    except Exception as exc:
        return {"ok": False, "message": str(exc), "amazon_history": False, "code": None, "message_count": 0}
    messages = parse_receive_sms_cc_html(html)
    code = latest_amazon_otp(messages)
    return {
        "ok": True,
        "amazon_history": amazon_history_on_inbox(messages),
        "code": code,
        "message_count": len(messages),
        "message": "OK",
    }


@router.post("/accounts/{account_id}/claim-staging-profile")
async def amazon_claim_staging_profile(
    account_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    claim_provision_staging_profile(user_id, account_id)
    bind_amazon_profile_for(user_id, account_id)
    return {"ok": True, "active_account_id": account_id}


@router.post("/accounts/{account_id}/open-register")
async def amazon_open_register_account(
    account_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    """Bind profile, pre-fill Amazon registration in Chrome with vault credentials."""
    bind_amazon_profile_for(user_id, account_id)
    _reset_amazon_scraper()
    try:
        email, password = await fetch_account_credentials(raw_token, remote, account_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not load credentials: {exc}",
        ) from exc

    logger.info("Amazon open-register account_id=%s email=%s…", account_id, email[:8])
    out = await _amazon_register_chrome(email, password)
    logger.info(
        "Amazon open-register done account_id=%s email_prefilled=%s success=%s",
        account_id,
        out.get("email_prefilled"),
        out.get("success"),
    )
    out["active_account_id"] = account_id
    return out


@router.get("/invites")
async def amazon_invites_list(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
    q: Annotated[str | None, Query(description="Optional Amazon-side search query")] = None,
    max_pages: Annotated[int, Query(ge=1, le=50, description="Number of result pages to scan")] = 2,
) -> dict[str, object]:
    key = _invites_cache_key(user_id, active_account_id)
    return {
        "items": list(_invites_cache.get(key, [])),
        "refreshed_at": _refreshed_at.get(key),
        "params": {"q": _norm_q(q), "max_pages": max_pages},
        "active_account_id": active_account_id,
    }


@router.post("/invites/refresh")
async def amazon_invites_refresh(
    _lock: Annotated[None, Depends(hold_invites_lock)],
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
    body: AmazonRefreshBody,
) -> dict[str, object]:
    cache_key = _invites_cache_key(user_id, active_account_id)

    qn = _norm_q(body.q)
    query_arg = qn if qn else ""
    loop = asyncio.get_running_loop()

    try:
        max_items = body.max_items
        scan_pages = _resolve_invite_scan_pages(body.max_pages, max_items, query_arg)
        search_rows = await asyncio.to_thread(
            _run_search_with_progress,
            query_arg,
            scan_pages,
            loop,
            max_items,
        )
        if max_items is not None and max_items > 0:
            search_rows = search_rows[: int(max_items)]
        _catalog_search_rows[user_id] = [dict(x) for x in search_rows]
        merged_rows: list[dict[str, Any]] = list(search_rows)
        asins_ordered: list[str] = []
        seen_asin: set[str] = set()
        for x in search_rows:
            a = str(x.get("asin") or "").strip().upper()
            if a and a not in seen_asin:
                seen_asin.add(a)
                asins_ordered.append(a)
                if max_items is not None and len(asins_ordered) >= int(max_items):
                    break
        if asins_ordered and body.check_statuses:
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

    invite_rows = [_integration_item_to_goupix_invite(x) for x in merged_rows]
    if max_items is not None and max_items > 0:
        invite_rows = invite_rows[: int(max_items)]
    _invites_cache[cache_key] = invite_rows
    refreshed_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _refreshed_at[cache_key] = refreshed_iso

    n = len(_invites_cache[cache_key])
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
        "items": list(_invites_cache[cache_key]),
        "refreshed_at": refreshed_iso,
        "message": msg,
        "params": {
            "q": qn,
            "max_pages": scan_pages,
            "max_items": max_items,
        },
        "active_account_id": active_account_id,
    }


@router.post("/invites/reverify")
async def amazon_invites_reverify(
    _lock: Annotated[None, Depends(hold_invites_lock)],
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
    body: AmazonReverifyBody,
) -> dict[str, object]:
    """
    Re-run product-page checks for the active account without a new search.
    Uses the request body or the last in-memory search catalog for this user.
    """
    cache_key = _invites_cache_key(user_id, active_account_id)
    search_rows = _goupix_invites_to_search_rows(body.items)
    if not search_rows:
        search_rows = [dict(x) for x in _catalog_search_rows.get(user_id, [])]
    if not search_rows:
        cached = list(_invites_cache.get(cache_key, []))
        return {
            "items": cached,
            "refreshed_at": _refreshed_at.get(cache_key),
            "message": "Aucun produit à revérifier — lancez d’abord une actualisation.",
            "active_account_id": active_account_id,
        }

    asins_ordered: list[str] = []
    seen_asin: set[str] = set()
    for x in search_rows:
        a = str(x.get("asin") or "").strip().upper()
        if a and a not in seen_asin:
            seen_asin.add(a)
            asins_ordered.append(a)

    loop = asyncio.get_running_loop()
    try:
        checked_rows = await asyncio.to_thread(
            _run_check_invites_with_progress,
            asins_ordered,
            loop,
        )
        merged_rows = _merge_search_rows_with_checked(search_rows, checked_rows)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Amazon invites reverify")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Amazon status check failed: {exc}",
        ) from exc

    _invites_cache[cache_key] = [_integration_item_to_goupix_invite(x) for x in merged_rows]
    refreshed_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _refreshed_at[cache_key] = refreshed_iso
    n = len(_invites_cache[cache_key])
    return {
        "items": list(_invites_cache[cache_key]),
        "refreshed_at": refreshed_iso,
        "message": f"Statuts mis à jour pour {n} produit(s) sur ce compte.",
        "active_account_id": active_account_id,
    }


@router.post("/invites/verify-all")
async def amazon_invites_verify_all(
    _lock: Annotated[None, Depends(hold_invites_lock)],
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
    body: AmazonReverifyBody,
) -> dict[str, object]:
    """
    Même catalogue vérifié sur chaque compte du coffre, l'un après l'autre, avec un scraper
    épinglé par compte (cookies du compte, jamais de Chrome). Une liste de lignes par compte.
    """
    search_rows = _goupix_invites_to_search_rows(body.items)
    if not search_rows:
        search_rows = [dict(x) for x in _catalog_search_rows.get(user_id, [])]
    if not search_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun produit à vérifier — lancez d’abord une actualisation.",
        )

    asins_ordered: list[str] = []
    seen_asin: set[str] = set()
    for x in search_rows:
        a = str(x.get("asin") or "").strip().upper()
        if a and a not in seen_asin:
            seen_asin.add(a)
            asins_ordered.append(a)

    try:
        account_ids = await fetch_vault_account_ids(raw_token, remote)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Liste des comptes Amazon injoignable : {exc}",
        ) from exc
    if not account_ids and active_account_id is not None:
        account_ids = [active_account_id]
    if not account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun compte Amazon dans le coffre.",
        )

    loop = asyncio.get_running_loop()
    rows_by_account: dict[str, list[dict[str, object]]] = {}
    account_states: dict[str, str] = {}
    errors: dict[str, str] = {}
    total = len(account_ids)
    for index, account_id in enumerate(account_ids, start=1):
        scope: dict[str, Any] = {
            "account_id": account_id,
            "account_index": index,
            "account_total": total,
        }
        try:
            await _broadcast_amazon_progress(
                {
                    "status": "connecting",
                    "message": f"Compte {index}/{total} — ouverture de Chrome et vérification de la connexion…",
                    **scope,
                }
            )
        except Exception:  # noqa: BLE001
            pass
        await _close_all_amazon_chromium()
        bind_amazon_profile_for(user_id, account_id)
        _reset_amazon_scraper()
        scraper = _browser_scraper()
        try:
            await _ensure_account_signed_in(user_id, account_id, raw_token, remote, scraper)
            account_states[str(account_id)] = "ready"
            try:
                await _broadcast_amazon_progress(
                    {
                        "status": "checking_phase",
                        "message": f"Compte {index}/{total} connecté — vérification de {len(asins_ordered)} fiche(s)…",
                        "total_pages": len(asins_ordered),
                        "current_page": 0,
                        **scope,
                    }
                )
            except Exception:  # noqa: BLE001
                pass
            checked_rows = await asyncio.to_thread(
                _run_check_invites_with_progress,
                asins_ordered,
                loop,
                scraper,
                scope,
            )
            rows = [
                _integration_item_to_goupix_invite(x)
                for x in _merge_search_rows_with_checked(search_rows, checked_rows)
            ]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Amazon verify-all account %s", account_id)
            errors[str(account_id)] = str(exc)
            account_states[str(account_id)] = "needs_login"
            # Fiches du catalogue marquées « compte non connecté » pour ce compte, sans deviner.
            rows = [
                _integration_item_to_goupix_invite({**x, "invitation_status": "needs_login"})
                for x in search_rows
            ]
            try:
                await _broadcast_amazon_progress(
                    {"status": "error", "message": f"Compte {index}/{total} : {exc}", **scope}
                )
            except Exception:  # noqa: BLE001
                pass
        finally:
            await _close_all_amazon_chromium()

        key = _invites_cache_key(user_id, account_id)
        _invites_cache[key] = rows
        _refreshed_at[key] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        rows_by_account[str(account_id)] = rows
        if account_states.get(str(account_id)) == "ready":
            try:
                await _broadcast_amazon_progress(
                    {
                        "status": "account_done",
                        "message": f"Compte {index}/{total} : {len(rows)} produit(s) vérifié(s).",
                        "items_found": len(rows),
                        **scope,
                    }
                )
            except Exception:  # noqa: BLE001
                pass

    # Revenir au profil du compte actif pour les requêtes suivantes.
    bind_amazon_profile_for(user_id, active_account_id)
    _reset_amazon_scraper()

    refreshed_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ready_count = sum(1 for s in account_states.values() if s == "ready")
    summary = f"{ready_count}/{total} compte(s) connecté(s), statuts vérifiés."
    try:
        await _broadcast_amazon_progress(
            {"status": "completed", "message": summary, "items_found": len(asins_ordered)}
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "rows_by_account": rows_by_account,
        "account_ids": account_ids,
        "account_states": account_states,
        "refreshed_at": refreshed_iso,
        "active_account_id": active_account_id,
        "errors": errors,
        "message": summary,
    }


@router.post("/invites/request")
async def amazon_invites_request(
    _lock: Annotated[None, Depends(hold_invites_lock)],
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    active_account_id: Annotated[int | None, Depends(bind_active_amazon_profile)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
    body: AmazonRequestInviteBody,
) -> dict[str, object]:
    """
    Demande l'invitation pour un ASIN depuis ``body.account_id`` : Chrome sur le profil de ce compte
    (connexion auto si besoin) et clic sur le bouton, puis mise à jour de la ligne dans son cache.
    Sans ``account_id`` : ancien chemin HTTP sur le profil actif.
    """
    target_account_id = body.account_id if body.account_id is not None else active_account_id
    cache_key = _invites_cache_key(user_id, target_account_id)

    asin = body.asin
    try:
        if body.account_id is None:
            result = await asyncio.to_thread(_get_amazon_scraper().request_invitation_for_asin, asin)
        else:
            await _close_all_amazon_chromium()
            bind_amazon_profile_for(user_id, body.account_id)
            _reset_amazon_scraper()
            scraper = _browser_scraper()
            try:
                await _ensure_account_signed_in(user_id, body.account_id, raw_token, remote, scraper)
                result = await asyncio.to_thread(scraper.request_invitation_via_browser, asin)
            except RuntimeError as exc:
                result = {"success": False, "message": str(exc)}
            finally:
                await _close_all_amazon_chromium()
                bind_amazon_profile_for(user_id, active_account_id)
                _reset_amazon_scraper()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Amazon request invitation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Worker error: {exc}",
        ) from exc

    if not result.get("success"):
        return {
            "success": False,
            "message": str(result.get("message") or "La demande a échoué."),
            "account_id": target_account_id,
        }

    raw_item = result.get("item")
    goupix: dict[str, object] | None = None
    if isinstance(raw_item, dict):
        goupix = _integration_item_to_goupix_invite(raw_item)
        rows = list(_invites_cache.get(cache_key, []))
        new_cache: list[dict[str, object]] = []
        replaced = False
        for row in rows:
            r_asin = str(row.get("asin") or "").strip().upper()
            if r_asin == asin:
                new_cache.append(goupix)
                replaced = True
            else:
                new_cache.append(dict(row))
        if replaced:
            _invites_cache[cache_key] = new_cache

    return {
        "success": True,
        "message": str(result.get("message") or "Invitation demandée."),
        "invite": goupix,
        "account_id": target_account_id,
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


_WS_JWT_SUBPROTOCOL_PREFIX = "goupix-jwt."


def _token_from_ws_subprotocols(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract the JWT from a ``goupix-jwt.<token>`` subprotocol entry.

    Returns ``(token, subprotocol)`` so ``accept()`` can echo the selected
    subprotocol back (browsers drop the connection otherwise).
    """
    header = websocket.headers.get("sec-websocket-protocol", "")
    for entry in header.split(","):
        entry = entry.strip()
        if entry.startswith(_WS_JWT_SUBPROTOCOL_PREFIX):
            token = entry[len(_WS_JWT_SUBPROTOCOL_PREFIX) :]
            if token:
                return token, entry
    return None, None


@app.websocket("/ws/progress")
async def amazon_progress_websocket(websocket: WebSocket) -> None:
    """
    Real-time JSON events during ``POST /amazon/invites/refresh`` (search progress).

    Auth: preferred via the ``goupix-jwt.<token>`` WebSocket subprotocol (keeps the JWT
    out of access logs); the legacy ``?token=JWT`` query param is still accepted.
    ``?remote_api=https://...`` selects the introspection API (same as local workers).
    """
    raw_token, chosen_subprotocol = _token_from_ws_subprotocols(websocket)
    if not raw_token:
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
    await websocket.accept(subprotocol=chosen_subprotocol)
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
