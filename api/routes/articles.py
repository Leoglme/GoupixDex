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
from core.security import decrypt_ebay_token
from models.article import Article
from models.image import Image as ImageModel
from models.user import User
from schemas.articles import ArticleUpdate, BulkIdsBody, SoldPatch, VintedBatchStartBody
from services import article_service
from services.combined_marketplace_service import CombinedMarketplaceService
from services.ebay_background_service import EbayBackgroundService
from services.user_settings_service import ebay_listing_config_complete, get_or_create_user_settings
from services.vinted_batch_session_service import VintedBatchSessionService as vinted_batch_hub
from services.vinted_progress_session_service import VintedProgressSessionService as vinted_progress_hub
from services import supabase_storage_service
from services.vinted_background_service import VintedBackgroundService
from services.vinted_batch_background_service import VintedBatchBackgroundService

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


def _parse_sold_at_iso(value: str | None) -> dt.datetime | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=dt.UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sold_at (expected ISO 8601 or YYYY-MM-DD).",
        ) from exc


def _parse_optional_iso_dt(value: str | None) -> dt.datetime | None:
    """Parse ISO-ish datetime without raising (e.g. wardrobe import)."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=dt.UTC)
    except ValueError:
        return None


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_articles(
    body: BulkIdsBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Delete multiple articles owned by the authenticated user."""
    unique_ids = list(dict.fromkeys(body.ids))
    deleted = article_service.delete_articles_by_ids(db, user.id, unique_ids)
    return {"deleted": deleted, "requested": len(unique_ids)}


@router.get("/vinted-batch/active")
def vinted_batch_active(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Active grouped Vinted job for this user, if any (otherwise null)."""
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
    """SSE: logs + ``progress`` events for a Vinted batch job."""
    owner = vinted_batch_hub.get_job_user_id(job_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    if owner != user.id:
        raise HTTPException(status_code=403, detail="Access denied for this job.")

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
    Queue a batch of Vinted listings (single browser, sequential listings).
    Follow ``GET /articles/vinted-batch/{job_id}/stream``.
    """
    ms = get_or_create_user_settings(db, user.id)
    if not ms.vinted_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vinted is disabled in your marketplace settings.",
        )
    unique_ids = list(dict.fromkeys(body.article_ids))
    for aid in unique_ids:
        article = article_service.get_article(db, aid, user.id)
        if article is None:
            raise HTTPException(status_code=400, detail=f"Article {aid} not found.")
        if not article.images:
            raise HTTPException(
                status_code=400,
                detail=f"Article {aid} has no images (required for Vinted).",
            )

    job_id = str(uuid.uuid4())
    if not vinted_batch_hub.try_register_job(job_id, user.id):
        raise HTTPException(
            status_code=409,
            detail="A grouped Vinted publish is already running for this account.",
        )

    background_tasks.add_task(
        VintedBatchBackgroundService.run_vinted_batch_publish_job,
        job_id,
        user.id,
        unique_ids,
    )
    return {
        "job_id": job_id,
        "stream_path": f"/articles/vinted-batch/{job_id}/stream",
    }


@router.post("/ebay-batch", status_code=status.HTTP_202_ACCEPTED)
def start_ebay_batch(
    body: VintedBatchStartBody,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Queue sequential eBay Inventory publishes (one article after another)."""
    ms = get_or_create_user_settings(db, user.id)
    if not ms.ebay_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="eBay is disabled in your marketplace settings.",
        )
    if not ebay_listing_config_complete(ms):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete eBay listing settings (category, location, policies) before batch publish.",
        )
    if not decrypt_ebay_token(user.ebay_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect eBay (OAuth) before publishing.",
        )
    unique_ids = list(dict.fromkeys(body.article_ids))
    for aid in unique_ids:
        article = article_service.get_article(db, aid, user.id)
        if article is None:
            raise HTTPException(status_code=400, detail=f"Article {aid} not found.")
        if article.is_sold:
            raise HTTPException(status_code=400, detail=f"Article {aid} is sold.")
        if not any((img.image_url or "").startswith("https://") for img in article.images):
            raise HTTPException(
                status_code=400,
                detail=f"Article {aid} needs at least one HTTPS image for eBay.",
            )

    # Enregistre les canaux SSE **avant** de retourner 202 : `BackgroundTasks`
    # ne démarre qu'après l'envoi de la réponse, et le front ouvre
    # `GET /articles/{id}/listing-progress` dès réception → sans ces registers
    # upfront, l'ouverture du SSE gagne la course et on renvoie l'erreur
    # « Aucune session de publication pour cet article. » alors que la publication
    # va en fait se dérouler juste après sans logs visibles côté UI.
    for aid in unique_ids:
        vinted_progress_hub.register(aid)

    background_tasks.add_task(
        EbayBackgroundService.run_ebay_batch_sequential,
        user.id,
        unique_ids,
    )
    return {"queued": len(unique_ids)}


@router.get("")
def list_articles(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    rows = article_service.list_articles_for_user(db, user.id)
    return [article_service.article_to_dict(a) for a in rows]


@router.get("/{article_id}/listing-progress")
@router.get("/{article_id}/vinted-progress", include_in_schema=False)
async def article_listing_progress_stream(
    article_id: int,
    user: Annotated[User, Depends(get_current_user_from_token_str)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """
    SSE stream for Vinted and/or eBay publish steps (JWT via ``Authorization`` or ``?token=``).
    Legacy path: ``/vinted-progress`` (alias).
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
    Start Vinted publish for an existing article (images already stored).
    Follow SSE ``GET /articles/{id}/listing-progress``.
    """
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.is_sold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Article already sold — not suitable for Vinted listing.",
        )
    image_urls = [img.image_url for img in article.images]
    if not image_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one image is required to publish on Vinted.",
        )
    ms = get_or_create_user_settings(db, user.id)
    if not ms.vinted_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vinted is disabled in your marketplace settings.",
        )

    vinted_progress_hub.register(article_id)
    background_tasks.add_task(
        VintedBackgroundService.run_vinted_publish_job,
        article_id,
        user.id,
        image_urls,
    )
    return {
        "vinted": {
            "status": "running",
            "stream_path": f"/articles/{article_id}/listing-progress",
        },
    }


@router.post("/{article_id}/confirm-vinted-publish", status_code=status.HTTP_200_OK)
def confirm_vinted_publish(
    article_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Mark the article as published on Vinted after success from the local desktop worker.
    """
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article_service.mark_article_published_on_vinted(article_id, user.id)
    return {"ok": True}


@router.post("/{article_id}/publish-ebay")
def publish_ebay_for_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Start eBay publish (Inventory API) for an existing article."""
    article = article_service.get_article(db, article_id, user.id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.is_sold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Article already sold — not suitable for eBay listing.",
        )
    if not any((img.image_url or "").startswith("https://") for img in article.images):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one HTTPS image is required for eBay.",
        )
    ms = get_or_create_user_settings(db, user.id)
    if not ms.ebay_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="eBay is disabled in your marketplace settings.",
        )
    if not ebay_listing_config_complete(ms):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete eBay listing settings (category, location, policies) first.",
        )
    if not decrypt_ebay_token(user.ebay_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect eBay (OAuth) first.",
        )

    vinted_progress_hub.register(article_id)
    background_tasks.add_task(
        EbayBackgroundService.run_ebay_publish_job,
        article_id,
        user.id,
    )
    return {
        "ebay": {
            "status": "running",
            "stream_path": f"/articles/{article_id}/listing-progress",
        },
    }


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
    sold_price: str | None = Form(None),
    sale_source: str | None = Form(None),
    publish_to_vinted: str | None = Form(None),
    publish_to_ebay: str | None = Form(None),
    is_sold: str | None = Form(None),
    sold_at: str | None = Form(None),
    wardrobe_vinted_listed: str | None = Form(None),
    vinted_published_at: str | None = Form(None),
    images: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    settings = get_settings()
    sold_flag = _form_bool(is_sold)
    sold_at_dt = _parse_sold_at_iso(sold_at) if sold_flag else None
    if sold_flag and sold_at_dt is None:
        sold_at_dt = dt.datetime.now(dt.UTC)

    sell_dec = _parse_decimal(sell_price)
    proceeds_dec = _parse_decimal(sold_price) if sold_flag and sold_price else None
    if sold_flag and proceeds_dec is None:
        proceeds_dec = sell_dec

    sale_src: str | None = None
    if sold_flag:
        raw_ss = (sale_source or "").strip().lower()
        if raw_ss in ("vinted", "ebay"):
            sale_src = raw_ss[:16]
        elif _form_bool(wardrobe_vinted_listed):
            sale_src = "vinted"

    article = Article(
        user_id=user.id,
        title=title.strip(),
        description=description,
        pokemon_name=pokemon_name.strip() if pokemon_name else None,
        set_code=set_code.strip() if set_code else None,
        card_number=card_number.strip() if card_number else None,
        condition=condition.strip() or "Near Mint",
        purchase_price=_parse_decimal_required(purchase_price),
        sell_price=sell_dec,
        sold_price=proceeds_dec if sold_flag else None,
        sale_source=sale_src,
        is_sold=sold_flag,
        sold_at=sold_at_dt if sold_flag else None,
    )

    if _form_bool(wardrobe_vinted_listed):
        article.published_on_vinted = True
        vp = _parse_optional_iso_dt(vinted_published_at)
        if vp is not None:
            article.vinted_published_at = vp
        elif not sold_flag:
            article.vinted_published_at = dt.datetime.now(dt.UTC)
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

    ms = get_or_create_user_settings(db, user.id)
    raw_want_vinted = _form_bool(publish_to_vinted) and not sold_flag
    want_vinted = raw_want_vinted and ms.vinted_enabled
    raw_want_ebay = _form_bool(publish_to_ebay) and not sold_flag

    stream_path = f"/articles/{article.id}/listing-progress"
    want_both_server = (
        want_vinted
        and not vinted_local_desktop
        and raw_want_ebay
        and ms.ebay_enabled
        and ebay_listing_config_complete(ms)
        and bool(decrypt_ebay_token(user.ebay_refresh_token))
        and any(str(u).startswith("https://") for u in stored_sources)
    )

    if raw_want_vinted and not ms.vinted_enabled:
        vinted_result = {"published": False, "skipped": True, "detail": "vinted_disabled"}
    elif want_both_server:
        vinted_progress_hub.register(article.id)
        background_tasks.add_task(
            CombinedMarketplaceService.run_vinted_then_ebay,
            article.id,
            user.id,
            stored_sources,
        )
        vinted_result = {"status": "running", "stream_path": stream_path}
        ebay_result = {"status": "running", "stream_path": stream_path}
    elif want_vinted and vinted_local_desktop:
        vinted_result = {
            "status": "pending",
            "stream_path": stream_path,
            "desktop_local": True,
        }
    elif want_vinted:
        vinted_progress_hub.register(article.id)
        background_tasks.add_task(
            VintedBackgroundService.run_vinted_publish_job,
            article.id,
            user.id,
            stored_sources,
        )
        vinted_result = {
            "status": "running",
            "stream_path": stream_path,
        }
    else:
        vinted_result = {"published": False, "skipped": True, "detail": "not_requested"}

    if not want_both_server:
        ebay_result = {"published": False, "skipped": True, "detail": "not_requested"}
        if raw_want_ebay:
            if not ms.ebay_enabled:
                ebay_result = {"skipped": True, "detail": "ebay_disabled"}
            elif not ebay_listing_config_complete(ms):
                ebay_result = {"skipped": True, "detail": "ebay_listing_config_incomplete"}
            elif not decrypt_ebay_token(user.ebay_refresh_token):
                ebay_result = {"skipped": True, "detail": "ebay_not_connected"}
            elif not any(str(u).startswith("https://") for u in stored_sources):
                ebay_result = {"skipped": True, "detail": "ebay_requires_https_images"}
            else:
                vinted_progress_hub.register(article.id)
                background_tasks.add_task(
                    EbayBackgroundService.run_ebay_publish_job,
                    article.id,
                    user.id,
                )
                ebay_result = {"status": "running", "stream_path": stream_path}

    return {
        "article": article_service.article_to_dict(article),
        "vinted": vinted_result,
        "ebay": ebay_result,
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
    article.sold_price = body.sold_price
    article.sale_source = body.sale_source
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
