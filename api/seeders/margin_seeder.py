"""Ensure every user has a margin row (default 60% benefit markup)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(_ROOT / ".env")

    from sqlalchemy.orm import Session

    from config import get_settings
    from core.database import SessionLocal

    default_margin = get_settings().seed_margin_percent
    from models.margin_settings import MarginSettings
    from models.user import User

    db: Session = SessionLocal()
    try:
        users = db.query(User).order_by(User.id.asc()).all()
        if not users:
            print("No users found. Run seeders/user_seeder.py first.")
            return

        created = 0
        for user in users:
            row = db.query(MarginSettings).filter(MarginSettings.user_id == user.id).first()
            if row is None:
                db.add(MarginSettings(user_id=user.id, margin_percent=default_margin))
                created += 1
                print(f"  + settings for user_id={user.id} ({user.email}): margin {default_margin}%")

        if created == 0:
            print("All users already have margin settings.")
        else:
            db.commit()
            print(f"Done: {created} row(s) created (default margin {default_margin}%).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
