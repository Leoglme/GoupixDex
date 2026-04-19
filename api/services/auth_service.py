"""Authentication helpers (login, user creation)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from config import get_settings
from core.security import hash_password, store_user_vinted_password, verify_password
from models.margin_settings import MarginSettings
from models.user import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if email/password match, else None.

    Users without a stored password (access request not finalized) cannot log in.
    Status checks (approved / banned / …) are performed by the caller / dependency.
    """
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        return None
    if not user.password:
        return None
    if not verify_password(password, user.password):
        return None
    return user


def create_user(
    db: Session,
    *,
    email: str,
    password: str | None,
    vinted_email: str | None = None,
    vinted_password: str | None = None,
    is_admin: bool = False,
    status: str = "approved",
    request_message: str | None = None,
) -> User:
    """Create a user, hash login password, encrypt Vinted password, and create margin settings.

    ``password`` may be ``None`` for users created from a public access request:
    they will set it later via the password-setup link the admin sends them.
    """
    normalized = email.strip().lower()
    u = User(
        email=normalized,
        password=hash_password(password) if password else None,
        vinted_email=vinted_email.strip() if vinted_email else None,
        vinted_password=store_user_vinted_password(vinted_password),
        is_admin=is_admin,
        status=status,
        request_message=(request_message or "").strip() or None,
    )
    db.add(u)
    db.flush()
    db.add(MarginSettings(user_id=u.id, margin_percent=get_settings().seed_margin_percent))
    db.commit()
    db.refresh(u)
    return u


def apply_password_updates(
    user: User,
    *,
    password: str | None = None,
    vinted_password: str | None = None,
) -> None:
    """Update login hash / encrypted Vinted secret when plaintext fields are provided (caller commits)."""
    if password is not None:
        user.password = hash_password(password)
    if vinted_password is not None:
        user.vinted_password = store_user_vinted_password(vinted_password)
