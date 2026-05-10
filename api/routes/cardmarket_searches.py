"""Saved Cardmarket URL lists + last scrape snapshot."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User
from schemas.cardmarket_searches import (
    CardmarketSearchCreateBody,
    CardmarketSearchResultPutBody,
    CardmarketSearchUpdateBody,
)
from services import cardmarket_search_service as cm_search_svc

router = APIRouter(prefix="/cardmarket-searches", tags=["cardmarket-searches"])


@router.get("")
def list_cardmarket_searches(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    return cm_search_svc.list_searches(db, user.id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_cardmarket_search(
    body: CardmarketSearchCreateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        return cm_search_svc.create_search(db, user.id, name=body.name, urls=body.urls)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{search_id}")
def get_cardmarket_search(
    search_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = cm_search_svc.get_search_detail(db, user.id, search_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found.")
    return row


@router.put("/{search_id}")
def update_cardmarket_search(
    search_id: int,
    body: CardmarketSearchUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        row = cm_search_svc.update_search(
            db,
            user.id,
            search_id,
            name=body.name,
            urls=body.urls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found.")
    return row


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cardmarket_search(
    search_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if not cm_search_svc.delete_search(db, user.id, search_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found.")


@router.put("/{search_id}/result")
def put_cardmarket_search_result(
    search_id: int,
    body: CardmarketSearchResultPutBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Same JWT as other endpoints; used by the desktop worker after a run."""
    row = cm_search_svc.upsert_last_result(db, user.id, search_id, body.payload)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found.")
    return row
