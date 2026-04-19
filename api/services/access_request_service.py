"""Access request lifecycle: create, approve, reject, ban, password setup tokens."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.security import hash_password
from models.margin_settings import MarginSettings
from models.user import USER_STATUSES, User

#: Default lifetime of a password setup link.
PASSWORD_SETUP_TTL = dt.timedelta(days=7)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    """Treat naive datetimes coming back from MySQL DATETIME as UTC.

    The column is declared ``DateTime(timezone=True)`` but MySQL ``DATETIME``
    has no offset, so SQLAlchemy returns naive values. We always store UTC
    (see ``_now()``), so attaching ``UTC`` is safe.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value


def _ensure_settings(db: Session, user_id: int) -> None:
    """Lazily attach a ``settings`` row so dashboards / margin reads always work."""
    existing = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if existing is None:
        from config import get_settings as _get_app_settings

        db.add(MarginSettings(user_id=user_id, margin_percent=_get_app_settings().seed_margin_percent))


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()


def submit_access_request(db: Session, *, email: str, message: str | None) -> User:
    """Public entry point used by the ``/request`` page.

    - new email → create a ``pending`` user (no password yet)
    - already pending/rejected → update the message and refresh ``created_at``
      so the admin sees the latest request
    - already approved/banned → 409 (the user must contact the admin manually)
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Email is required")
    msg = (message or "").strip() or None
    existing = db.query(User).filter(User.email == normalized).first()
    if existing is None:
        u = User(
            email=normalized,
            password=None,
            is_admin=False,
            status="pending",
            request_message=msg,
        )
        db.add(u)
        db.flush()
        _ensure_settings(db, u.id)
        db.commit()
        db.refresh(u)
        return u

    if existing.status in ("approved", "banned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email.",
        )
    # pending or rejected → keep their row, update the latest message.
    existing.request_message = msg
    existing.status = "pending"
    db.commit()
    db.refresh(existing)
    return existing


def _require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _set_status(db: Session, user_id: int, new_status: str) -> User:
    if new_status not in USER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    user = _require_user(db, user_id)
    if user.is_admin and new_status != "approved":
        raise HTTPException(status_code=400, detail="Cannot change admin status")
    user.status = new_status
    db.commit()
    db.refresh(user)
    return user


def approve(db: Session, user_id: int) -> User:
    return _set_status(db, user_id, "approved")


def reject(db: Session, user_id: int) -> User:
    return _set_status(db, user_id, "rejected")


def ban(db: Session, user_id: int) -> User:
    return _set_status(db, user_id, "banned")


def generate_password_setup_token(db: Session, user_id: int) -> tuple[User, str]:
    """Issue a single-use token allowing the user to (re)define their password."""
    user = _require_user(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Admin password is set via SEED_USER_PASSWORD")
    token = secrets.token_urlsafe(32)
    user.password_setup_token = token
    user.password_setup_expires_at = _now() + PASSWORD_SETUP_TTL
    db.commit()
    db.refresh(user)
    return user, token


def get_user_by_setup_token(db: Session, token: str) -> User:
    """Return the user owning ``token`` if it is still valid; raise 404 otherwise."""
    if not token or not token.strip():
        raise HTTPException(status_code=404, detail="Invalid token")
    user = db.query(User).filter(User.password_setup_token == token.strip()).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Invalid token")
    expires_at = _as_utc(user.password_setup_expires_at)
    if expires_at and expires_at < _now():
        raise HTTPException(status_code=410, detail="Token expired")
    return user


def consume_setup_token(db: Session, token: str, *, password: str) -> User:
    """Persist ``password`` for the user owning ``token`` then invalidate the token."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    user = get_user_by_setup_token(db, token)
    user.password = hash_password(password)
    user.password_setup_token = None
    user.password_setup_expires_at = None
    if user.status == "pending":
        # Setting a password from a link sent by the admin implicitly approves the user.
        user.status = "approved"
    db.commit()
    db.refresh(user)
    return user


def status_filter(users: Iterable[User], wanted: str | None) -> list[User]:
    if not wanted:
        return list(users)
    return [u for u in users if u.status == wanted]
