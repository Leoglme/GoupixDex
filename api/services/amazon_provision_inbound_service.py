"""Persist inbound OTP e-mails for Amazon account provisioning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import SessionLocal


class InboundMessageRow(TypedDict):
    to_address: str
    otp_code: str | None
    received_at: datetime


def upsert_inbound_message(
    *,
    resend_email_id: str,
    to_address: str,
    from_address: str,
    subject: str | None,
    body_text: str | None,
    otp_code: str | None,
) -> InboundMessageRow:
    with SessionLocal() as db:
        return _upsert_inbound_message(
            db,
            resend_email_id=resend_email_id,
            to_address=to_address,
            from_address=from_address,
            subject=subject,
            body_text=body_text,
            otp_code=otp_code,
        )


def _upsert_inbound_message(
    db: Session,
    *,
    resend_email_id: str,
    to_address: str,
    from_address: str,
    subject: str | None,
    body_text: str | None,
    otp_code: str | None,
) -> InboundMessageRow:
    db.execute(
        text(
            """
            INSERT INTO amazon_provision_inbound_messages (
              resend_email_id, to_address, from_address, subject, body_text, otp_code
            ) VALUES (
              :resend_email_id, :to_address, :from_address, :subject, :body_text, :otp_code
            )
            ON DUPLICATE KEY UPDATE
              from_address = VALUES(from_address),
              subject = VALUES(subject),
              body_text = VALUES(body_text),
              otp_code = COALESCE(VALUES(otp_code), otp_code)
            """
        ),
        {
            "resend_email_id": resend_email_id,
            "to_address": to_address,
            "from_address": from_address or None,
            "subject": subject,
            "body_text": body_text,
            "otp_code": otp_code,
        },
    )
    db.commit()
    row = db.execute(
        text(
            """
            SELECT to_address, otp_code, received_at
            FROM amazon_provision_inbound_messages
            WHERE resend_email_id = :id
            LIMIT 1
            """
        ),
        {"id": resend_email_id},
    ).mappings().first()
    if row is None:
        raise RuntimeError("Inbound message insert failed")
    return InboundMessageRow(
        to_address=str(row["to_address"]),
        otp_code=row["otp_code"],
        received_at=row["received_at"],
    )


def register_inbound_watch(*, user_id: int, email: str, ttl_minutes: int = 45) -> None:
    normalized = email.strip().lower()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO amazon_provision_inbound_watch (user_id, email, expires_at)
                VALUES (:user_id, :email, :expires_at)
                ON DUPLICATE KEY UPDATE expires_at = VALUES(expires_at)
                """
            ),
            {"user_id": user_id, "email": normalized, "expires_at": expires_at.replace(tzinfo=None)},
        )
        db.commit()


def user_may_read_inbound_code(*, user_id: int, email: str) -> bool:
    normalized = email.strip().lower()
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT 1
                FROM amazon_provision_inbound_watch
                WHERE user_id = :user_id
                  AND email = :email
                  AND expires_at >= UTC_TIMESTAMP()
                LIMIT 1
                """
            ),
            {"user_id": user_id, "email": normalized},
        ).first()
    return row is not None


def latest_otp_for_recipient(to_address: str) -> str | None:
    normalized = to_address.strip().lower()
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT otp_code
                FROM amazon_provision_inbound_messages
                WHERE to_address = :to_address
                  AND otp_code IS NOT NULL
                  AND received_at >= (UTC_TIMESTAMP() - INTERVAL 30 MINUTE)
                ORDER BY received_at DESC
                LIMIT 1
                """
            ),
            {"to_address": normalized},
        ).mappings().first()
    if not row:
        return None
    code = row["otp_code"]
    return str(code) if code else None
