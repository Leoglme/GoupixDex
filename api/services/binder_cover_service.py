"""Binder custom cover images (Supabase Storage)."""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status

from services import supabase_storage_service

MAX_COVER_BYTES = 3 * 1024 * 1024
ALLOWED_TYPES = {"image/webp", "image/jpeg", "image/png"}

_PATH_RE = re.compile(r"^\d+/covers/\d+/[a-f0-9-]+\.(webp|jpe?g|png)$", re.I)


def cover_path_prefix(user_id: int, binder_id: int) -> str:
    return f"{user_id}/covers/{binder_id}/"


def validate_cover_paths(user_id: int, binder_id: int, paths: list[str]) -> None:
    prefix = cover_path_prefix(user_id, binder_id)
    for p in paths:
        if not p.startswith(prefix) or not _PATH_RE.match(p):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image de couverture non autorisée")


def collect_paths_from_cover(cover: dict[str, Any] | None) -> list[str]:
    if not cover:
        return []
    paths: list[str] = []
    bg = cover.get("bg")
    if isinstance(bg, dict):
        img = bg.get("image")
        if isinstance(img, str) and img.strip():
            paths.append(img.strip())
    zones = cover.get("zones")
    if isinstance(zones, dict):
        for el in zones.values():
            if isinstance(el, dict) and el.get("type") == "image":
                p = el.get("path")
                if isinstance(p, str) and p.strip():
                    paths.append(p.strip())
    return list(dict.fromkeys(paths))


async def upload_cover_image(user_id: int, binder_id: int, upload: UploadFile) -> dict[str, str]:
    if not supabase_storage_service.is_configured():
        raise HTTPException(status_code=503, detail="Stockage images indisponible")
    content_type = (upload.content_type or "").strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Format non accepté : {content_type or 'inconnu'}")
    raw = await upload.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Aucune image à envoyer")
    if len(raw) > MAX_COVER_BYTES:
        raise HTTPException(status_code=400, detail="Image trop lourde (max 3 Mo)")

    ext = Path(upload.filename or "cover.webp").suffix.lower()
    if ext not in (".webp", ".jpg", ".jpeg", ".png"):
        ext = ".webp" if content_type == "image/webp" else ".jpg" if "jpeg" in content_type else ".png"
    object_path = f"{cover_path_prefix(user_id, binder_id)}{uuid.uuid4().hex}{ext}"

    def _do_upload() -> str:
        return supabase_storage_service.upload_at_path_sync(
            object_path=object_path,
            data=raw,
            content_type=content_type,
        )

    url = await asyncio.to_thread(_do_upload)
    return {"path": object_path, "url": url}


def resolve_cover_urls(paths: list[str]) -> dict[str, str]:
    if not supabase_storage_service.is_configured():
        return {}
    out: dict[str, str] = {}
    for p in paths:
        if p and p not in out:
            try:
                out[p] = supabase_storage_service.public_url_for_path(p)
            except RuntimeError:
                continue
    return out
