"""Public scan index complement: ``GET /scan-index/phash-delta`` lists cards the shipped index lacks."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from services.scan_phash_index_service import scan_phash_delta_payload

router = APIRouter(prefix="/scan-index", tags=["scan"])


@router.get("/phash-delta")
def get_scan_phash_delta(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    """Fingerprints computed overnight for cards missing from ``web/public/scan-index`` (public card data)."""
    return JSONResponse(scan_phash_delta_payload(db), headers={"Cache-Control": "public, max-age=900"})
