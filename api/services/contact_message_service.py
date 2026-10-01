"""Messages of the contact page: mailed to the publisher's inbox through Resend, with the visitor as Reply-To."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from collections import deque
from zoneinfo import ZoneInfo

import resend
from sqlalchemy.orm import Session

from config import get_settings
from models.user import User
from schemas.contact import ContactMessageCreate
from services.contact_email import render_contact_email

logger = logging.getLogger(__name__)

#: At most this many messages per visitor (IP address) in one hour.
MAX_MESSAGES_PER_HOUR = 5
_WINDOW_SECONDS = 3600.0
#: Past this many visitors in memory, the ones silent for an hour are forgotten.
_MAX_TRACKED_VISITORS = 1000
_PARIS_TZ = ZoneInfo("Europe/Paris")
_ACCOUNT_LABELS: dict[str, str] = {
    "approved": "Accès actif",
    "pending": "Demande d'accès en attente",
    "rejected": "Demande d'accès refusée",
    "banned": "Compte bloqué",
}

_lock = asyncio.Lock()
_recent_messages: dict[str, deque[float]] = {}


class ContactDeliveryError(Exception):
    """The message could not be mailed: the visitor has to try again or write directly."""


async def allow_message_from(visitor_key: str) -> bool:
    """
    Count a message from ``visitor_key`` and say whether it stays within the hourly limit.

    Args:
        visitor_key: Who sends the message (the client IP address).

    Returns:
        False once the visitor already sent ``MAX_MESSAGES_PER_HOUR`` messages in the last hour.
    """
    now = time.monotonic()
    async with _lock:
        if len(_recent_messages) > _MAX_TRACKED_VISITORS:
            silent_visitors = [key for key, sent in _recent_messages.items() if now - sent[-1] >= _WINDOW_SECONDS]
            for key in silent_visitors:
                del _recent_messages[key]
        sent_times = _recent_messages.setdefault(visitor_key, deque())
        while sent_times and now - sent_times[0] >= _WINDOW_SECONDS:
            sent_times.popleft()
        if len(sent_times) >= MAX_MESSAGES_PER_HOUR:
            return False
        sent_times.append(now)
        return True


def describe_account(db: Session, email: str) -> str:
    """
    Say whether the visitor already has a GoupixDex account, and where its access stands.

    Args:
        db: Active database session.
        email: The visitor's e-mail address.

    Returns:
        « Accès actif », « Demande d'accès en attente »… or « Aucun compte ».
    """
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        return "Aucun compte"
    return _ACCOUNT_LABELS.get(user.status, user.status)


async def send_contact_message(db: Session, message: ContactMessageCreate) -> None:
    """
    Mail the message to the publisher's inbox, with the visitor as Reply-To so a plain reply answers them.

    Args:
        db: Active database session.
        message: The visitor's message.

    Raises:
        ContactDeliveryError: When Resend is not configured on this server or refuses the e-mail.
    """
    settings = get_settings()
    if not settings.resend_api_key:
        raise ContactDeliveryError("RESEND_API_KEY is not set")
    email = render_contact_email(
        message,
        received_at=dt.datetime.now(_PARIS_TZ),
        account_label=describe_account(db, str(message.email)),
    )
    params: resend.Emails.SendParams = {
        "from": settings.contact_form_from,
        "to": [settings.contact_form_to],
        "subject": email.subject,
        "html": email.html,
        "text": email.text,
        "reply_to": str(message.email),
    }
    try:
        await asyncio.to_thread(_send_with_resend, settings.resend_api_key, params)
    except Exception as exc:
        logger.error("Contact message from %s not mailed: %s", message.email, exc)
        raise ContactDeliveryError(str(exc)) from exc


def _send_with_resend(api_key: str, params: resend.Emails.SendParams) -> None:
    """Blocking Resend call, run in a worker thread."""
    resend.api_key = api_key
    resend.Emails.send(params)
