"""Per-user margin settings (table ``settings``)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.margin_settings import MarginSettings
from models.user import User
from schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_or_create_settings(db: Session, user_id: int) -> MarginSettings:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if row is None:
        row = MarginSettings(user_id=user_id, margin_percent=20)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=SettingsResponse)
def get_margin_settings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SettingsResponse:
    s = _get_or_create_settings(db, user.id)
    return SettingsResponse(margin_percent=s.margin_percent)


@router.put("", response_model=SettingsResponse)
def put_margin_settings(
    body: SettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SettingsResponse:
    s = _get_or_create_settings(db, user.id)
    s.margin_percent = body.margin_percent
    db.commit()
    db.refresh(s)
    return SettingsResponse(margin_percent=s.margin_percent)
