"""Persistence and matching for Cardmarket orders."""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from models.article import Article
from models.cardmarket_order import CardmarketOrder
from models.cardmarket_order_line import CardmarketOrderLine
from services.cardmarket_pdf_parser import ParsedCardmarketPdf, normalize_card_number_token, normalize_pokemon_key

def _order_by_paid_at_desc_nulls_last() -> tuple:
    """
    ``ORDER BY paid_at DESC`` with null ``paid_at`` rows last (MySQL/MariaDB: no ``NULLS LAST``).

    @returns Tuple of SQLAlchemy order expressions.
    """
    return (
        case((CardmarketOrder.paid_at.is_(None), 1), else_=0).asc(),
        CardmarketOrder.paid_at.desc(),
    )


_APP_CONDITION_TO_CM: dict[str, str] = {
    "Near Mint": "NM",
    "Lightly Played": "LP",
    "Moderately Played": "MP",
    "Heavily Played": "HP",
    "Damaged": "DMG",
    "Poor": "PR",
}


def _linked_units_for_line(db: Session, line_id: int) -> int:
    """Count articles tied to a purchase line."""
    return (
        db.query(func.count(Article.id))
        .filter(Article.order_line_id == line_id)
        .scalar()
        or 0
    )


def remaining_units(db: Session, line: CardmarketOrderLine) -> int:
    """
    Remaining purchasable slots on a line (quantity minus linked articles).

    @param db - DB session.
    @param line - Order line row.
    @returns Non-negative remaining count.
    """
    used = _linked_units_for_line(db, line.id)
    return max(0, int(line.quantity) - int(used))


def persist_order_from_parsed(
    db: Session,
    user_id: int,
    parsed: ParsedCardmarketPdf,
    source_filename: str | None,
) -> CardmarketOrder:
    """
    Insert a parsed Cardmarket PDF into the database.

    @param db - Session.
    @param user_id - Owner user id.
    @param parsed - Parsed PDF payload.
    @param source_filename - Original upload name for audit.
    @returns Persisted order with lines loaded.
    """
    order = CardmarketOrder(
        user_id=user_id,
        external_order_id=parsed.external_order_id,
        seller_username=parsed.seller_username,
        seller_display_name=parsed.seller_display_name,
        seller_country_code=parsed.seller_country_code,
        paid_at=parsed.paid_at,
        shipped_at=parsed.shipped_at,
        delivered_at=parsed.delivered_at,
        items_subtotal=parsed.items_subtotal,
        shipping_fee=parsed.shipping_fee,
        order_total=parsed.order_total,
        source_filename=(source_filename[:500] if source_filename else None),
    )
    db.add(order)
    db.flush()

    for idx, pl in enumerate(parsed.lines):
        key = normalize_pokemon_key(pl.pokemon_name_raw)
        lang = pl.language_code.upper()[:16]
        cond = pl.condition_label.upper()[:128]
        var = pl.variant_token[:512]
        db.add(
            CardmarketOrderLine(
                order_id=order.id,
                line_index=idx,
                quantity=pl.quantity,
                raw_label=pl.invoice_line_text,
                pokemon_key=key,
                card_number=normalize_card_number_token(pl.card_number),
                language_code=lang,
                condition_label=cond,
                set_code=pl.set_code.lower(),
                variant_token=var,
                unit_price_eur=pl.unit_price_eur,
            )
        )
    db.commit()
    db.refresh(order)
    return (
        db.query(CardmarketOrder)
        .options(joinedload(CardmarketOrder.lines))
        .filter(CardmarketOrder.id == order.id)
        .one()
    )


def _orders_search_tokens(search: str | None) -> list[str]:
    """Lowercase tokens (split on whitespace) for order / card line search."""
    if not search or not search.strip():
        return []
    return [t for t in search.strip().lower().split() if t]


def _mysql_like_pattern(fragment: str) -> str:
    """Build ``LIKE`` pattern with wildcards; escape ``%`` / ``_`` / ``\\`` inside ``fragment``."""
    esc = fragment.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def list_orders_summary(db: Session, user_id: int, search: str | None = None) -> list[dict[str, Any]]:
    """
    List orders with aggregate sold-article counts for the dashboard table.

    Optional ``search``: each token must match either (a) the same purchase line
    (set, card #, name, variant, raw line) or (b) the order row (order id, seller).

    @param db - Session.
    @param user_id - Owner.
    @param search - Optional free-text filter.
    @returns Serializable rows sorted by paid date desc.
    """
    tokens = _orders_search_tokens(search)
    if tokens:
        line_hay = func.lower(
            func.concat_ws(
                " ",
                func.coalesce(CardmarketOrderLine.set_code, ""),
                func.coalesce(CardmarketOrderLine.card_number, ""),
                func.coalesce(CardmarketOrderLine.pokemon_key, ""),
                func.coalesce(CardmarketOrderLine.language_code, ""),
                func.coalesce(CardmarketOrderLine.condition_label, ""),
                func.coalesce(CardmarketOrderLine.variant_token, ""),
                func.coalesce(CardmarketOrderLine.raw_label, ""),
            )
        )
        q_line = (
            db.query(CardmarketOrderLine.order_id)
            .join(CardmarketOrder, CardmarketOrder.id == CardmarketOrderLine.order_id)
            .filter(CardmarketOrder.user_id == user_id)
        )
        for tok in tokens:
            q_line = q_line.filter(line_hay.like(_mysql_like_pattern(tok), escape="\\"))
        line_order_ids = {r[0] for r in q_line.distinct().all()}

        q_meta = db.query(CardmarketOrder.id).filter(CardmarketOrder.user_id == user_id)
        for tok in tokens:
            pat = _mysql_like_pattern(tok)
            q_meta = q_meta.filter(
                or_(
                    func.lower(CardmarketOrder.external_order_id).like(pat, escape="\\"),
                    func.lower(func.coalesce(CardmarketOrder.seller_username, "")).like(pat, escape="\\"),
                    func.lower(func.coalesce(CardmarketOrder.seller_display_name, "")).like(pat, escape="\\"),
                )
            )
        meta_order_ids = {r[0] for r in q_meta.all()}
        allowed_ids = line_order_ids | meta_order_ids
        if not allowed_ids:
            return []
        orders = (
            db.query(CardmarketOrder)
            .filter(CardmarketOrder.user_id == user_id, CardmarketOrder.id.in_(allowed_ids))
            .order_by(*_order_by_paid_at_desc_nulls_last(), CardmarketOrder.id.desc())
            .all()
        )
    else:
        orders = (
            db.query(CardmarketOrder)
            .filter(CardmarketOrder.user_id == user_id)
            .order_by(*_order_by_paid_at_desc_nulls_last(), CardmarketOrder.id.desc())
            .all()
        )
    line_ids_by_order: dict[int, list[int]] = {}
    for o in orders:
        db.refresh(o, ["lines"])
        line_ids_by_order[o.id] = [ln.id for ln in o.lines]

    out: list[dict[str, Any]] = []
    for o in orders:
        lids = line_ids_by_order.get(o.id, [])
        if not lids:
            sold_count = 0
        else:
            sold_count = int(
                db.query(func.count(Article.id))
                .filter(
                    Article.order_line_id.in_(lids),
                    Article.is_sold.is_(True),
                )
                .scalar()
                or 0,
            )
        item_count = sum(int(ln.quantity) for ln in o.lines)
        out.append(
            {
                "id": o.id,
                "external_order_id": o.external_order_id,
                "seller_username": o.seller_username,
                "seller_display_name": o.seller_display_name,
                "seller_country_code": o.seller_country_code,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
                "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
                "items_subtotal": float(o.items_subtotal),
                "shipping_fee": float(o.shipping_fee),
                "order_total": float(o.order_total),
                "line_count": len(o.lines),
                "item_units": item_count,
                "sold_articles_count": sold_count,
                "created_at": o.created_at.isoformat(),
            }
        )
    return out


def get_order_detail(db: Session, user_id: int, order_id: int) -> dict[str, Any] | None:
    """
    Full order with lines and linked articles for the detail page.

    @param db - Session.
    @param user_id - Owner.
    @param order_id - Primary key.
    @returns Nested dict or None if missing.
    """
    o = (
        db.query(CardmarketOrder)
        .options(joinedload(CardmarketOrder.lines))
        .filter(CardmarketOrder.id == order_id, CardmarketOrder.user_id == user_id)
        .first()
    )
    if o is None:
        return None

    lines_out: list[dict[str, Any]] = []
    for ln in sorted(o.lines, key=lambda x: x.line_index):
        linked = (
            db.query(Article)
            .filter(Article.order_line_id == ln.id)
            .order_by(Article.id.asc())
            .all()
        )
        lines_out.append(
            {
                "id": ln.id,
                "line_index": ln.line_index,
                "quantity": ln.quantity,
                "raw_label": ln.raw_label,
                "pokemon_key": ln.pokemon_key,
                "card_number": ln.card_number,
                "language_code": ln.language_code,
                "condition_label": ln.condition_label,
                "set_code": ln.set_code,
                "variant_token": ln.variant_token,
                "unit_price_eur": float(ln.unit_price_eur),
                "remaining_units": remaining_units(db, ln),
                "articles": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "is_sold": a.is_sold,
                        "sold_at": a.sold_at.isoformat() if a.sold_at else None,
                    }
                    for a in linked
                ],
            }
        )

    sold_total = (
        db.query(func.count(Article.id))
        .join(CardmarketOrderLine, CardmarketOrderLine.id == Article.order_line_id)
        .filter(CardmarketOrderLine.order_id == o.id, Article.is_sold.is_(True))
        .scalar()
        or 0
    )

    sales_revenue_raw = (
        db.query(func.coalesce(func.sum(Article.sell_price), 0))
        .join(CardmarketOrderLine, CardmarketOrderLine.id == Article.order_line_id)
        .filter(CardmarketOrderLine.order_id == o.id, Article.is_sold.is_(True))
        .scalar()
    )
    sales_revenue_eur = float(sales_revenue_raw or 0)

    return {
        "id": o.id,
        "external_order_id": o.external_order_id,
        "seller_username": o.seller_username,
        "seller_display_name": o.seller_display_name,
        "seller_country_code": o.seller_country_code,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
        "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
        "items_subtotal": float(o.items_subtotal),
        "shipping_fee": float(o.shipping_fee),
        "order_total": float(o.order_total),
        "sales_revenue_eur": sales_revenue_eur,
        "source_filename": o.source_filename,
        "created_at": o.created_at.isoformat(),
        "sold_articles_count": int(sold_total),
        "lines": lines_out,
    }


def _pokemon_keys_from_match_input(name: str | None) -> list[str]:
    """
    Build normalized Pokémon keys for SQL ``IN`` from form/OCR input.

    Supports several names separated by ``|`` (FR / EN / printed) and ``/`` in
    ``Piafabec / Spearow``-style labels.

    @param name - Raw string from the client (may include pipes).
    @returns Deduped list of ``normalize_pokemon_key`` outputs.
    """
    if not name or not name.strip():
        return []
    keys: list[str] = []
    for chunk in re.split(r"[|]", name.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        for segment in re.split(r"[/]", chunk):
            k = normalize_pokemon_key(segment.strip())
            if k:
                keys.append(k)
    if not keys and name.strip():
        k = normalize_pokemon_key(name.strip())
        if k:
            keys.append(k)
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


# OCR / ISO 639 may use ``JA``; Cardmarket invoice lines use ``JP`` for Japanese.
_CARDMATCH_LANG_EQUIV: dict[str, str] = {
    "JA": "JP",
    "JPN": "JP",
}


def _normalize_cardmarket_language_for_match(raw: str | None) -> str | None:
    """Map common OCR language codes to Cardmarket line codes."""
    if not raw or not str(raw).strip():
        return None
    u = str(raw).strip().upper()
    return _CARDMATCH_LANG_EQUIV.get(u, u)


def _condition_matches(app_condition: str | None, line_cond: str | None) -> bool:
    if not app_condition or not line_cond:
        return True
    cm = _APP_CONDITION_TO_CM.get(app_condition.strip())
    if cm is None:
        return True
    return line_cond.upper() == cm.upper()


def match_order_lines(
    db: Session,
    user_id: int,
    pokemon_name: str | None,
    set_code: str | None,
    card_number: str | None,
    app_condition: str | None,
    language_code: str | None,
) -> dict[str, Any]:
    """
    Find purchase lines matching card fields; suggest FIFO link and latest purchase price.

    @param db - Session.
    @param user_id - Owner.
    @param pokemon_name - Pokémon name(s): pipe ``|`` separates variants (FR / EN); ``/`` splits
        slash labels. Matched against invoice ``pokemon_key`` (any variant).
    @param set_code - Set code (case-insensitive).
    @param card_number - Card number / fraction.
    @param app_condition - GoupixDex condition label.
    @param language_code - Optional ISO language (e.g. JP).
    @returns Candidate lines, fifo id, suggested purchase from latest buy with stock.
    """
    keys = _pokemon_keys_from_match_input(pokemon_name or "")
    num = normalize_card_number_token(card_number or "")
    set_c = (set_code or "").strip().lower()
    lang = _normalize_cardmarket_language_for_match(language_code)

    q = (
        db.query(CardmarketOrderLine)
        .join(CardmarketOrder, CardmarketOrder.id == CardmarketOrderLine.order_id)
        .filter(CardmarketOrder.user_id == user_id)
    )
    if keys:
        q = q.filter(CardmarketOrderLine.pokemon_key.in_(keys))
    if set_c:
        q = q.filter(func.lower(CardmarketOrderLine.set_code) == set_c)
    if num:
        q = q.filter(CardmarketOrderLine.card_number == num)
    if lang:
        q = q.filter(CardmarketOrderLine.language_code == lang)

    lines: list[CardmarketOrderLine] = q.order_by(
        *_order_by_paid_at_desc_nulls_last(),
        CardmarketOrderLine.id.desc(),
    ).all()

    filtered: list[CardmarketOrderLine] = []
    for ln in lines:
        if not _condition_matches(app_condition, ln.condition_label):
            continue
        if remaining_units(db, ln) <= 0:
            continue
        filtered.append(ln)

    order_ids = {ln.order_id for ln in filtered}
    order_cache: dict[int, CardmarketOrder] = {}
    if order_ids:
        for o in db.query(CardmarketOrder).filter(CardmarketOrder.id.in_(order_ids)).all():
            order_cache[o.id] = o

    def paid_ts(line: CardmarketOrderLine) -> dt.datetime | None:
        o = order_cache.get(line.order_id)
        return o.paid_at if o else None

    fifo_line_id: int | None = None
    if filtered:
        fifo_sorted = sorted(
            filtered,
            key=lambda ln: (
                paid_ts(ln) or dt.datetime.min.replace(tzinfo=dt.UTC),
                ln.order_id,
                ln.line_index,
            ),
        )
        fifo_line_id = fifo_sorted[0].id

    latest_price_line_id: int | None = None
    suggested_purchase: Decimal | None = None
    if filtered:
        latest_sorted = sorted(
            filtered,
            key=lambda ln: (paid_ts(ln) or dt.datetime.min.replace(tzinfo=dt.UTC)),
            reverse=True,
        )
        pick = latest_sorted[0]
        latest_price_line_id = pick.id
        suggested_purchase = pick.unit_price_eur

    candidates: list[dict[str, Any]] = []
    for ln in sorted(filtered, key=lambda x: paid_ts(x) or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True):
        o = order_cache[ln.order_id]
        candidates.append(
            {
                "order_line_id": ln.id,
                "order_id": ln.order_id,
                "external_order_id": o.external_order_id,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "unit_price_eur": float(ln.unit_price_eur),
                "remaining_units": remaining_units(db, ln),
            }
        )

    return {
        "candidates": candidates,
        "fifo_order_line_id": fifo_line_id,
        "latest_purchase_order_line_id": latest_price_line_id,
        "suggested_purchase_price": float(suggested_purchase) if suggested_purchase is not None else None,
    }


def assign_article_order_line(
    db: Session,
    user_id: int,
    article: Article,
    new_line_id: int | None,
) -> None:
    """
    Attach or detach an article to a purchase line; validates ownership and remaining quantity.

    @param db - Session.
    @param user_id - Article owner.
    @param article - Row to update (mutated in memory).
    @param new_line_id - Target purchase line id or None to clear.
    @raises ValueError - Invalid line or no remaining quantity.
    """
    if new_line_id is None:
        article.order_line_id = None
        return
    if article.order_line_id == new_line_id:
        return
    if not validate_order_line_owner(db, user_id, new_line_id):
        raise ValueError("purchase_line_not_found")
    line = db.query(CardmarketOrderLine).filter(CardmarketOrderLine.id == new_line_id).first()
    if line is None:
        raise ValueError("purchase_line_not_found")
    if remaining_units(db, line) < 1:
        raise ValueError("purchase_line_full")
    article.order_line_id = new_line_id


def validate_order_line_owner(db: Session, user_id: int, order_line_id: int) -> bool:
    """
    Return True if the order line belongs to the user's order tree.

    @param db - Session.
    @param user_id - Owner.
    @param order_line_id - Line pk.
    """
    row = (
        db.query(CardmarketOrderLine.id)
        .join(CardmarketOrder, CardmarketOrder.id == CardmarketOrderLine.order_id)
        .filter(CardmarketOrderLine.id == order_line_id, CardmarketOrder.user_id == user_id)
        .first()
    )
    return row is not None


