"""User registration and management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User
from schemas.users import UserCreate, UserResponse, UserUpdate
from services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


def _serialize(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        vinted_email=u.vinted_email,
        created_at=u.created_at.isoformat(),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    existing = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = auth_service.create_user(
        db,
        email=body.email,
        password=body.password,
        vinted_email=body.vinted_email,
        vinted_password=body.vinted_password,
    )
    return _serialize(user)


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[UserResponse]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [_serialize(u) for u in users]


@router.get("/me", response_model=UserResponse)
def me(current: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return _serialize(current)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    if current.id != user_id:
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
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    if current.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
