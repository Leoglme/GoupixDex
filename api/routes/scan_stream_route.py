"""
Live scan stream: phone uploads a card photo, every desktop/tab listening on
``/ws/scan-stream`` for the same user sees the card pop into the binder in
real time.

* ``POST /scan-stream/photo`` — multipart upload, returns ``{ event_id }``
  immediately while a background task does OCR + TCGdex lookup + insert.
* ``GET  /scan-stream/recent`` — backlog used by the page on mount so the
  user sees the last batch of scans without waiting for new ones.
* ``WS   /ws/scan-stream`` — user-scoped channel; JWT in the ``token`` query
  string (browsers don't allow ``Authorization`` headers on ``WebSocket``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    status,
)
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from core.database import get_db
from core.deps import get_current_user, get_current_user_from_token_str
from models.user import User
from services.scan_stream_hub import get_scan_stream_hub
from services.scan_stream_service import submit_scan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan-stream"])

#: Hard upload cap so a misbehaving phone (or attacker) can't ship 50 MB photos.
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


_MIME_BY_SUFFIX: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _resolve_mime(upload: UploadFile) -> str:
    """Trust the client mime when usable, else fall back to the filename suffix."""
    declared = (upload.content_type or "").strip().lower()
    if declared in {"image/jpeg", "image/png", "image/webp"}:
        return declared
    suffix = Path(upload.filename or "").suffix.lower()
    return _MIME_BY_SUFFIX.get(suffix, "image/jpeg")


def _clean_language(value: str | None) -> str:
    """``auto`` (or anything unknown / empty) → server-side OCR detection."""
    raw = (value or "").strip().lower()
    if raw in {"fr", "en", "ja"}:
        return raw
    return "auto"


def _clean_hint(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.strip().split())
    if not text:
        return None
    return text[:500]


@router.post("/scan-stream/photo", status_code=status.HTTP_202_ACCEPTED)
async def upload_scan_photo(
    user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File(description="Photo de la carte (JPEG / PNG / WebP)")],
    language: Annotated[
        str, Form(description="Langue physique : auto (détection OCR) | fr | en | ja")
    ] = "auto",
    hint: Annotated[str | None, Form(description="Indice optionnel pour l'OCR")] = None,
) -> dict[str, Any]:
    """
    Accept one card photo, enqueue the OCR + TCGdex + insert pipeline, and
    return an ``event_id``. The phone can fire-and-forget; the desktop UI
    receives the same ``event_id`` over the WebSocket as the scan progresses.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image trop volumineuse ({len(data) // 1024} ko, max {_MAX_UPLOAD_BYTES // 1024} ko).",
        )

    mime = _resolve_mime(file)
    physical_language = _clean_language(language)
    user_hint = _clean_hint(hint)

    event_id = submit_scan(
        user_id=user.id,
        image_bytes=data,
        filename=file.filename or "scan.jpg",
        mime=mime,
        physical_language=physical_language,
        user_hint=user_hint,
    )

    return {
        "event_id": event_id,
        "status": "queued",
        "physical_language": physical_language,
    }


@router.get("/scan-stream/recent")
def list_recent_scans(
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
) -> dict[str, Any]:
    """Last N events in this process for the current user (post-reload replay)."""
    hub = get_scan_stream_hub()
    events = hub.history_snapshot(user.id, limit=max(1, min(int(limit), 100)))
    return {"items": events}


@router.delete("/scan-stream/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_scan_event(
    event_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove one scan event from the live backlog (does not delete collection rows)."""
    hub = get_scan_stream_hub()
    if not hub.dismiss_event(user.id, event_id.strip()):
        raise HTTPException(status_code=404, detail="Événement introuvable.")


@router.delete("/scan-stream/events")
def clear_scan_events(
    user: Annotated[User, Depends(get_current_user)],
    filter: Annotated[
        str,
        Query(description="failed | needs_review | problems (failed + needs_review)"),
    ] = "problems",
) -> dict[str, Any]:
    """
    Bulk-remove scan events from the backlog.

    Does not touch cards already inserted in the collection — only the scan feed.
    """
    hub = get_scan_stream_hub()
    key = filter.strip().lower()
    if key in {"failed", "echec", "échec"}:
        statuses = {"failed"}
    elif key in {"needs_review", "review", "a_verifier", "à_vérifier"}:
        statuses = {"needs_review"}
    elif key in {"problems", "problem", "issues"}:
        statuses = {"failed", "needs_review"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Filtre invalide. Utilisez problems, failed ou needs_review.",
        )
    removed = hub.clear_events(user.id, statuses=statuses)
    return {"removed": removed}


@router.get("/scan-stream/health")
def scan_stream_health() -> dict[str, Any]:
    """Lightweight probe — confirms the scan-stream router is deployed."""
    return {"ok": True, "websocket_paths": ["/ws/scan-stream", "/scan-stream/ws"]}


async def _scan_stream_socket_impl(ws: WebSocket, db: Session) -> None:
    try:
        user = get_current_user_from_token_str(
            raw_token=ws.query_params.get("token", ""),
            db=db,
        )
    except HTTPException as exc:
        await ws.close(code=4401, reason=str(exc.detail))
        return

    hub = get_scan_stream_hub()
    backlog = await hub.connect(user.id, ws)

    try:
        for past in backlog:
            await ws.send_json(past)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("scan-stream socket crashed (user=%s)", user.id)
    finally:
        await hub.disconnect(user.id, ws)


@router.websocket("/ws/scan-stream")
async def scan_stream_socket(
    ws: WebSocket,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """
    Authenticated WebSocket. The browser cannot send custom headers on
    ``WebSocket``, so the JWT travels in ``?token=<jwt>``.
    """
    await _scan_stream_socket_impl(ws, db)


@router.websocket("/scan-stream/ws")
async def scan_stream_socket_alias(
    ws: WebSocket,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Alias for nginx configs that only proxy ``/scan-stream/*``."""
    await _scan_stream_socket_impl(ws, db)
