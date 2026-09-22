"""Amazon multi-account profile paths + remote API helpers (desktop worker)."""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx

from amazon_config import bind_amazon_profile
from services.os_service import OsService


def legacy_amazon_profile_dir() -> Path:
    explicit = None
    return OsService.resolve_amazon_nodriver_user_data_dir(explicit)


def account_profile_dir(user_id: int, account_id: int) -> Path:
    root = legacy_amazon_profile_dir().parent / "amazon-nodriver-profile"
    return root / f"u{user_id}" / f"acc{account_id}"


def provision_staging_profile_dir(user_id: int) -> Path:
    """Profil Chrome temporaire pendant « Créer sur Amazon » (avant enregistrement coffre)."""
    root = legacy_amazon_profile_dir().parent / "amazon-nodriver-profile"
    return root / f"u{user_id}" / "_provision_staging"


def bind_provision_staging_profile(user_id: int) -> Path:
    profile = provision_staging_profile_dir(user_id)
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    bind_amazon_profile(str(profile))
    return profile


def discard_provision_staging_profile(user_id: int) -> None:
    profile = provision_staging_profile_dir(user_id)
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)


def claim_provision_staging_profile(user_id: int, account_id: int) -> Path:
    src = provision_staging_profile_dir(user_id)
    dst = account_profile_dir(user_id, account_id)
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    else:
        dst.mkdir(parents=True, exist_ok=True)
    bind_amazon_profile(str(dst))
    return dst


def bind_amazon_profile_for(user_id: int, account_id: int | None) -> Path:
    if account_id is None:
        profile = legacy_amazon_profile_dir()
    else:
        profile = account_profile_dir(user_id, account_id)
    profile.mkdir(parents=True, exist_ok=True)
    bind_amazon_profile(str(profile))
    return profile


async def fetch_vault_account_ids(raw_token: str, remote: str) -> list[int]:
    """Identifiants de tous les comptes Amazon du coffre de l'utilisateur (ordre de l'API)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{remote.rstrip('/')}/amazon-accounts",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == 401:
        raise PermissionError("Not authenticated")
    r.raise_for_status()
    data = r.json()
    out: list[int] = []
    for acc in data.get("accounts") or []:
        try:
            out.append(int(acc.get("id")))
        except (AttributeError, TypeError, ValueError):
            continue
    return out


async def fetch_active_account_id(raw_token: str, remote: str) -> int | None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{remote.rstrip('/')}/amazon-accounts/active",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == 401:
        # Ne jamais retomber en silence sur le profil legacy partagé : la session est expirée.
        raise PermissionError("Not authenticated")
    r.raise_for_status()
    data = r.json()
    aid = data.get("active_account_id")
    if aid is None:
        return None
    try:
        return int(aid)
    except (TypeError, ValueError):
        return None


async def fetch_account_credentials(
    raw_token: str, remote: str, account_id: int
) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{remote.rstrip('/')}/amazon-accounts/{account_id}/credentials",
            headers={"Authorization": f"Bearer {raw_token}", "Accept": "application/json"},
        )
    if r.status_code == 401:
        raise PermissionError("Not authenticated")
    r.raise_for_status()
    data = r.json()
    email = str(data.get("amazon_email") or "").strip()
    password = str(data.get("password") or "")
    if not email or not password:
        raise ValueError("Credentials missing on server")
    return email, password
