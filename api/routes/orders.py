"""Cardmarket order import and listing."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User
from services.cardmarket_order_service import (
    get_order_detail,
    list_orders_summary,
    match_order_lines,
    persist_order_from_parsed,
)
from services.cardmarket_pdf_parser import parse_cardmarket_pdf_bytes

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
) -> list[dict[str, Any]]:
    """
    List Cardmarket orders for the current user.

    ``search`` — optional; space-separated tokens. An order is kept if it matches
    all tokens on order metadata (order id, seller) or on a single line
    (set, card number, name, line text).
    """
    return list_orders_summary(db, user.id, search=search)


@router.get("/match")
def match_lines(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    pokemon_name: str | None = None,
    set_code: str | None = None,
    card_number: str | None = None,
    condition: str | None = None,
    language_code: str | None = None,
) -> dict[str, Any]:
    """
    Match imported purchase lines to article fields (FIFO + suggested purchase from latest buy).
    """
    return match_order_lines(
        db,
        user.id,
        pokemon_name=pokemon_name,
        set_code=set_code,
        card_number=card_number,
        app_condition=condition,
        language_code=language_code,
    )


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return one order with lines and linked articles."""
    row = get_order_detail(db, user.id, order_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return row


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_order_pdf(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """
    Upload a Cardmarket purchase PDF and persist order + line items.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")
    try:
        parsed = parse_cardmarket_pdf_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        order = persist_order_from_parsed(db, user.id, parsed, file.filename)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This order is already imported.",
        ) from exc

    detail = get_order_detail(db, user.id, order.id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Import failed.")
    return detail
