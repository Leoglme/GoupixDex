"""Thematic binders (classeurs) — CRUD and pocket layout."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from fastapi import HTTPException, status

from models.binder import Binder, BinderItem
from models.collection_card import CollectionCard
from services.collection_card_lookup_service import fetch_card_for_collection
from services import collection_card_service
from services.binder_cover_service import (
    collect_paths_from_cover,
    cover_path_prefix,
    resolve_cover_urls,
    validate_cover_paths,
)

POCKET_KEY_RE = re.compile(r"^i:(\d+)$")

BINDER_COLOR_CODES = frozenset({"red", "orange", "yellow", "green", "blue", "purple", "pink"})
BINDER_STYLE_CODES = frozenset({"binder", "mosaic", "showcase", "fan", "label", "custom"})
PAGE_GRID_CODES = frozenset({"3x3", "4x3", "2x2", "4x4"})


def pocket_key(collection_card_id: int) -> str:
    return f"i:{collection_card_id}"


def parse_pocket_key(key: str) -> int | None:
    m = POCKET_KEY_RE.match(key.strip())
    if not m:
        return None
    return int(m.group(1))


def _card_cover_dict(card: CollectionCard) -> dict[str, str]:
    return {"image_url": card.image_url or ""}


def _pocket_item_dict(item: BinderItem) -> dict[str, Any]:
    card = item.collection_card
    kind = "wanted"
    if card and not card.is_placeholder and int(card.quantity) > 0:
        kind = "owned"
    return {
        "id": pocket_key(item.collection_card_id),
        "kind": kind,
        "collection_card_id": item.collection_card_id,
        "card_name": card.display_name if card else "",
        "set_name": card.set_name if card else None,
        "local_id": card.card_number if card else None,
        "tcgdex_card_id": card.tcgdex_card_id if card else None,
        "image_url": card.image_url if card else "",
        "quantity": int(card.quantity) if card else 1,
        "position": item.position,
        "created_at": item.created_at.isoformat() if item.created_at else "",
    }


def _binder_summary(binder: Binder, *, card_count: int, value_eur: float | None) -> dict[str, Any]:
    return {
        "id": binder.id,
        "name": binder.name,
        "color": binder.color,
        "style": binder.style,
        "page_grid": binder.page_grid,
        "page_count": binder.page_count,
        "position": binder.position,
        "design": binder.design,
        "cover": binder.cover,
        "cover_collection_card_ids": binder.cover_collection_card_ids,
        "created_at": binder.created_at.isoformat() if binder.created_at else None,
        "updated_at": binder.updated_at.isoformat() if binder.updated_at else None,
        "card_count": card_count,
        "estimated_value_eur": value_eur,
    }


def _resolve_covers(binder: Binder, items: list[BinderItem]) -> list[dict[str, str]]:
    card_by_id = {bi.collection_card_id: bi.collection_card for bi in items if bi.collection_card}
    chosen_ids = binder.cover_collection_card_ids or []
    covers: list[dict[str, str]] = []
    for cid in chosen_ids:
        card = card_by_id.get(cid)
        if card and card.image_url:
            covers.append(_card_cover_dict(card))
    if covers:
        return covers
    for bi in sorted(items, key=lambda x: x.created_at):
        card = bi.collection_card
        if card and card.image_url:
            covers.append(_card_cover_dict(card))
        if len(covers) >= 4:
            break
    return covers


def list_binders_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(Binder)
        .options(joinedload(Binder.items).joinedload(BinderItem.collection_card))
        .filter(Binder.user_id == user_id)
        .order_by(Binder.position.asc(), Binder.created_at.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for b in rows:
        count = 0
        value = Decimal(0)
        priced = False
        for bi in b.items:
            card = bi.collection_card
            if not card:
                continue
            count += int(card.quantity)
            if card.market_price_eur is not None:
                value += Decimal(str(card.market_price_eur)) * int(card.quantity)
                priced = True
        summary = _binder_summary(b, card_count=count, value_eur=float(value) if priced else None)
        summary["covers"] = _resolve_covers(b, b.items)
        out.append(summary)
    return out


def get_binder_detail(db: Session, binder_id: int, user_id: int) -> dict[str, Any] | None:
    binder = (
        db.query(Binder)
        .options(joinedload(Binder.items).joinedload(BinderItem.collection_card))
        .filter(Binder.id == binder_id, Binder.user_id == user_id)
        .first()
    )
    if binder is None:
        return None

    items = [_pocket_item_dict(bi) for bi in binder.items]
    count = sum(int(bi.collection_card.quantity) for bi in binder.items if bi.collection_card)
    value = Decimal(0)
    priced = False
    for bi in binder.items:
        card = bi.collection_card
        if card and card.market_price_eur is not None:
            value += Decimal(str(card.market_price_eur)) * int(card.quantity)
            priced = True

    member_ids = {bi.collection_card_id for bi in binder.items}
    candidates = (
        db.query(CollectionCard)
        .filter(CollectionCard.user_id == user_id, CollectionCard.is_placeholder.is_(False))
        .order_by(CollectionCard.created_at.desc())
        .all()
    )
    candidate_dicts = [
        {
            "id": str(c.id),
            "collection_card_id": c.id,
            "tcgdex_card_id": c.tcgdex_card_id,
            "card_name": c.display_name,
            "set_name": c.set_name or "",
            "local_id": c.card_number,
            "image_url": c.image_url or "",
            "quantity": int(c.quantity),
            "in_binder": c.id in member_ids,
        }
        for c in candidates
    ]

    summary = _binder_summary(binder, card_count=count, value_eur=float(value) if priced else None)
    summary["items"] = items
    summary["covers"] = _resolve_covers(binder, binder.items)
    summary["candidates"] = candidate_dicts
    paths = collect_paths_from_cover(binder.cover)
    if paths:
        summary["cover_urls"] = resolve_cover_urls(paths)
    else:
        summary["cover_urls"] = {}
    return summary


def create_binder(db: Session, user_id: int, name: str) -> Binder:
    max_pos = (
        db.query(Binder.position)
        .filter(Binder.user_id == user_id, Binder.position.is_not(None))
        .order_by(Binder.position.desc())
        .limit(1)
        .scalar()
    )
    position = (max_pos + 1) if max_pos is not None else 0
    row = Binder(user_id=user_id, name=name.strip(), position=position)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_binder(
    db: Session,
    binder: Binder,
    *,
    name: str | None = None,
    color: str | None = None,
    style: str | None = None,
    page_grid: str | None = None,
    page_count: int | None = None,
    design: dict[str, Any] | None = None,
    cover: dict[str, Any] | None = None,
    cover_collection_card_ids: list[int] | None = None,
) -> Binder:
    if name is not None:
        binder.name = name.strip()
    if color is not None:
        binder.color = color if color in BINDER_COLOR_CODES else None
    if style is not None:
        binder.style = style if style in BINDER_STYLE_CODES else binder.style
    if page_grid is not None:
        binder.page_grid = page_grid if page_grid in PAGE_GRID_CODES else binder.page_grid
    if page_count is not None:
        binder.page_count = page_count
    if design is not None:
        binder.design = design
    if cover is not None:
        paths = collect_paths_from_cover(cover)
        if paths:
            validate_cover_paths(binder.user_id, binder.id, paths)
        card_refs: set[str] = set()
        bg = cover.get("bg") if isinstance(cover, dict) else None
        if isinstance(bg, dict) and isinstance(bg.get("card"), str) and bg["card"].isdigit():
            card_refs.add(bg["card"])
        zones = cover.get("zones") if isinstance(cover, dict) else None
        if isinstance(zones, dict):
            for el in zones.values():
                if isinstance(el, dict) and el.get("type") == "card":
                    cid = el.get("itemId")
                    if isinstance(cid, str) and cid.isdigit():
                        card_refs.add(cid)
        member = {str(bi.collection_card_id) for bi in binder.items}
        if card_refs - member:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Carte de couverture non autorisée")
        binder.cover = cover
    if cover_collection_card_ids is not None:
        member = {bi.collection_card_id for bi in binder.items}
        binder.cover_collection_card_ids = [cid for cid in cover_collection_card_ids if cid in member] or None
    db.commit()
    db.refresh(binder)
    return binder


def delete_binder(db: Session, binder: Binder) -> None:
    db.delete(binder)
    db.commit()


def reorder_binders(db: Session, user_id: int, binder_ids: list[int]) -> None:
    owned = {
        b.id
        for b in db.query(Binder.id).filter(Binder.user_id == user_id, Binder.id.in_(binder_ids)).all()
    }
    ordered = [bid for bid in binder_ids if bid in owned]
    for i, bid in enumerate(ordered):
        db.query(Binder).filter(Binder.id == bid, Binder.user_id == user_id).update({"position": i})
    db.commit()


def _max_pocket(db: Session, binder_id: int) -> int:
    row = (
        db.query(BinderItem.position)
        .filter(BinderItem.binder_id == binder_id)
        .order_by(BinderItem.position.desc())
        .limit(1)
        .scalar()
    )
    return row if row is not None else -1


def _occupant_at(db: Session, binder_id: int, pocket: int, except_card_id: int | None = None) -> int | None:
    q = db.query(BinderItem).filter(BinderItem.binder_id == binder_id, BinderItem.position == pocket)
    if except_card_id is not None:
        q = q.filter(BinderItem.collection_card_id != except_card_id)
    row = q.first()
    return row.collection_card_id if row else None


def _ensure_collection_card_for_catalog(
    db: Session,
    user_id: int,
    tcgdex_card_id: str,
    language: str,
) -> CollectionCard:
    lang = language.strip().lower() or "fr"
    existing = collection_card_service.find_existing_for_user(
        db,
        user_id,
        tcgdex_card_id=tcgdex_card_id.strip(),
        language=lang,
    )
    if existing is not None:
        return existing

    meta = fetch_card_for_collection(tcgdex_card_id=tcgdex_card_id.strip(), physical_language=lang)
    row = CollectionCard(
        user_id=user_id,
        tcgdex_card_id=meta["tcgdex_card_id"],
        tcgdex_set_id=meta["tcgdex_set_id"],
        set_code=meta["set_code"],
        set_name=meta["set_name"],
        card_number=meta["card_number"],
        card_name_en=meta["card_name_en"],
        card_name_fr=meta["card_name_fr"],
        card_name_ja=meta["card_name_ja"],
        display_name=meta["display_name"],
        rarity=meta["rarity"],
        language=meta["language"],
        image_url=meta["image_url"],
        quantity=0,
        is_placeholder=True,
    )
    collection_card_service.apply_market_price(
        row,
        cardmarket_id_product=meta["cardmarket_id_product"],
        market_price_eur=meta["market_price_eur"],
    )
    db.add(row)
    db.flush()
    return row


def place_catalog_card_in_pocket(
    db: Session,
    binder: Binder,
    user_id: int,
    tcgdex_card_id: str,
    pocket: int,
    language: str = "fr",
) -> None:
    try:
        card = _ensure_collection_card_for_catalog(db, user_id, tcgdex_card_id, language)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc
    place_item_in_pocket(db, binder, user_id, card.id, pocket)


def place_item_in_pocket(
    db: Session,
    binder: Binder,
    user_id: int,
    collection_card_id: int,
    pocket: int,
) -> None:
    card = (
        db.query(CollectionCard)
        .filter(CollectionCard.id == collection_card_id, CollectionCard.user_id == user_id)
        .first()
    )
    if card is None:
        raise ValueError("Carte introuvable dans la collection")

    occupant = _occupant_at(db, binder.id, pocket, except_card_id=collection_card_id)
    if occupant is not None:
        raise ValueError("Pochette occupée")

    existing = (
        db.query(BinderItem)
        .filter(BinderItem.binder_id == binder.id, BinderItem.collection_card_id == collection_card_id)
        .first()
    )
    if existing:
        existing.position = pocket
    else:
        db.add(BinderItem(binder_id=binder.id, collection_card_id=collection_card_id, position=pocket))
    db.commit()


def move_pocket(db: Session, binder: Binder, pocket_key_str: str, to_pocket: int) -> None:
    card_id = parse_pocket_key(pocket_key_str)
    if card_id is None:
        raise ValueError("Clé de pochette invalide")

    item = (
        db.query(BinderItem)
        .filter(BinderItem.binder_id == binder.id, BinderItem.collection_card_id == card_id)
        .first()
    )
    if item is None:
        raise ValueError("Carte absente du classeur")

    from_pocket = item.position
    occupant_id = _occupant_at(db, binder.id, to_pocket, except_card_id=card_id)
    item.position = to_pocket
    if occupant_id is not None and from_pocket is not None:
        occ = (
            db.query(BinderItem)
            .filter(BinderItem.binder_id == binder.id, BinderItem.collection_card_id == occupant_id)
            .first()
        )
        if occ:
            occ.position = from_pocket
    db.commit()


def remove_from_pocket(db: Session, binder: Binder, pocket_key_str: str) -> None:
    card_id = parse_pocket_key(pocket_key_str)
    if card_id is None:
        raise ValueError("Clé de pochette invalide")
    db.query(BinderItem).filter(
        BinderItem.binder_id == binder.id,
        BinderItem.collection_card_id == card_id,
    ).delete()
    card = db.query(CollectionCard).filter(CollectionCard.id == card_id, CollectionCard.user_id == binder.user_id).first()
    if card is not None and card.is_placeholder:
        still_used = (
            db.query(BinderItem)
            .filter(BinderItem.collection_card_id == card_id)
            .count()
        )
        if still_used == 0:
            db.delete(card)
    db.commit()


def set_page_count(db: Session, binder: Binder, count: int) -> None:
    binder.page_count = count
    db.commit()


def add_items_to_binder(db: Session, binder: Binder, user_id: int, collection_card_ids: list[int]) -> None:
    present = {
        bi.collection_card_id
        for bi in db.query(BinderItem).filter(BinderItem.binder_id == binder.id).all()
    }
    pocket = _max_pocket(db, binder.id) + 1
    for cid in collection_card_ids:
        if cid in present:
            continue
        card = (
            db.query(CollectionCard)
            .filter(CollectionCard.id == cid, CollectionCard.user_id == user_id)
            .first()
        )
        if card is None:
            continue
        db.add(BinderItem(binder_id=binder.id, collection_card_id=cid, position=pocket))
        present.add(cid)
        pocket += 1
    db.commit()
