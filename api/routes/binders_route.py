"""REST API for thematic binders (classeurs)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.binder import Binder
from models.user import User
from schemas.binders import (
    BinderAddItemsBody,
    BinderCoverUrlsBody,
    BinderCreateBody,
    BinderMovePocketBody,
    BinderPageCountBody,
    BinderPlaceCatalogBody,
    BinderPlaceItemBody,
    BinderRemovePocketBody,
    BinderReorderBody,
    BinderUpdateBody,
)
from services import binder_cover_service, binder_service

router = APIRouter(prefix="/binders", tags=["binders"])


def _get_owned_binder(db: Session, binder_id: int, user_id: int) -> Binder:
    row = db.query(Binder).filter(Binder.id == binder_id, Binder.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classeur introuvable")
    return row


@router.get("")
def list_binders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    return {"items": binder_service.list_binders_for_user(db, user.id)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_binder(
    body: BinderCreateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = binder_service.create_binder(db, user.id, body.name)
    detail = binder_service.get_binder_detail(db, row.id, user.id)
    return {"binder": detail}


@router.get("/{binder_id}")
def get_binder(
    binder_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classeur introuvable")
    return detail


@router.patch("/{binder_id}")
def patch_binder(
    binder_id: int,
    body: BinderUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    binder_service.update_binder(
        db,
        binder,
        name=body.name,
        color=body.color,
        style=body.style,
        page_grid=body.page_grid,
        page_count=body.page_count,
        pokedex_region=body.pokedex_region,
        design=body.design,
        cover=body.cover,
        cover_collection_card_ids=body.cover_collection_card_ids,
    )
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.delete("/{binder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_binder(
    binder_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    binder = _get_owned_binder(db, binder_id, user.id)
    binder_service.delete_binder(db, binder)


@router.post("/reorder")
def reorder_binders(
    body: BinderReorderBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    binder_service.reorder_binders(db, user.id, body.binder_ids)
    return {"status": "ok"}


@router.post("/{binder_id}/place")
def place_in_pocket(
    binder_id: int,
    body: BinderPlaceItemBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    try:
        binder_service.place_item_in_pocket(db, binder, user.id, body.collection_card_id, body.pocket)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.post("/{binder_id}/place-catalog")
def place_catalog_in_pocket(
    binder_id: int,
    body: BinderPlaceCatalogBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    try:
        binder_service.place_catalog_card_in_pocket(
            db,
            binder,
            user.id,
            body.tcgdex_card_id,
            body.pocket,
            body.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.post("/{binder_id}/move")
def move_pocket(
    binder_id: int,
    body: BinderMovePocketBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    try:
        binder_service.move_pocket(db, binder, body.pocket_key, body.to_pocket)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.post("/{binder_id}/remove")
def remove_from_pocket(
    binder_id: int,
    body: BinderRemovePocketBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    try:
        binder_service.remove_from_pocket(db, binder, body.pocket_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.post("/{binder_id}/page-count")
def set_page_count(
    binder_id: int,
    body: BinderPageCountBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    binder_service.set_page_count(db, binder, body.page_count)
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}


@router.post("/{binder_id}/cover-image")
async def upload_cover_image(
    binder_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    image: UploadFile = File(...),
) -> dict[str, str]:
    _get_owned_binder(db, binder_id, user.id)
    return await binder_cover_service.upload_cover_image(user.id, binder_id, image)


@router.post("/{binder_id}/cover-urls")
def resolve_cover_urls(
    binder_id: int,
    body: BinderCoverUrlsBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, dict[str, str]]:
    binder = _get_owned_binder(db, binder_id, user.id)
    prefix = binder_cover_service.cover_path_prefix(user.id, binder.id)
    safe = [p for p in body.paths if p.startswith(prefix)]
    return {"urls": binder_cover_service.resolve_cover_urls(safe)}


@router.post("/{binder_id}/add-items")
def add_items(
    binder_id: int,
    body: BinderAddItemsBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    binder = _get_owned_binder(db, binder_id, user.id)
    binder_service.add_items_to_binder(db, binder, user.id, body.collection_card_ids)
    detail = binder_service.get_binder_detail(db, binder_id, user.id)
    return detail or {}
