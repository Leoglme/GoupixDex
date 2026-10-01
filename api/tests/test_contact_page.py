"""Page contact : le message part vers la boîte de l'éditeur, la réponse va au visiteur, les robots sont filtrés."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from config import AppSettings
from models.base import Base
from models.user import User
from routes import contact_route
from schemas.contact import ContactMessageCreate
from services import contact_message_service
from services.contact_email import render_contact_email

_THURSDAY_MORNING = dt.datetime(2026, 10, 1, 9, 42)


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire avec toutes les tables."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def forget_recent_messages() -> Iterator[None]:
    """Chaque test part sans message compté dans la limite horaire."""
    contact_message_service._recent_messages.clear()
    yield
    contact_message_service._recent_messages.clear()


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Les e-mails confiés à Resend, avec une clé d'API configurée."""
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(
        contact_message_service, "get_settings", lambda: AppSettings(_env_file=None, resend_api_key="re_test")
    )
    monkeypatch.setattr(contact_message_service, "_send_with_resend", lambda api_key, params: sent.append(params))
    return sent


def _message(**overrides: Any) -> ContactMessageCreate:
    """Un message de visiteur sur l'accès à GoupixDex, avec les champs que le test veut changer."""
    fields: dict[str, Any] = {
        "topic": "access",
        "name": "Camille Martin",
        "email": "camille@exemple.fr",
        "message": "Bonjour, je vends mes cartes sur Vinted, est-ce que GoupixDex peut m'aider ?",
    }
    fields.update(overrides)
    return ContactMessageCreate(**fields)


def _render(**overrides: Any) -> Any:
    """Le mail rendu pour un message reçu un jeudi matin, d'un visiteur sans compte."""
    return render_contact_email(_message(**overrides), received_at=_THURSDAY_MORNING, account_label="Aucun compte")


def _visitor_request(address: str = "203.0.113.9") -> Request:
    """La requête HTTP d'un visiteur."""
    return Request({"type": "http", "headers": [], "client": (address, 443)})


def test_the_message_reaches_the_inbox_and_a_reply_answers_the_visitor(
    db: Session, sent_emails: list[dict[str, Any]]
) -> None:
    asyncio.run(contact_message_service.send_contact_message(db, _message()))

    [email] = sent_emails
    assert email["to"] == ["contact@dibodev.fr"]
    assert email["from"] == "GoupixDex <contact@mail.goupixdex.dibodev.fr>"
    assert email["reply_to"] == "camille@exemple.fr"
    assert email["subject"] == "Nouveau message · Camille Martin · Accès à GoupixDex"
    assert "est-ce que GoupixDex peut m'aider" in email["text"]


def test_the_email_says_whether_the_visitor_already_has_an_account(
    db: Session, sent_emails: list[dict[str, Any]]
) -> None:
    db.add(User(email="camille@exemple.fr", status="pending"))
    db.commit()

    asyncio.run(contact_message_service.send_contact_message(db, _message(email="Camille@Exemple.fr")))

    assert "Compte : Demande d'accès en attente" in sent_emails[0]["text"]


def test_a_visitor_without_account_is_told_so() -> None:
    assert "Compte : Aucun compte" in _render().text


def test_a_message_that_resend_refuses_fails(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(api_key: str, params: dict[str, Any]) -> None:
        raise RuntimeError("Resend API error 500")

    monkeypatch.setattr(
        contact_message_service, "get_settings", lambda: AppSettings(_env_file=None, resend_api_key="re_test")
    )
    monkeypatch.setattr(contact_message_service, "_send_with_resend", refuse)

    with pytest.raises(contact_message_service.ContactDeliveryError):
        asyncio.run(contact_message_service.send_contact_message(db, _message()))


def test_a_server_without_resend_key_does_not_pretend_the_message_left(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_message_service, "get_settings", lambda: AppSettings(_env_file=None))

    with pytest.raises(contact_message_service.ContactDeliveryError):
        asyncio.run(contact_message_service.send_contact_message(db, _message()))


def test_the_visitor_text_is_escaped_in_the_html_email() -> None:
    email = _render(name="<b>Camille</b>", message="<script>alert(1)</script>")

    assert "<script>" not in email.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in email.html
    assert "&lt;b&gt;Camille&lt;/b&gt;" in email.html


def test_a_mobile_can_be_called_or_texted_on_whatsapp() -> None:
    email = _render(phone="06 12 34 56 78")

    assert 'href="tel:+33612345678"' in email.html
    assert 'href="https://wa.me/33612345678"' in email.html


def test_a_landline_can_be_called_but_not_texted() -> None:
    email = _render(phone="01 23 45 67 89")

    assert 'href="tel:+33123456789"' in email.html
    assert "wa.me" not in email.html


def test_a_foreign_number_typed_in_international_form_can_be_texted() -> None:
    assert 'href="https://wa.me/41791234567"' in _render(phone="+41 79 123 45 67").html


def test_without_a_phone_the_email_only_offers_to_reply() -> None:
    email = _render()

    assert "tel:" not in email.html
    assert "Téléphone" not in email.text
    assert 'href="mailto:camille@exemple.fr?subject=Votre%20message%20sur%20GoupixDex"' in email.html


@pytest.mark.parametrize(
    ("received_at", "deadline"),
    [
        (dt.datetime(2026, 10, 1, 9, 42), "vendredi 2 octobre 2026"),
        (dt.datetime(2026, 10, 2, 18, 0), "lundi 5 octobre 2026"),
        (dt.datetime(2026, 10, 3, 11, 0), "lundi 5 octobre 2026"),
        (dt.datetime(2026, 10, 4, 22, 30), "lundi 5 octobre 2026"),
    ],
)
def test_the_answer_is_due_the_next_weekday(received_at: dt.datetime, deadline: str) -> None:
    email = render_contact_email(_message(), received_at=received_at, account_label="Aucun compte")

    assert f"À répondre au plus tard {deadline}" in email.text


def test_the_message_keeps_its_line_breaks_in_the_email() -> None:
    assert "Bonjour,<br>À bientôt" in _render(message="Bonjour,\r\nÀ bientôt").html


def test_a_name_written_on_several_lines_becomes_one_line() -> None:
    assert _message(name="Camille\n  Martin").name == "Camille Martin"


def test_an_empty_phone_is_dropped() -> None:
    assert _message(phone="   ").phone is None


@pytest.mark.parametrize(
    "overrides",
    [{"name": "   "}, {"message": ""}, {"email": "camille"}, {"message": "x" * 5001}, {"topic": "partenariat"}],
)
def test_an_incomplete_message_is_refused(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _message(**overrides)


def test_a_filled_honeypot_is_answered_without_sending(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_if_sent(session: Session, message: ContactMessageCreate) -> None:
        raise AssertionError("un robot ne doit déclencher aucun e-mail")

    monkeypatch.setattr(contact_message_service, "send_contact_message", fail_if_sent)

    response = asyncio.run(
        contact_route.send_contact_message(_message(website="https://spam.example"), _visitor_request(), db)
    )

    assert response.ok is True


def test_a_visitor_is_stopped_after_five_messages_in_an_hour(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    async def send(session: Session, message: ContactMessageCreate) -> None:
        return None

    monkeypatch.setattr(contact_message_service, "send_contact_message", send)
    for _ in range(contact_message_service.MAX_MESSAGES_PER_HOUR):
        asyncio.run(contact_route.send_contact_message(_message(), _visitor_request(), db))

    with pytest.raises(HTTPException) as refusal:
        asyncio.run(contact_route.send_contact_message(_message(), _visitor_request(), db))

    assert refusal.value.status_code == 429
    asyncio.run(contact_route.send_contact_message(_message(), _visitor_request("198.51.100.4"), db))


def test_a_message_that_did_not_leave_answers_503(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    async def send(session: Session, message: ContactMessageCreate) -> None:
        raise contact_message_service.ContactDeliveryError("Resend API error 500")

    monkeypatch.setattr(contact_message_service, "send_contact_message", send)

    with pytest.raises(HTTPException) as refusal:
        asyncio.run(contact_route.send_contact_message(_message(), _visitor_request(), db))

    assert refusal.value.status_code == 503
