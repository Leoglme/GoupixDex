"""Amazon account vault — CRUD, credentials reveal, active account selection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.security import decrypt_vinted_credential, encrypt_vinted_credential
from models.amazon_account import AmazonAccount
from models.user import User
from schemas.amazon_accounts import (
    AmazonAccountCreate,
    AmazonAccountCredentials,
    AmazonAccountResponse,
    AmazonAccountUpdate,
    AmazonAccountsOverview,
    AmazonActiveAccountUpdate,
    AmazonProvisionInboundCodeResponse,
    AmazonProvisionInboundWatchRequest,
)
from services.amazon_provision_inbound_service import (
    latest_otp_for_recipient,
    register_inbound_watch,
    user_may_read_inbound_code,
)
from services.user_settings_service import get_or_create_user_settings

router = APIRouter(prefix="/amazon-accounts", tags=["amazon-accounts"])


def _to_response(row: AmazonAccount) -> AmazonAccountResponse:
    return AmazonAccountResponse(
        id=row.id,
        label=(row.label or "").strip() or None,
        amazon_email=row.amazon_email,
        has_password=bool(row.password_encrypted),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _owned(db: Session, user_id: int, account_id: int) -> AmazonAccount:
    row = (
        db.query(AmazonAccount)
        .filter(AmazonAccount.id == account_id, AmazonAccount.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte Amazon introuvable.")
    return row


@router.get("", response_model=AmazonAccountsOverview)
def list_amazon_accounts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountsOverview:
    settings = get_or_create_user_settings(db, user.id)
    rows = (
        db.query(AmazonAccount)
        .filter(AmazonAccount.user_id == user.id)
        .order_by(AmazonAccount.id.asc())
        .all()
    )
    active = settings.active_amazon_account_id
    if active is not None and not any(r.id == active for r in rows):
        active = None
    return AmazonAccountsOverview(
        accounts=[_to_response(r) for r in rows],
        active_account_id=active,
    )


@router.get("/active", response_model=AmazonAccountsOverview)
def active_amazon_account(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountsOverview:
    return list_amazon_accounts(db, user)


@router.post("/provision/inbound-watch")
def amazon_provision_inbound_watch(
    body: AmazonProvisionInboundWatchRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """En dev local, le webhook Resend écrit sur l’API prod — enregistre l’e-mail surveillé."""
    register_inbound_watch(user_id=user.id, email=str(body.email))
    return {"status": "ok"}


@router.get("/provision/inbound-code", response_model=AmazonProvisionInboundCodeResponse)
def amazon_provision_inbound_code(
    user: Annotated[User, Depends(get_current_user)],
    email: Annotated[str, Query(min_length=3, max_length=255)],
) -> AmazonProvisionInboundCodeResponse:
    normalized = email.strip().lower()
    if not user_may_read_inbound_code(user_id=user.id, email=normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune surveillance active pour cet e-mail.")
    code = latest_otp_for_recipient(normalized)
    return AmazonProvisionInboundCodeResponse(email=normalized, code=code)


@router.put("/active", response_model=AmazonAccountsOverview)
def set_active_amazon_account(
    body: AmazonActiveAccountUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountsOverview:
    settings = get_or_create_user_settings(db, user.id)
    if body.account_id is None:
        settings.active_amazon_account_id = None
    else:
        _owned(db, user.id, body.account_id)
        settings.active_amazon_account_id = body.account_id
    db.commit()
    return list_amazon_accounts(db, user)


@router.post("", response_model=AmazonAccountResponse, status_code=status.HTTP_201_CREATED)
def create_amazon_account(
    body: AmazonAccountCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountResponse:
    email = str(body.amazon_email).strip().lower()
    pwd = body.password.strip()
    if not pwd:
        raise HTTPException(status_code=400, detail="Mot de passe requis.")
    row = AmazonAccount(
        user_id=user.id,
        label=(body.label or "").strip() or None,
        amazon_email=email,
        password_encrypted=encrypt_vinted_credential(pwd),
    )
    db.add(row)
    db.flush()
    settings = get_or_create_user_settings(db, user.id)
    if settings.active_amazon_account_id is None:
        settings.active_amazon_account_id = row.id
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.put("/{account_id}", response_model=AmazonAccountResponse)
def update_amazon_account(
    account_id: int,
    body: AmazonAccountUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountResponse:
    row = _owned(db, user.id, account_id)
    if body.label is not None:
        row.label = body.label.strip() or None
    if body.amazon_email is not None:
        row.amazon_email = str(body.amazon_email).strip().lower()
    if body.clear_password:
        row.password_encrypted = ""
    elif body.password is not None:
        stripped = body.password.strip()
        if stripped:
            row.password_encrypted = encrypt_vinted_credential(stripped)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_amazon_account(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    row = _owned(db, user.id, account_id)
    settings = get_or_create_user_settings(db, user.id)
    if settings.active_amazon_account_id == account_id:
        settings.active_amazon_account_id = None
    db.delete(row)
    db.commit()


@router.get("/{account_id}/credentials", response_model=AmazonAccountCredentials)
def reveal_amazon_credentials(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AmazonAccountCredentials:
    row = _owned(db, user.id, account_id)
    plain = decrypt_vinted_credential(row.password_encrypted)
    if not plain:
        raise HTTPException(status_code=400, detail="Aucun mot de passe enregistré pour ce compte.")
    return AmazonAccountCredentials(amazon_email=row.amazon_email, password=plain)
