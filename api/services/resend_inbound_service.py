"""Resend inbound webhooks: signature verification, fetch body, OTP extraction."""

from __future__ import annotations

import logging
import re
from typing import Any

import resend
from resend.webhooks._webhook import VerifyWebhookOptions, WebhookHeaders

logger = logging.getLogger(__name__)

AMAZON_PROVISION_EMAIL_DOMAIN = "mail.goupixdex.dibodev.fr"

_AMAZON_OTP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'class="data">\s*(\d{6})\s*<'),
    re.compile(r"(?i)mot de passe à usage unique \(OTP\) suivant[^\d]{0,120}(\d{6})"),
    re.compile(r"(?i)OTP\)\s*suivant[^0-9]{0,40}:?\s*(\d{6})"),
    re.compile(r"(?i)\b(\d{6})\b\s+est\s+votre\s+code"),
    re.compile(r":(\d{6})(?:\s|$)"),
)


def _normalize_recipient(raw: str) -> str:
    addr = raw.strip().lower()
    if addr.startswith("<") and addr.endswith(">"):
        addr = addr[1:-1].strip()
    return addr


def recipient_is_provision_inbox(address: str) -> bool:
    addr = _normalize_recipient(address)
    return addr.endswith(f"@{AMAZON_PROVISION_EMAIL_DOMAIN}")


def extract_otp_from_content(*, text: str | None, html: str | None) -> str | None:
    """Amazon FR : OTP dans le texte (`:502122`) ou bloc HTML `class=\"data\"`."""
    plain = (text or "").strip()
    markup = (html or "").strip()
    for haystack in (plain, markup):
        if not haystack:
            continue
        for pattern in _AMAZON_OTP_PATTERNS:
            match = pattern.search(haystack)
            if match:
                return match.group(1)
    if plain:
        match = re.search(r"\b(\d{6})\b", plain)
        if match:
            return match.group(1)
    return None


def verify_resend_webhook(
    *,
    payload: str,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
    webhook_secret: str,
) -> Any:
    if not svix_id or not svix_timestamp or not svix_signature:
        raise ValueError("Missing Svix webhook headers")
    return resend.Webhooks.verify(
        VerifyWebhookOptions(
            payload=payload,
            headers=WebhookHeaders(
                id=svix_id,
                timestamp=svix_timestamp,
                signature=svix_signature,
            ),
            webhook_secret=webhook_secret,
        ),
    )


def fetch_received_email_body(*, api_key: str, email_id: str) -> resend.ReceivedEmail:
    resend.api_key = api_key
    return resend.Emails.Receiving.get(email_id)


def process_email_received_event(*, api_key: str, email_id: str, to_addresses: list[str]) -> dict[str, Any]:
    provision_recipients = [a for a in to_addresses if recipient_is_provision_inbox(a)]
    if not provision_recipients:
        logger.info("Resend inbound ignored email_id=%s (not provision domain)", email_id[:8])
        return {"stored": False, "reason": "not_provision_domain"}

    received = fetch_received_email_body(api_key=api_key, email_id=email_id)
    if isinstance(received, dict):
        text = received.get("text") or received.get("body")
        html = received.get("html")
        from_addr = received.get("from") or ""
        subject = received.get("subject")
    else:
        text = getattr(received, "text", None) or getattr(received, "body", None)
        html = getattr(received, "html", None)
        from_addr = getattr(received, "from", "") or ""
        subject = getattr(received, "subject", None)
    otp = extract_otp_from_content(text=text if isinstance(text, str) else None, html=html if isinstance(html, str) else None)

    from services.amazon_provision_inbound_service import upsert_inbound_message

    row = upsert_inbound_message(
        resend_email_id=email_id,
        to_address=_normalize_recipient(provision_recipients[0]),
        from_address=_normalize_recipient(str(from_addr)),
        subject=(str(subject or ""))[:512] or None,
        body_text=text if isinstance(text, str) else None,
        otp_code=otp,
    )

    logger.info(
        "Resend inbound stored email_id=%s to=%s otp=%s",
        email_id[:8],
        row["to_address"],
        "yes" if otp else "no",
    )
    return {"stored": True, "to": row["to_address"], "otp": otp}
