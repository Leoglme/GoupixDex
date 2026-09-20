"""Resend webhooks (inbound e-mail for Amazon provision)."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status

from config import get_settings
from services.resend_inbound_service import process_email_received_event, verify_resend_webhook

logger = logging.getLogger(__name__)
router = APIRouter()


def _email_received_payload(event: object) -> tuple[str, list[str]] | None:
    """Resend verify() returns a dict (TypedDict) — pas de isinstance() dessus."""
    if not isinstance(event, dict):
        return None
    if event.get("type") != "email.received":
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    email_id = data.get("email_id")
    if not email_id:
        return None
    raw_to = data.get("to")
    to_list = [str(x) for x in raw_to] if isinstance(raw_to, list) else []
    return str(email_id), to_list


@router.post("/resend")
async def resend_webhook(request: Request) -> dict[str, str]:
    settings = get_settings()
    if not settings.resend_webhook_secret or not settings.resend_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resend webhook is not configured on this server",
        )

    payload = (await request.body()).decode("utf-8")
    headers = request.headers

    try:
        event = await asyncio.to_thread(
            verify_resend_webhook,
            payload=payload,
            svix_id=headers.get("svix-id"),
            svix_timestamp=headers.get("svix-timestamp"),
            svix_signature=headers.get("svix-signature"),
            webhook_secret=settings.resend_webhook_secret,
        )
    except Exception:
        logger.warning("Resend webhook signature verification failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature") from None

    received = _email_received_payload(event)
    if received is not None:
        email_id, to_addresses = received
        await asyncio.to_thread(
            process_email_received_event,
            api_key=settings.resend_api_key,
            email_id=email_id,
            to_addresses=to_addresses,
        )

    return {"status": "ok"}
