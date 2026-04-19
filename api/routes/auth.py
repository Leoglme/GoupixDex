"""JWT login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import create_access_token
from models.user import User
from schemas.auth import LoginRequest, TokenResponse
from services import auth_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = auth_service.authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status == "banned":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account banned")
    if user.status == "rejected":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access request rejected")
    if user.status != "approved":
        # 'pending' or any unknown intermediate state.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access not granted yet")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)
