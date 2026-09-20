"""
Local HTTP worker (127.0.0.1): Leboncoin publish / nodriver on the user's PC.

Run from the ``api/`` folder (venv activated)::

    python desktop_leboncoin_server.py

Env: ``GOUPIX_LEBONCOIN_LOCAL_PORT`` (default 18769), ``GOUPIX_REMOTE_API``,
header ``X-Goupix-Remote-Api``.
"""

from __future__ import annotations

import os
import sys

from worker_env_bootstrap import load_worker_dotenv

load_worker_dotenv()

import asyncio
import hashlib
import json
import logging
import time
from typing import Annotated

import httpx
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.deps import get_bearer_or_query_token
from core.win32_asyncio import ensure_proactor_event_loop
from services.desktop_leboncoin_runner_service import DesktopLeboncoinRunnerService
from services.leboncoin_profile_session_service import detect_leboncoin_session_from_profile
from services.os_service import resolve_leboncoin_nodriver_user_data_dir
from services.vinted_progress_session_service import VintedProgressSessionService as progress_hub

ensure_proactor_event_loop()


def _resolve_log_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "GoupixDex", "logs")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Logs", "GoupixDex")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "GoupixDex", "logs")


def _configure_logging() -> None:
    from logging.handlers import RotatingFileHandler

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        log_dir = _resolve_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(log_dir, "leboncoin-worker.log"),
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass


_configure_logging()
logger = logging.getLogger("goupixdex.leboncoin_local")

_INTROSPECT_CACHE_TTL_SEC = 120.0
_introspect_cache: dict[str, tuple[float, int]] = {}


def _introspect_cache_key(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_remote_base_flexible(
    x_goupix_remote_api: Annotated[str | None, Header(alias="X-Goupix-Remote-Api")] = None,
    remote_api: Annotated[str | None, Query(description="URL API distante")] = None,
) -> str:
    for cand in (x_goupix_remote_api, remote_api, os.environ.get("GOUPIX_REMOTE_API", "")):
        if cand and str(cand).strip():
            return str(cand).strip().rstrip("/")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Remote API URL required (X-Goupix-Remote-Api, remote_api, or GOUPIX_REMOTE_API).",
    )


async def get_user_id_introspected(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> int:
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Remote API unreachable.")
    uid = int(r.json()["id"])
    _introspect_cache[key] = (now, uid)
    return uid


router = APIRouter(prefix="/articles", tags=["articles-leboncoin-local"])
lbc_router = APIRouter(prefix="/leboncoin", tags=["leboncoin-local"])


@router.post("/{article_id}/publish-leboncoin")
async def publish_leboncoin_for_article(
    article_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    progress_hub.register(article_id)
    asyncio.create_task(
        DesktopLeboncoinRunnerService.run_desktop_leboncoin_publish_job(
            article_id, user_id, raw_token, remote
        )
    )
    return {
        "leboncoin": {
            "status": "running",
            "stream_path": f"/articles/{article_id}/listing-progress",
        },
    }


@router.get("/{article_id}/listing-progress")
async def article_listing_progress_stream(
    article_id: int,
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> StreamingResponse:
    async def generate():
        async for ev in progress_hub.event_stream(article_id):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@lbc_router.get("/meta")
def leboncoin_meta() -> dict[str, str]:
    return {"service": "goupix-leboncoin-worker", "version": "1"}


@lbc_router.get("/session")
def leboncoin_session_state() -> dict[str, str]:
    profile = resolve_leboncoin_nodriver_user_data_dir(os.environ.get("LEBONCOIN_USER_DATA_DIR"))
    state = detect_leboncoin_session_from_profile(profile)
    return {"state": state, "profile_dir": str(profile)}


@lbc_router.post("/open-login")
async def leboncoin_open_login(
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    """Ouvre Chrome sur la page de connexion Leboncoin (profil persistant)."""
    from services.leboncoin_service import LeboncoinService

    try:
        return await LeboncoinService.open_login_browser()
    except Exception as exc:  # noqa: BLE001
        logger.exception("leboncoin open-login failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


app = FastAPI(title="GoupixDex Leboncoin local worker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(lbc_router)


def main() -> None:
    port = int(os.environ.get("GOUPIX_LEBONCOIN_LOCAL_PORT", "18769"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
