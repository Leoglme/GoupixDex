"""User registration and management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_admin, get_current_user
from core.security import decrypt_vinted_credential, store_user_vinted_password
from models.user import User
from schemas.users import (
    AdminUserResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    VintedCredentialsUpdate,
    VintedDecryptedResponse,
)
from services import auth_service
from services.user_settings_service import get_or_create_user_settings

router = APIRouter(prefix="/users", tags=["users"])


def _serialize(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        vinted_email=u.vinted_email,
        is_admin=bool(u.is_admin),
        status=u.status,
        created_at=u.created_at.isoformat(),
    )


def _serialize_admin(db: Session, u: User) -> AdminUserResponse:
    settings = get_or_create_user_settings(db, u.id)
    return AdminUserResponse(
        id=u.id,
        email=u.email,
        vinted_email=u.vinted_email,
        vinted_linked=bool(u.vinted_email and u.vinted_password),
        vinted_enabled=bool(settings.vinted_enabled),
        ebay_enabled=bool(settings.ebay_enabled),
        margin_percent=int(settings.margin_percent or 0),
        is_admin=bool(u.is_admin),
        status=u.status,
        request_message=u.request_message,
        created_at=u.created_at.isoformat(),
        has_password=bool(u.password),
        has_password_setup_link=bool(u.password_setup_token),
    )


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> AdminUserResponse:
    existing = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = auth_service.create_user(
        db,
        email=body.email,
        password=body.password,
        vinted_email=body.vinted_email,
        vinted_password=body.vinted_password,
        status="approved",
    )
    return _serialize_admin(db, user)


@router.get("", response_model=list[AdminUserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
) -> list[AdminUserResponse]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [_serialize_admin(db, u) for u in users]


@router.get("/me", response_model=UserResponse)
def me(current: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return _serialize(current)


@router.get("/me/vinted-decrypted", response_model=VintedDecryptedResponse)
def me_vinted_decrypted(current: Annotated[User, Depends(get_current_user)]) -> VintedDecryptedResponse:
    """Expose les identifiants Vinted en clair pour le worker Python local (app desktop)."""
    plain = decrypt_vinted_credential(current.vinted_password)
    return VintedDecryptedResponse(
        vinted_email=current.vinted_email,
        vinted_password=plain,
    )


@router.put("/me/vinted", response_model=UserResponse)
def update_my_vinted_credentials(
    body: VintedCredentialsUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Self-service: link/update the user's own Vinted email + password."""
    if body.vinted_email is not None:
        current.vinted_email = body.vinted_email.strip() or None
    if body.vinted_password is not None:
        # Empty string clears the stored secret; non-empty is encrypted.
        current.vinted_password = store_user_vinted_password(body.vinted_password)
    db.commit()
    db.refresh(current)
    return _serialize(current)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    if current.id != user_id and not current.is_admin:
        raise HTTPException(status_code=403, detail="Cannot modify another user")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.email is not None:
        new_email = body.email.strip().lower()
        taken = (
            db.query(User)
            .filter(User.email == new_email, User.id != user_id)
            .first()
        )
        if taken:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = new_email
    auth_service.apply_password_updates(
        user,
        password=body.password,
        vinted_password=body.vinted_password,
    )
    if body.vinted_email is not None:
        user.vinted_email = body.vinted_email.strip() or None
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_admin)],
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(user)
    db.commit()
