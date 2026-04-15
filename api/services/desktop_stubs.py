"""Objets Article / User non persistés pour réutiliser la logique Vinted sans DB locale."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from models.article import Article
from models.user import User


def article_from_api_dict(d: dict[str, Any]) -> Article:
    a = Article()
    a.id = d["id"]
    a.user_id = d["user_id"]
    a.title = d["title"]
    a.description = d["description"]
    a.pokemon_name = d.get("pokemon_name")
    a.set_code = d.get("set_code")
    a.card_number = d.get("card_number")
    a.condition = d.get("condition") or "Near Mint"
    a.purchase_price = Decimal(str(d["purchase_price"]))
    sp = d.get("sell_price")
    a.sell_price = Decimal(str(sp)) if sp is not None else None
    a.is_sold = bool(d.get("is_sold", False))
    return a


def user_stub(user_id: int, email: str, vinted_email: str | None) -> User:
    u = User()
    u.id = user_id
    u.email = email
    u.vinted_email = vinted_email
    u.vinted_password = None
    return u
