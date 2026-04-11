from decimal import Decimal

from pydantic import BaseModel, Field


class ArticleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    pokemon_name: str | None = None
    set_code: str | None = None
    card_number: str | None = None
    condition: str | None = None
    purchase_price: Decimal | None = None
    sell_price: Decimal | None = None


class SoldPatch(BaseModel):
    sell_price: Decimal = Field(ge=0)
