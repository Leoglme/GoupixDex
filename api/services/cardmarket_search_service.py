"""CRUD for saved Cardmarket multi-URL searches."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from models.cardmarket_search import CardmarketSearch, CardmarketSearchResult, CardmarketSearchUrl


def _default_basket_name() -> str:
    now = dt.datetime.now().astimezone()
    return f"Panier du {now.strftime('%d/%m/%Y %H:%M')}"


def _normalize_urls(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in raw:
        u = (line or "").strip()
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _search_row_to_summary(search: CardmarketSearch) -> dict[str, Any]:
    res = search.result
    ran_at = res.ran_at.isoformat() if res else None
    max_cov: int | None = None
    if res and res.payload_json:
        try:
            payload = json.loads(res.payload_json)
            meta = payload.get("meta") or {}
            mc = meta.get("max_coverage")
            if isinstance(mc, int):
                max_cov = mc
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": search.id,
        "name": search.name,
        "created_at": search.created_at.isoformat() if search.created_at else None,
        "updated_at": search.updated_at.isoformat() if search.updated_at else None,
        "url_count": len(search.urls or []),
        "last_ran_at": ran_at,
        "max_seller_coverage": max_cov,
    }


def list_searches(db: Session, user_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(CardmarketSearch)
        .where(CardmarketSearch.user_id == user_id)
        .options(selectinload(CardmarketSearch.urls), selectinload(CardmarketSearch.result))
        .order_by(CardmarketSearch.updated_at.desc())
    )
    rows = list(db.scalars(stmt).unique().all())
    return [_search_row_to_summary(s) for s in rows]


def get_search_detail(db: Session, user_id: int, search_id: int) -> dict[str, Any] | None:
    stmt = (
        select(CardmarketSearch)
        .where(CardmarketSearch.id == search_id, CardmarketSearch.user_id == user_id)
        .options(selectinload(CardmarketSearch.urls), selectinload(CardmarketSearch.result))
    )
    s = db.scalars(stmt).first()
    if s is None:
        return None
    payload: dict[str, Any] | None = None
    if s.result and s.result.payload_json:
        try:
            payload = json.loads(s.result.payload_json)
        except (json.JSONDecodeError, TypeError):
            payload = None
    return {
        "id": s.id,
        "name": s.name,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "urls": [{"id": u.id, "url": u.url, "sort_index": u.sort_index} for u in sorted(s.urls, key=lambda x: x.sort_index)],
        "last_result": payload,
        "last_ran_at": s.result.ran_at.isoformat() if s.result else None,
    }


def create_search(db: Session, user_id: int, *, name: str | None, urls: list[str]) -> dict[str, Any]:
    norm = _normalize_urls(urls)
    if not norm:
        raise ValueError("Au moins une URL est requise.")
    nm = (name or "").strip() or _default_basket_name()
    s = CardmarketSearch(user_id=user_id, name=nm)
    db.add(s)
    db.flush()
    for i, u in enumerate(norm):
        db.add(CardmarketSearchUrl(search_id=s.id, url=u, sort_index=i))
    db.commit()
    db.refresh(s)
    return get_search_detail(db, user_id, s.id) or {}


def update_search(
    db: Session,
    user_id: int,
    search_id: int,
    *,
    name: str | None = None,
    urls: list[str] | None = None,
) -> dict[str, Any] | None:
    s = db.get(CardmarketSearch, search_id)
    if s is None or s.user_id != user_id:
        return None
    if name is not None:
        t = name.strip()
        if t:
            s.name = t
    if urls is not None:
        norm = _normalize_urls(urls)
        if not norm:
            raise ValueError("Au moins une URL est requise.")
        db.execute(delete(CardmarketSearchUrl).where(CardmarketSearchUrl.search_id == search_id))
        for i, u in enumerate(norm):
            db.add(CardmarketSearchUrl(search_id=search_id, url=u, sort_index=i))
    s.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return get_search_detail(db, user_id, search_id)


def delete_search(db: Session, user_id: int, search_id: int) -> bool:
    s = db.get(CardmarketSearch, search_id)
    if s is None or s.user_id != user_id:
        return False
    db.delete(s)
    db.commit()
    return True


def upsert_last_result(
    db: Session,
    user_id: int,
    search_id: int,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    s = db.get(CardmarketSearch, search_id)
    if s is None or s.user_id != user_id:
        return None
    ran_at = dt.datetime.now(dt.UTC)
    payload = {**payload, "ran_at": ran_at.isoformat()}
    text = json.dumps(payload, ensure_ascii=False, default=str)
    existing = db.scalars(
        select(CardmarketSearchResult).where(CardmarketSearchResult.search_id == search_id)
    ).first()
    if existing:
        existing.ran_at = ran_at
        existing.payload_json = text
    else:
        db.add(CardmarketSearchResult(search_id=search_id, ran_at=ran_at, payload_json=text))
    s.updated_at = ran_at
    db.commit()
    return get_search_detail(db, user_id, search_id)
