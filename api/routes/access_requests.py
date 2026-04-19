"""Public access requests + admin moderation + password setup links."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_admin
from models.user import User
from routes.users import _serialize_admin
from schemas.access_requests import (
    AccessRequestCreate,
    AccessRequestSubmittedResponse,
    PasswordSetupCompleteRequest,
    PasswordSetupInfoResponse,
    PasswordSetupTokenResponse,
)
from schemas.users import AdminUserResponse
from services import access_request_service
from services.access_request_service import _as_utc as _as_utc_dt


def _iso_utc(value) -> str:
    """ISO 8601 in UTC (with explicit ``+00:00``) so JS clients parse correctly."""
    aware = _as_utc_dt(value)
    return aware.isoformat() if aware else ""

router = APIRouter()

# ----------------------------------------------------------------------- public

requests_router = APIRouter(prefix="/access-requests", tags=["access-requests"])


@requests_router.post(
    "",
    response_model=AccessRequestSubmittedResponse,
    status_code=201,
)
def submit_access_request(
    body: AccessRequestCreate,
    db: Annotated[Session, Depends(get_db)],
) -> AccessRequestSubmittedResponse:
    user = access_request_service.submit_access_request(
        db,
        email=body.email,
        message=body.message,
    )
    return AccessRequestSubmittedResponse(email=user.email)


# ----------------------------------------------------------------------- admin


@requests_router.post("/{user_id}/approve", response_model=AdminUserResponse)
def approve(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> AdminUserResponse:
    user = access_request_service.approve(db, user_id)
    return _serialize_admin(db, user)


@requests_router.post("/{user_id}/reject", response_model=AdminUserResponse)
def reject(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> AdminUserResponse:
    user = access_request_service.reject(db, user_id)
    return _serialize_admin(db, user)


@requests_router.post("/{user_id}/ban", response_model=AdminUserResponse)
def ban(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> AdminUserResponse:
    user = access_request_service.ban(db, user_id)
    return _serialize_admin(db, user)


def _build_setup_url(request: Request, token: str) -> str:
    """Try the ``Origin`` header first (browser caller), fallback to the API host."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        # Strip any trailing path on referer, keep scheme + host.
        from urllib.parse import urlparse

        parsed = urlparse(origin)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/setup-password/{token}"
    base = str(request.base_url).rstrip("/")
    return f"{base}/setup-password/{token}"


@requests_router.post("/{user_id}/password-link", response_model=PasswordSetupTokenResponse)
def issue_password_link(
    user_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> PasswordSetupTokenResponse:
    user, token = access_request_service.generate_password_setup_token(db, user_id)
    return PasswordSetupTokenResponse(
        token=token,
        expires_at=_iso_utc(user.password_setup_expires_at),
        setup_url=_build_setup_url(request, token),
    )


# ----------------------------------------------------------------- password setup

password_setup_router = APIRouter(prefix="/password-setup", tags=["password-setup"])


@password_setup_router.get("/{token}", response_model=PasswordSetupInfoResponse)
def get_password_setup_info(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> PasswordSetupInfoResponse:
    user = access_request_service.get_user_by_setup_token(db, token)
    return PasswordSetupInfoResponse(
        email=user.email,
        expires_at=_iso_utc(user.password_setup_expires_at),
    )


@password_setup_router.post("/{token}", response_model=PasswordSetupInfoResponse)
def complete_password_setup(
    token: str,
    body: PasswordSetupCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PasswordSetupInfoResponse:
    user = access_request_service.consume_setup_token(db, token, password=body.password)
    return PasswordSetupInfoResponse(
        email=user.email,
        expires_at="",
    )


router.include_router(requests_router)
router.include_router(password_setup_router)
