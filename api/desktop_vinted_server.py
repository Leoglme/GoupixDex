"""
Local HTTP worker (127.0.0.1): Vinted publish / nodriver on the user's PC.

Metadata and JWT are read from the remote API; Chrome and nodriver run here.

Run from the ``api/`` folder (venv activated)::

    python desktop_vinted_server.py

Useful env vars: ``GOUPIX_VINTED_LOCAL_PORT`` (default 18766), ``GOUPIX_REMOTE_API`` (API URL if
the client does not send ``X-Goupix-Remote-Api``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from typing import Annotated

import httpx
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from urllib.parse import urlparse

from core.deps import get_bearer_or_query_token
from core.win32_asyncio import ensure_proactor_event_loop
from schemas.articles import VintedBatchStartBody
from services.wardrobe_job_store_service import WardrobeJobStoreService as wardrobe_jobs
from services.desktop_vinted_runner_service import DesktopVintedRunnerService
from services.desktop_wardrobe_sync_runner_service import DesktopWardrobeSyncRunnerService
from services.vinted_batch_session_service import VintedBatchSessionService as vinted_batch_hub
from services.vinted_progress_session_service import VintedProgressSessionService as vinted_progress_hub

ensure_proactor_event_loop()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("goupixdex.vinted_local")

_LISTING_IMAGE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
)
_MAX_LISTING_IMAGE_BYTES = 18 * 1024 * 1024


def _allowed_listing_image_host(hostname: str) -> bool:
    h = hostname.lower()
    if h.endswith(".vinted.net"):
        return True
    if "imagedelivery.net" in h:
        return True
    if h.endswith("vinted.fr") or h.endswith("vinted.co.uk") or h.endswith("vinted.com"):
        return True
    return False


try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def get_remote_base_flexible(
    x_goupix_remote_api: Annotated[str | None, Header(alias="X-Goupix-Remote-Api")] = None,
    remote_api: Annotated[str | None, Query(description="URL API (SSE / EventSource)")] = None,
) -> str:
    for cand in (x_goupix_remote_api, remote_api, os.environ.get("GOUPIX_REMOTE_API", "")):
        if cand and str(cand).strip():
            return str(cand).strip().rstrip("/")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "URL API distante requise (header X-Goupix-Remote-Api, query remote_api ou GOUPIX_REMOTE_API)."
        ),
    )


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


async def get_user_id_introspected(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> int:
    """Valide le JWT via l'API distante (pas besoin du secret JWT en local).

    Mise en cache courte : le polling ``GET /vinted/wardrobe-sync/jobs/…`` ne doit pas
    appeler ``/users/me`` toutes les 2 s (bruit logs + charge API).
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
            detail="Impossible de joindre l'API distante pour valider la session.",
        )
    uid = int(r.json()["id"])
    _introspect_cache[key] = (now, uid)
    _prune_introspect_cache(now)
    return uid


router = APIRouter(prefix="/articles", tags=["articles-vinted-local"])
wardrobe_router = APIRouter(prefix="/vinted/wardrobe-sync", tags=["vinted-wardrobe-local"])


@router.post("/{article_id}/publish-vinted")
async def publish_vinted_for_article(
    article_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    vinted_progress_hub.register(article_id)
    asyncio.create_task(
        DesktopVintedRunnerService.run_desktop_vinted_publish_job(article_id, user_id, raw_token, remote)
    )
    return {
        "vinted": {
            "status": "running",
            "stream_path": f"/articles/{article_id}/vinted-progress",
        },
    }


@router.get("/{article_id}/vinted-progress")
async def vinted_progress_stream(
    article_id: int,
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> StreamingResponse:
    async def generate():
        async for ev in vinted_progress_hub.event_stream(article_id):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/vinted-batch/active")
async def vinted_batch_active(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    jid = vinted_batch_hub.get_active_job_id(user_id)
    return {
        "job_id": jid,
        "stream_path": f"/articles/vinted-batch/{jid}/stream" if jid else None,
    }


@router.get("/vinted-batch/{job_id}/stream")
async def vinted_batch_stream(
    job_id: str,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> StreamingResponse:
    owner = vinted_batch_hub.get_job_user_id(job_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    if owner != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé à ce job.")

    async def generate():
        async for ev in vinted_batch_hub.event_stream(job_id):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/vinted-batch", status_code=status.HTTP_202_ACCEPTED)
async def start_vinted_batch(
    body: VintedBatchStartBody,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    unique_ids = list(dict.fromkeys(body.article_ids))
    job_id = str(uuid.uuid4())
    if not vinted_batch_hub.try_register_job(job_id, user_id):
        raise HTTPException(
            status_code=409,
            detail="Une publication Vinted groupée est déjà en cours pour ce compte.",
        )
    asyncio.create_task(
        DesktopVintedRunnerService.run_desktop_vinted_batch_job(
            job_id, user_id, unique_ids, raw_token, remote
        ),
    )
    return {
        "job_id": job_id,
        "stream_path": f"/articles/vinted-batch/{job_id}/stream",
    }


async def _wardrobe_job_task(
    job_id: str,
    user_id: int,
    token: str,
    remote: str,
) -> None:
    await wardrobe_jobs.set_running(job_id)
    try:
        payload = await DesktopWardrobeSyncRunnerService.run_desktop_wardrobe_sync_for_user(
            token, remote, job_id=job_id
        )
        await wardrobe_jobs.set_done(job_id, payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("wardrobe sync job_id=%s", job_id)
        await wardrobe_jobs.set_error(job_id, str(exc))


@wardrobe_router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def wardrobe_sync_start_job(
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    await wardrobe_jobs.create_job(job_id, user_id)
    asyncio.create_task(_wardrobe_job_task(job_id, user_id, raw_token, remote))
    return {"job_id": job_id}


@wardrobe_router.get("/jobs/{job_id}/stream")
async def wardrobe_sync_job_stream(
    job_id: str,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> StreamingResponse:
    """SSE : journal texte + ``done`` avec ``result`` ou ``error`` (comme publication Vinted)."""

    async def generate():
        last_i = 0
        while True:
            row = wardrobe_jobs.get_job(job_id)
            if row is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job introuvable'})}\n\n"
                return
            if int(row["user_id"]) != user_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Accès refusé'})}\n\n"
                return
            logs = row.get("logs") or []
            while last_i < len(logs):
                yield f"data: {json.dumps({'type': 'log', 'message': logs[last_i]})}\n\n"
                last_i += 1
            st = row.get("status")
            if st == "done":
                yield f"data: {json.dumps({'type': 'done', 'result': row.get('result')})}\n\n"
                return
            if st == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': row.get('error') or 'Erreur'})}\n\n"
                return
            await asyncio.sleep(0.28)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@wardrobe_router.get("/listing-image")
async def wardrobe_listing_image_proxy(
    url: Annotated[str, Query(min_length=12, max_length=2048)],
    _: Annotated[int, Depends(get_user_id_introspected)],
) -> Response:
    """Proxy CDN Vinted pour l’app desktop (évite CORS ``fetch`` depuis le WebView)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL invalide.")
    if not _allowed_listing_image_host(parsed.hostname):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hôte image non autorisé.")
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        r = await client.get(
            url,
            headers={
                "User-Agent": _LISTING_IMAGE_UA,
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            },
        )
    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Téléchargement image impossible.",
        )
    if len(r.content) > _MAX_LISTING_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image trop volumineuse.")
    ct_raw = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
    if not ct_raw.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La ressource n’est pas une image.",
        )
    return Response(content=r.content, media_type=ct_raw)


@wardrobe_router.get("/jobs/{job_id}")
async def wardrobe_sync_job_status(
    job_id: str,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
) -> dict[str, object]:
    row = wardrobe_jobs.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    if int(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé à ce job.")
    out: dict[str, object] = {"status": row["status"]}
    if row.get("error"):
        out["error"] = row["error"]
    if row.get("result") is not None:
        out["result"] = row["result"]
    return out


app = FastAPI(title="GoupixDex Vinted local", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(wardrobe_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "goupixdex-vinted-local"}


if __name__ == "__main__":
    from core.nodriver_uvicorn_loop import UVICORN_WINDOWS_NODRIVER_LOOP

    port = int(os.environ.get("GOUPIX_VINTED_LOCAL_PORT", "18766"))
    loop = UVICORN_WINDOWS_NODRIVER_LOOP if sys.platform == "win32" else "auto"
    uvicorn.run(app, host="127.0.0.1", port=port, loop=loop, log_level="info")
