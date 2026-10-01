"""
The e-mail the publisher receives for each message of the contact page (``/contact``).

Table-based HTML with inline styles, so Gmail, Outlook and Apple Mail render it alike: the GoupixDex cream, ink and
orange, with Fredoka titles in the mail clients that load web fonts.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from calendar import FRIDAY
from dataclasses import dataclass
from urllib.parse import quote

from app_types.contact import CONTACT_TOPIC_LABELS
from schemas.contact import ContactMessageCreate

_LOGO_URL = "https://goupixdex.dibodev.fr/apple-touch-icon.png"
_FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Fredoka:wght@600"
    "&family=Nunito+Sans:wght@400;600&family=JetBrains+Mono:wght@500&display=swap"
)
_DISPLAY_FONT = "'Fredoka', 'Trebuchet MS', Arial, sans-serif"
_BODY_FONT = "'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif"
_LABEL_FONT = "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"
_PAPER = "#f7f2ea"
_CARD = "#ffffff"
_INK = "#221a13"
_INK_SOFT = "#6f6355"
_LINE = "#e4dbcb"
_ACCENT = "#e86112"
_BUTTON_TEXT = "#fdfaf4"
_PREHEADER_LENGTH = 120
_REPLY_SUBJECT = "Votre message sur GoupixDex"
_WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


@dataclass(frozen=True)
class ContactEmailAction:
    """A button of the e-mail: what it says and what it opens."""

    label: str
    href: str
    is_primary: bool = False


@dataclass(frozen=True)
class ContactEmailDetailRow:
    """A line of the details table, linked when the value can be tapped (e-mail, phone)."""

    label: str
    value: str
    href: str | None = None


@dataclass(frozen=True)
class RenderedContactEmail:
    """A ready-to-send subject, HTML body and plain-text body."""

    subject: str
    html: str
    text: str


def render_contact_email(
    message: ContactMessageCreate,
    *,
    received_at: dt.datetime,
    account_label: str,
) -> RenderedContactEmail:
    """
    Render the e-mail of a contact-page message.

    Args:
        message: The visitor's message.
        received_at: When the message arrived, in Paris time.
        account_label: Whether the visitor already has a GoupixDex account (« Accès actif », « Aucun compte »…).

    Returns:
        The subject, the HTML body and its plain-text version; every visitor value is escaped in the HTML.
    """
    topic_label = CONTACT_TOPIC_LABELS[message.topic]
    subject = f"Nouveau message · {message.name} · {topic_label}"
    deadline = _long_date(_next_weekday(received_at))
    actions = _build_actions(message)
    rows = _build_detail_rows(message, topic_label, received_at, account_label)
    return RenderedContactEmail(
        subject=subject,
        html=_build_html(message, subject, topic_label, received_at, deadline, actions, rows),
        text=_build_text(message, topic_label, deadline, rows),
    )


def _next_weekday(moment: dt.datetime) -> dt.datetime:
    """The weekday after ``moment``: a message of Friday or of the weekend is due on Monday."""
    days_ahead = 7 - moment.weekday() if moment.weekday() >= FRIDAY else 1
    return moment + dt.timedelta(days=days_ahead)


def _long_date(moment: dt.datetime) -> str:
    """French long date, as « vendredi 2 octobre 2026 »."""
    return f"{_WEEKDAYS[moment.weekday()]} {moment.day} {_MONTHS[moment.month - 1]} {moment.year}"


def _short_date_time(moment: dt.datetime) -> str:
    """French short date and time, as « jeu. 01/10 à 09:42 »."""
    return f"{_WEEKDAYS[moment.weekday()][:3]}. {moment:%d/%m} à {moment:%H:%M}"


def _international_phone(phone: str) -> str | None:
    """
    The ``+…`` form of a phone number typed by the visitor.

    Args:
        phone: The number as typed (« 06 12 34 56 78 », « +33 (0)6 12… », « 0041 79… »).

    Returns:
        The international number, or None when it is neither a French number nor typed in international form.
    """
    compact = re.sub(r"[\s.()/-]", "", phone.replace("(0)", ""))
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+"):
        return compact if re.fullmatch(r"\+[1-9]\d{7,14}", compact) else None
    if re.fullmatch(r"0[1-9]\d{8}", compact):
        return "+33" + compact[1:]
    return None


def _is_mobile(international: str) -> bool:
    """A French number is a mobile when it starts with 06 or 07; a foreign one cannot be told, so it counts as one."""
    return not international.startswith("+33") or international[3] in "67"


def _build_tel_href(phone: str) -> str:
    """The ``tel:`` link of a phone number typed by the visitor, international when the number is recognized."""
    return f"tel:{_international_phone(phone) or re.sub(r'[^0-9+]', '', phone)}"


def _build_actions(message: ContactMessageCreate) -> list[ContactEmailAction]:
    """
    Build the buttons: reply first, then call, and WhatsApp for a mobile, when the visitor left a number.

    Args:
        message: The visitor's message.

    Returns:
        The buttons, the reply one highlighted.
    """
    reply_href = f"mailto:{message.email}?subject={quote(_REPLY_SUBJECT)}"
    actions = [ContactEmailAction(label="Répondre", href=reply_href, is_primary=True)]
    if message.phone:
        actions.append(ContactEmailAction(label="Appeler", href=_build_tel_href(message.phone)))
        international = _international_phone(message.phone)
        if international and _is_mobile(international):
            actions.append(ContactEmailAction(label="WhatsApp", href=f"https://wa.me/{international[1:]}"))
    return actions


def _build_detail_rows(
    message: ContactMessageCreate,
    topic_label: str,
    received_at: dt.datetime,
    account_label: str,
) -> list[ContactEmailDetailRow]:
    """
    Build the details table: how to reach the visitor, the topic, their account and the reception date.

    Args:
        message: The visitor's message.
        topic_label: The topic in French words.
        received_at: When the message arrived, in Paris time.
        account_label: Whether the visitor already has a GoupixDex account.

    Returns:
        The rows, without the phone when none was given.
    """
    rows = [ContactEmailDetailRow(label="E‑mail", value=str(message.email), href=f"mailto:{message.email}")]
    if message.phone:
        rows.append(ContactEmailDetailRow(label="Téléphone", value=message.phone, href=_build_tel_href(message.phone)))
    received = f"{_long_date(received_at)} à {received_at:%H:%M}"
    rows.append(ContactEmailDetailRow(label="Sujet", value=topic_label))
    rows.append(ContactEmailDetailRow(label="Compte", value=account_label))
    rows.append(ContactEmailDetailRow(label="Reçu le", value=received))
    return rows


def _build_html(
    message: ContactMessageCreate,
    subject: str,
    topic_label: str,
    received_at: dt.datetime,
    deadline: str,
    actions: list[ContactEmailAction],
    rows: list[ContactEmailDetailRow],
) -> str:
    """
    Build the HTML document: header, card and footer on the GoupixDex cream.

    Args:
        message: The visitor's message.
        subject: The e-mail subject, also the document title.
        topic_label: The topic in French words.
        received_at: When the message arrived, in Paris time.
        deadline: The day the visitor should get an answer, in French words.
        actions: The buttons of the card.
        rows: The details table of the card.

    Returns:
        The full HTML document.
    """
    preheader = " ".join(message.message.split())[:_PREHEADER_LENGTH]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{html.escape(subject)}</title>
<link href="{html.escape(_FONTS_URL)}" rel="stylesheet">
<style>
@media only screen and (max-width: 480px) {{
  .card-cell {{ padding: 28px 20px !important; }}
  .card {{ border-radius: 0 !important; border-left: 0 !important; border-right: 0 !important; }}
  .edge {{ padding-left: 20px !important; padding-right: 20px !important; }}
  .title {{ font-size: 26px !important; line-height: 32px !important; }}
  .action-button {{ padding-left: 16px !important; padding-right: 16px !important; }}
  .detail-label {{ width: 96px !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background-color:{_PAPER};">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{html.escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{_PAPER};">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
{_build_header(received_at)}
{_build_card(message, topic_label, deadline, actions, rows)}
<tr><td class="edge" style="padding:24px 0 40px;font-family:{_BODY_FONT};font-size:12px;line-height:18px;color:{_INK_SOFT};">
Envoyé par le formulaire de contact de goupixdex.dibodev.fr. Répondre à cet e‑mail écrit directement à {html.escape(message.name)}.
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _build_header(received_at: dt.datetime) -> str:
    """The header row: the GoupixDex mark, « Nouveau message » and the reception time."""
    return f"""<tr><td class="edge" style="padding:32px 0 20px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td style="font-size:0;line-height:0;"><img src="{_LOGO_URL}" width="30" height="30" alt="GoupixDex" style="display:inline-block;vertical-align:middle;width:30px;height:30px;border:0;border-radius:8px;"><span style="display:inline-block;vertical-align:middle;margin-left:10px;font-family:{_DISPLAY_FONT};font-size:20px;line-height:30px;font-weight:600;color:{_INK};">Nouveau message</span></td>
<td align="right" style="font-family:{_BODY_FONT};font-size:13px;line-height:30px;color:{_INK_SOFT};white-space:nowrap;">{_short_date_time(received_at)}</td>
</tr>
</table>
</td></tr>"""


def _build_card(
    message: ContactMessageCreate,
    topic_label: str,
    deadline: str,
    actions: list[ContactEmailAction],
    rows: list[ContactEmailDetailRow],
) -> str:
    """
    Build the card: reply deadline, visitor's name, buttons, message and details.

    Args:
        message: The visitor's message.
        topic_label: The topic in French words.
        deadline: The day the visitor should get an answer, in French words.
        actions: The buttons.
        rows: The details table.

    Returns:
        The card row of the layout table.
    """
    buttons = "".join(_build_button(action) for action in actions)
    message_html = "<br>".join(html.escape(line) for line in message.message.splitlines())
    detail_rows = "".join(_build_detail_row(row) for row in rows)
    return f"""<tr><td class="card" style="background-color:{_CARD};border:1px solid {_LINE};border-radius:16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td class="card-cell" style="padding:40px;font-family:{_BODY_FONT};">
<table role="presentation" cellpadding="0" cellspacing="0" border="0">
<tr><td style="padding:7px 14px;background-color:{_PAPER};border-radius:999px;font-size:13px;line-height:18px;color:{_INK};"><span style="display:inline-block;width:7px;height:7px;margin-right:8px;border-radius:4px;background-color:{_ACCENT};vertical-align:middle;"></span>À répondre au plus tard <strong style="font-weight:700;white-space:nowrap;">{deadline}</strong></td></tr>
</table>
<div class="title" style="padding-top:22px;font-family:{_DISPLAY_FONT};font-size:30px;line-height:36px;font-weight:600;color:{_INK};">{html.escape(message.name)}</div>
<div style="padding-top:6px;font-size:15px;line-height:22px;color:{_INK_SOFT};">{html.escape(topic_label)} · page contact de GoupixDex</div>
<div style="padding-top:24px;font-size:0;line-height:0;">{buttons}</div>
<div style="padding-top:20px;font-family:{_LABEL_FONT};font-size:11px;line-height:16px;letter-spacing:1.8px;text-transform:uppercase;color:{_INK_SOFT};"><span style="display:inline-block;width:18px;height:2px;margin-right:8px;background-color:{_ACCENT};vertical-align:middle;"></span>Message</div>
<div style="margin-top:10px;padding:18px 20px;background-color:{_PAPER};border-radius:12px;font-size:15px;line-height:24px;color:{_INK};word-break:break-word;">{message_html}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:28px;border-collapse:collapse;">
{detail_rows}
</table>
</td></tr>
</table>
</td></tr>"""


def _build_button(action: ContactEmailAction) -> str:
    """One pill button: orange for the main action, outlined for the others."""
    colors = (
        f"background-color:{_ACCENT};border:1px solid {_ACCENT};color:{_BUTTON_TEXT};font-weight:700;"
        if action.is_primary
        else f"background-color:{_CARD};border:1px solid {_LINE};color:{_INK};font-weight:600;"
    )
    return (
        f'<a class="action-button" href="{html.escape(action.href)}" style="display:inline-block;margin:0 8px 8px 0;'
        f"padding:12px 22px;{colors}border-radius:999px;font-family:{_BODY_FONT};font-size:15px;line-height:20px;"
        f'text-decoration:none;">{html.escape(action.label)}</a>'
    )


def _build_detail_row(row: ContactEmailDetailRow) -> str:
    """One line of the details table, the value linked when it can be tapped."""
    value = html.escape(row.value)
    if row.href:
        value = (
            f'<a href="{html.escape(row.href)}" style="color:{_INK};text-decoration:underline;'
            f'text-decoration-color:{_LINE};">{value}</a>'
        )
    return (
        f'<tr><td class="detail-label" width="120" valign="top" style="width:120px;padding:11px 12px 11px 0;'
        f'border-top:1px solid {_LINE};font-size:14px;line-height:20px;color:{_INK_SOFT};">'
        f"{html.escape(row.label)}</td>"
        f'<td valign="top" style="padding:11px 0;border-top:1px solid {_LINE};font-size:14px;line-height:20px;'
        f'font-weight:600;color:{_INK};word-break:break-word;">{value}</td></tr>'
    )


def _build_text(
    message: ContactMessageCreate,
    topic_label: str,
    deadline: str,
    rows: list[ContactEmailDetailRow],
) -> str:
    """
    Build the plain-text version, for the mail clients that do not show HTML.

    Args:
        message: The visitor's message.
        topic_label: The topic in French words.
        deadline: The day the visitor should get an answer, in French words.
        rows: The details table.

    Returns:
        The text body.
    """
    lines = [
        f"Nouveau message de {message.name}",
        f"{topic_label} · page contact de GoupixDex",
        f"À répondre au plus tard {deadline}",
        "",
        "Message :",
        message.message,
        "",
        *(f"{row.label} : {row.value}" for row in rows),
    ]
    return "\n".join(lines)
