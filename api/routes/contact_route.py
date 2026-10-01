"""Public contact page: ``POST /contact`` mails the visitor's message to the publisher."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.contact import ContactMessageCreate, ContactMessageSentResponse
from services import contact_message_service

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", response_model=ContactMessageSentResponse)
async def send_contact_message(
    body: ContactMessageCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> ContactMessageSentResponse:
    """Mail a contact-page message; a filled honeypot gets the same answer, without any e-mail."""
    if body.website:
        return ContactMessageSentResponse()
    visitor_key = request.client.host if request.client else "unknown"
    if not await contact_message_service.allow_message_from(visitor_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de messages envoyés en peu de temps. "
            "Réessayez dans une heure ou écrivez à contact@dibodev.fr.",
        )
    try:
        await contact_message_service.send_contact_message(db, body)
    except contact_message_service.ContactDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Votre message n'est pas parti. Réessayez dans un instant ou écrivez à contact@dibodev.fr.",
        ) from None
    return ContactMessageSentResponse()
