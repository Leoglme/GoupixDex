"""FastAPI dependencies (auth, DB)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_sub_from_token
from models.user import User

security = HTTPBearer(auto_error=False)


def get_bearer_or_query_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    token: Annotated[str | None, Query(description="JWT pour EventSource (sans header Authorization)")] = None,
) -> str:
    """JWT depuis ``Authorization: Bearer`` ou ``?token=`` (SSE / EventSource)."""
    if credentials is not None:
        return credentials.credentials
    if token and token.strip():
        return token.strip()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def get_current_user_from_token_str(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Utilisateur courant à partir du jeton Bearer ou query."""
    try:
        sub = get_sub_from_token(raw_token)
        user_id = int(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Require a valid Bearer JWT and return the ``User`` row."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        sub = get_sub_from_token(credentials.credentials)
        user_id = int(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Return ``User`` when Bearer token is valid; ``None`` when missing (does not raise)."""
    if credentials is None:
        return None
    try:
        sub = get_sub_from_token(credentials.credentials)
        user_id = int(sub)
    except (JWTError, ValueError):
        return None
    return db.get(User, user_id)
