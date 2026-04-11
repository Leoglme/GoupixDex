"""Seed default user and margin settings from environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _vinted_from_env() -> tuple[str | None, str | None]:
    """Read Vinted login from .env (same keys as CLI / publish fallback)."""
    email = os.environ.get("VINTED_EMAIL_OR_USERNAME", "").strip() or None
    password = os.environ.get("VINTED_PASSWORD", "").strip() or None
    return email, password


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    email = os.environ.get("SEED_USER_EMAIL", "").strip()
    password = os.environ.get("SEED_USER_PASSWORD", "").strip()
    if not email or not password:
        print("SEED_USER_EMAIL and SEED_USER_PASSWORD must be set.", file=sys.stderr)
        raise SystemExit(1)

    vinted_email, vinted_password = _vinted_from_env()

    from sqlalchemy.orm import Session

    from core.database import SessionLocal
    from core.security import store_user_vinted_password
    from models.user import User
    from services.auth_service import create_user

    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            if vinted_email and vinted_password:
                existing.vinted_email = vinted_email
                existing.vinted_password = store_user_vinted_password(vinted_password)
                db.commit()
                print(f"User already exists: {email}")
                print("Updated vinted_email / vinted_password from VINTED_EMAIL_OR_USERNAME / VINTED_PASSWORD.")
            else:
                print(f"User already exists: {email}")
                print(
                    "Vinted columns unchanged (set VINTED_EMAIL_OR_USERNAME and VINTED_PASSWORD in .env to sync).",
                )
            return
        create_user(
            db,
            email=email,
            password=password,
            vinted_email=vinted_email,
            vinted_password=vinted_password,
        )
        print(f"Seeded user: {email}")
        if vinted_email and vinted_password:
            print("Stored Vinted credentials from .env on the user row.")
        elif vinted_email or vinted_password:
            print("Note: set both VINTED_EMAIL_OR_USERNAME and VINTED_PASSWORD to store Vinted on the user.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
