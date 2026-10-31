"""Public scan index complements: cards the shipped indexes lack (``/scan-index/phash-delta``, ``/scan-index/embed-delta``)."""

from __future__ import annotations

import gzip
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from services.scan_embed_index_service import scan_embed_delta
from services.scan_phash_index_service import scan_phash_delta_payload

router = APIRouter(prefix="/scan-index", tags=["scan"])


@router.get("/phash-delta")
def get_scan_phash_delta(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    """Fingerprints computed overnight for cards missing from ``web/public/scan-index`` (public card data)."""
    return JSONResponse(scan_phash_delta_payload(db), headers={"Cache-Control": "public, max-age=900"})


@router.get("/embed-delta")
def get_scan_embed_delta(request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    """Embeddings computed overnight for cards missing from ``web/public/scan-index/embed-v3`` (public card data, several MB: gzip + ETag)."""
    delta = scan_embed_delta(db)
    headers = {"Cache-Control": "public, max-age=900", "ETag": delta.etag, "Vary": "Accept-Encoding"}
    if request.headers.get("if-none-match") == delta.etag:
        return Response(status_code=304, headers=headers)
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(delta.gzip_body, media_type="application/json", headers={**headers, "Content-Encoding": "gzip"})
    return Response(gzip.decompress(delta.gzip_body), media_type="application/json", headers=headers)
