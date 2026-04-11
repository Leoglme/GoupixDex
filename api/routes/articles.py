"""Articles (cards) CRUD and Vinted publish."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from config import get_settings
from core.database import get_db
from core.deps import get_current_user
from models.article import Article
from models.image import Image as ImageModel
from models.user import User
from schemas.articles import ArticleUpdate, SoldPatch
from services import article_service
from services.vinted_publish_service import publish_article_to_vinted

router = APIRouter(prefix="/articles", tags=["articles"])


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value).strip())


def _parse_decimal_required(value: str) -> Decimal:
    return Decimal(str(value).strip())


@router.get("")
def list_articles(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    rows = article_service.list_articles_for_user(db, user.id)
    return [article_service.article_to_dict(a) for a in rows]


@router.get("/{article_id}")
def get_article(
    article_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article_service.article_to_dict(article)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_article(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    title: str = Form(),
    description: str = Form(),
    purchase_price: str = Form(),
    pokemon_name: str | None = Form(None),
    set_code: str | None = Form(None),
    card_number: str | None = Form(None),
    condition: str = Form("Near Mint"),
    sell_price: str | None = Form(None),
    images: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    settings = get_settings()
    base_upload = Path(settings.upload_dir)
    article = Article(
        user_id=user.id,
        title=title.strip(),
        description=description,
        pokemon_name=pokemon_name.strip() if pokemon_name else None,
        set_code=set_code.strip() if set_code else None,
        card_number=card_number.strip() if card_number else None,
        condition=condition.strip() or "Near Mint",
        purchase_price=_parse_decimal_required(purchase_price),
        sell_price=_parse_decimal(sell_price),
        is_sold=False,
    )
    db.add(article)
    db.flush()

    user_dir = base_upload / str(user.id) / str(article.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_paths: list[Path] = []
    upload_list = images or []

    for upload in upload_list:
        raw = await upload.read()
        if not raw:
            continue
        ext = Path(upload.filename or "img").suffix or ".jpg"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = user_dir / safe_name
        dest.write_bytes(raw)
        rel_url = f"/uploads/{user.id}/{article.id}/{safe_name}"
        db.add(ImageModel(article_id=article.id, image_url=rel_url))
        stored_paths.append(dest)

    db.commit()
    db.refresh(article)

    vinted_result = await publish_article_to_vinted(article, user, stored_paths)
    return {
        "article": article_service.article_to_dict(article),
        "vinted": vinted_result,
    }


@router.put("/{article_id}")
def update_article(
    article_id: int,
    body: ArticleUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article_service.update_article_fields(
        article,
        title=body.title,
        description=body.description,
        pokemon_name=body.pokemon_name,
        set_code=body.set_code,
        card_number=body.card_number,
        condition=body.condition,
        purchase_price=body.purchase_price,
        sell_price=body.sell_price,
    )
    db.commit()
    db.refresh(article)
    return article_service.article_to_dict(article)


@router.patch("/{article_id}/sold")
def mark_sold(
    article_id: int,
    body: SoldPatch,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article.is_sold = True
    article.sold_at = dt.datetime.now(dt.UTC)
    article.sell_price = body.sell_price
    db.commit()
    db.refresh(article)
    return article_service.article_to_dict(article)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(
    article_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
