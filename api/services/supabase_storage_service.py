"""Upload images to Supabase Storage (S3-compatible API, service role key on the server)."""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any

try:
    from supabase import Client, create_client
except ImportError as _supabase_import_error:  # pragma: no cover
    Client = Any  # type: ignore[misc, assignment]
    create_client = None  # type: ignore[assignment, misc]
    _SUPABASE_IMPORT_ERROR = _supabase_import_error
else:
    _SUPABASE_IMPORT_ERROR = None

from config import AppSettings, get_settings

_client: Client | None = None


def is_configured(settings: AppSettings | None = None) -> bool:
    """True when URL, API key (service role), and bucket name are set."""
    if create_client is None:
        return False
    s = settings or get_settings()
    return bool(
        (s.supabase_url or "").strip()
        and (s.supabase_api_key or "").strip()
        and (s.supabase_storage_bucket or "").strip(),
    )


def _get_client() -> Client:
    global _client
    if create_client is None:
        raise RuntimeError(
            "The Python package `supabase` is missing. Install it with "
            "`pip install 'supabase>=2'` or rebuild the Docker image "
            "(`docker compose build --no-cache api`).",
        ) from _SUPABASE_IMPORT_ERROR
    if _client is not None:
        return _client
    s = get_settings()
    url = (s.supabase_url or "").strip()
    key = (s.supabase_api_key or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase URL or API key missing")
    _client = create_client(url, key)
    return _client


def _guess_content_type(filename: str | None, fallback_ext: str) -> str:
    name = filename or f"x{fallback_ext}"
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        return guessed
    if fallback_ext.lower() in (".jpg", ".jpeg"):
        return "image/jpeg"
    if fallback_ext.lower() == ".png":
        return "image/png"
    if fallback_ext.lower() == ".webp":
        return "image/webp"
    if fallback_ext.lower() == ".gif":
        return "image/gif"
    return "application/octet-stream"


def upload_image_bytes_sync(
    *,
    user_id: int,
    article_id: int,
    data: bytes,
    original_filename: str | None,
) -> str:
    """
    Upload bytes to the configured bucket and return the file's public URL.

    Raises:
        RuntimeError: Invalid configuration or Storage response.
    """
    if not data:
        raise ValueError("empty image payload")
    s = get_settings()
    bucket = (s.supabase_storage_bucket or "").strip()
    if not bucket:
        raise RuntimeError("SUPABASE_STORAGE_BUCKET missing")

    ext = Path(original_filename or "img").suffix or ".jpg"
    if not ext.startswith("."):
        ext = f".{ext}"
    safe_name = f"{uuid.uuid4().hex}{ext}"
    object_path = f"{user_id}/{article_id}/{safe_name}"

    content_type = _guess_content_type(original_filename, ext)
    file_options = {
        "content-type": content_type,
        "upsert": "true",
    }

    client = _get_client()
    client.storage.from_(bucket).upload(object_path, data, file_options=file_options)
    public_url = client.storage.from_(bucket).get_public_url(object_path)
    if not public_url or not str(public_url).startswith("http"):
        raise RuntimeError(f"Invalid Supabase public URL: {public_url!r}")
    return str(public_url)


async def upload_image_bytes(
    *,
    user_id: int,
    article_id: int,
    data: bytes,
    original_filename: str | None,
) -> str:
    """Async wrapper (sync Supabase client runs in a thread)."""
    return await asyncio.to_thread(
        upload_image_bytes_sync,
        user_id=user_id,
        article_id=article_id,
        data=data,
        original_filename=original_filename,
    )
