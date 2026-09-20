"""Parse public inbox pages from receive-sms.cc (HTML only, no official API)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ITEM_RE = re.compile(
    r'<div class="item">\s*'
    r'<div class="form">(.*?)</div>\s*'
    r'<span class="time">(.*?)</span>\s*'
    r'<div class="con">(.*?)</div>',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")

_AMAZON_OTP_RE = re.compile(
    r"(?:(\d{4,8})\s+est votre mot de passe\s*usage unique Amazon|"
    r"verification code is:?\s*(\d{4,8})|"
    r"Your verification code is\s*(\d{4,8}))",
    re.I,
)


@dataclass(frozen=True)
class ReceiveSmsMessage:
    sender: str
    time_label: str
    body: str
    is_amazon: bool


def _strip_tags(raw: str) -> str:
    return _TAG_RE.sub("", raw or "").replace("\n", " ").strip()


def parse_receive_sms_cc_html(html: str) -> list[ReceiveSmsMessage]:
    out: list[ReceiveSmsMessage] = []
    for sender_raw, time_raw, body_raw in _ITEM_RE.findall(html or ""):
        sender = _strip_tags(sender_raw)
        body = _strip_tags(body_raw)
        low = sender.lower()
        is_amazon = "amazon" in low and "aws" not in low
        out.append(
            ReceiveSmsMessage(
                sender=sender,
                time_label=_strip_tags(time_raw),
                body=body,
                is_amazon=is_amazon,
            )
        )
    return out


def amazon_history_on_inbox(messages: list[ReceiveSmsMessage]) -> bool:
    return any(m.is_amazon for m in messages)


def extract_amazon_otp_from_text(text: str) -> str | None:
    m = _AMAZON_OTP_RE.search(text or "")
    if not m:
        return None
    for g in m.groups():
        if g:
            return g.strip()
    return None


def latest_amazon_otp(messages: list[ReceiveSmsMessage]) -> str | None:
    for msg in messages:
        if not msg.is_amazon:
            continue
        code = extract_amazon_otp_from_text(msg.body)
        if code:
            return code
    return None
