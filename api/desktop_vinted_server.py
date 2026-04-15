"""
Worker HTTP local (127.0.0.1) : publication Vinted / nodriver sur le PC utilisateur.

Les métadonnées et le JWT sont lus sur l’API distante ; Chrome et nodriver tournent ici.

Lancer depuis le dossier ``api/`` (venv activé) ::

    python desktop_vinted_server.py

Variables utiles : ``GOUPIX_VINTED_LOCAL_PORT`` (défaut 18766), ``GOUPIX_REMOTE_API`` (URL API si
le client n’envoie pas ``X-Goupix-Remote-Api``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Annotated

import httpx
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.deps import get_bearer_or_query_token
from core.win32_asyncio import ensure_proactor_event_loop
from schemas.articles import VintedBatchStartBody
from services import vinted_batch_progress as vinted_batch_hub
from services import vinted_progress as vinted_progress_hub
from services.desktop_vinted_runner import run_desktop_vinted_batch_job, run_desktop_vinted_publish_job

ensure_proactor_event_loop()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("goupixdex.vinted_local")

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


async def get_user_id_introspected(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> int:
    """Valide le JWT via l’API distante (pas besoin du secret JWT en local)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{remote}/users/me",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not r.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de joindre l’API distante pour valider la session.",
        )
    return int(r.json()["id"])


router = APIRouter(prefix="/articles", tags=["articles-vinted-local"])


@router.post("/{article_id}/publish-vinted")
async def publish_vinted_for_article(
    article_id: int,
    user_id: Annotated[int, Depends(get_user_id_introspected)],
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    remote: Annotated[str, Depends(get_remote_base_flexible)],
) -> dict[str, object]:
    vinted_progress_hub.register(article_id)
    asyncio.create_task(run_desktop_vinted_publish_job(article_id, user_id, raw_token, remote))
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
        run_desktop_vinted_batch_job(job_id, user_id, unique_ids, raw_token, remote),
    )
    return {
        "job_id": job_id,
        "stream_path": f"/articles/vinted-batch/{job_id}/stream",
    }


app = FastAPI(title="GoupixDex Vinted local", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "goupixdex-vinted-local"}


if __name__ == "__main__":
    from core.nodriver_uvicorn_loop import UVICORN_WINDOWS_NODRIVER_LOOP

    port = int(os.environ.get("GOUPIX_VINTED_LOCAL_PORT", "18766"))
    loop = UVICORN_WINDOWS_NODRIVER_LOOP if sys.platform == "win32" else "auto"
    uvicorn.run(app, host="127.0.0.1", port=port, loop=loop, log_level="info")
