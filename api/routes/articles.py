"""Articles (cards) CRUD and Vinted publish."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import get_settings
from core.database import get_db
from core.deps import get_current_user, get_current_user_from_token_str
from models.article import Article
from models.image import Image as ImageModel
from models.user import User
from schemas.articles import ArticleUpdate, BulkIdsBody, SoldPatch, VintedBatchStartBody
from services import article_service
from services import vinted_batch_progress as vinted_batch_hub
from services import vinted_progress as vinted_progress_hub
from services import supabase_storage_service
from services.vinted_background import run_vinted_publish_job
from services.vinted_batch_background import run_vinted_batch_publish_job

router = APIRouter(prefix="/articles", tags=["articles"])


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value).strip())


def _parse_decimal_required(value: str) -> Decimal:
    return Decimal(str(value).strip())


def _form_bool(value: str | None) -> bool:
    if value is None or str(value).strip() == "":
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "on")


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_articles(
    body: BulkIdsBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Supprime plusieurs articles appartenant à l'utilisateur connecté."""
    unique_ids = list(dict.fromkeys(body.ids))
    deleted = article_service.delete_articles_by_ids(db, user.id, unique_ids)
    return {"deleted": deleted, "requested": len(unique_ids)}


@router.get("/vinted-batch/active")
def vinted_batch_active(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Job Vinted groupé en cours pour cet utilisateur (sinon null)."""
    jid = vinted_batch_hub.get_active_job_id(user.id)
    return {
        "job_id": jid,
        "stream_path": f"/articles/vinted-batch/{jid}/stream" if jid else None,
    }


@router.get("/vinted-batch/{job_id}/stream")
async def vinted_batch_stream(
    job_id: str,
    user: Annotated[User, Depends(get_current_user_from_token_str)],
) -> StreamingResponse:
    """SSE : logs + événements ``progress`` pour un lot Vinted."""
    owner = vinted_batch_hub.get_job_user_id(job_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    if owner != user.id:
        raise HTTPException(status_code=403, detail="Accès refusé à ce job.")

    async def generate():
        async for ev in vinted_batch_hub.event_stream(job_id):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/vinted-batch", status_code=status.HTTP_202_ACCEPTED)
def start_vinted_batch(
    body: VintedBatchStartBody,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Enfile un lot de publications Vinted (navigateur unique, annonces enchaînées).
    Suivre ``GET /articles/vinted-batch/{job_id}/stream``.
    """
    unique_ids = list(dict.fromkeys(body.article_ids))
    for aid in unique_ids:
        article = article_service.get_article(db, aid, user.id)
        if article is None:
            raise HTTPException(status_code=400, detail=f"Article {aid} introuvable.")
        if not article.images:
            raise HTTPException(
                status_code=400,
                detail=f"L'article {aid} n'a pas d'image (requis pour Vinted).",
            )

    job_id = str(uuid.uuid4())
    if not vinted_batch_hub.try_register_job(job_id, user.id):
        raise HTTPException(
            status_code=409,
            detail="Une publication Vinted groupée est déjà en cours pour ce compte.",
        )

    background_tasks.add_task(
        run_vinted_batch_publish_job,
        job_id,
        user.id,
        unique_ids,
    )
    return {
        "job_id": job_id,
        "stream_path": f"/articles/vinted-batch/{job_id}/stream",
    }


@router.get("")
def list_articles(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    rows = article_service.list_articles_for_user(db, user.id)
    return [article_service.article_to_dict(a) for a in rows]


@router.get("/{article_id}/vinted-progress")
async def vinted_progress_stream(
    article_id: int,
    user: Annotated[User, Depends(get_current_user_from_token_str)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """
    Flux SSE des étapes de publication Vinted (JWT via ``Authorization`` ou ``?token=``).
    """
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    async def generate():
        async for ev in vinted_progress_hub.event_stream(article_id):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.post("/{article_id}/publish-vinted")
def publish_vinted_for_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Lance la publication Vinted pour un article existant (images déjà enregistrées).
    Suivre le flux SSE ``GET /articles/{id}/vinted-progress``.
    """
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.is_sold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Article déjà vendu — publication sur Vinted inadaptée.",
        )
    image_urls = [img.image_url for img in article.images]
    if not image_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins une image est requise pour publier sur Vinted.",
        )

    vinted_progress_hub.register(article_id)
    background_tasks.add_task(
        run_vinted_publish_job,
        article_id,
        user.id,
        image_urls,
    )
    return {
        "vinted": {
            "status": "running",
            "stream_path": f"/articles/{article_id}/vinted-progress",
        },
    }


@router.post("/{article_id}/confirm-vinted-publish", status_code=status.HTTP_200_OK)
def confirm_vinted_publish(
    article_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Marque l'article comme publié sur Vinted après succès du worker desktop local.
    """
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article_service.mark_article_published_on_vinted(article_id, user.id)
    return {"ok": True}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_article(
    request: Request,
    background_tasks: BackgroundTasks,
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
    publish_to_vinted: str | None = Form(None),
    images: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    settings = get_settings()
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

    stored_sources: list[str] = []
    upload_list = images or []
    if upload_list and not supabase_storage_service.is_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Storage is not configured (SUPABASE_URL, SUPABASE_API_KEY, SUPABASE_STORAGE_BUCKET).",
        )

    for upload in upload_list:
        raw = await upload.read()
        if not raw:
            continue
        public_url = await supabase_storage_service.upload_image_bytes(
            user_id=user.id,
            article_id=article.id,
            data=raw,
            original_filename=upload.filename,
        )
        db.add(ImageModel(article_id=article.id, image_url=public_url))
        stored_sources.append(public_url)

    db.commit()
    db.refresh(article)

    vinted_local_desktop = request.headers.get("x-goupix-vinted-target", "").strip().lower() == "local"

    if _form_bool(publish_to_vinted) and vinted_local_desktop:
        vinted_result = {
            "status": "pending",
            "stream_path": f"/articles/{article.id}/vinted-progress",
            "desktop_local": True,
        }
    elif _form_bool(publish_to_vinted):
        vinted_progress_hub.register(article.id)
        background_tasks.add_task(
            run_vinted_publish_job,
            article.id,
            user.id,
            stored_sources,
        )
        vinted_result = {
            "status": "running",
            "stream_path": f"/articles/{article.id}/vinted-progress",
        }
    else:
        vinted_result = {"published": False, "skipped": True, "detail": "not_requested"}
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
