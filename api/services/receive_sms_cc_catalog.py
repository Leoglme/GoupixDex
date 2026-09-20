"""Catalogue receive-sms.cc (Canada) — repérage de numéros sans historique Amazon visible."""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.receive_sms_cc_fetch import fetch_receive_sms_cc_html
from services.receive_sms_cc_parser import amazon_history_on_inbox, parse_receive_sms_cc_html

_LISTING_A_RE = re.compile(
    r'<a[^>]+href="(https://receive-sms\.cc/Canada-Phone-Number/\d+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_LISTING_TEXT_RE = re.compile(
    r"Canada Phone Number \+1\s*(\d{10})\s+(\d+)\s+",
    re.I,
)


@dataclass(frozen=True)
class ReceiveSmsCatalogEntry:
    inbox_url: str
    phone_e164: str
    message_count: int
    path_id: str


@dataclass(frozen=True)
class ReceiveSmsInboxAllocation:
    inbox_url: str
    phone_e164: str
    amazon_history_visible: bool
    message_count: int


def _listing_page_url(page: int) -> str:
    if page <= 1:
        return "https://receive-sms.cc/Canada-Phone-Number/"
    return f"https://receive-sms.cc/Canada-Phone-Number/Page/{page}"


def parse_canada_listing_html(html: str) -> list[ReceiveSmsCatalogEntry]:
    """Extrait les numéros du listing (href + compteur SMS affiché sur la carte)."""
    seen: set[str] = set()
    out: list[ReceiveSmsCatalogEntry] = []
    for inbox_url, inner in _LISTING_A_RE.findall(html or ""):
        path_id = inbox_url.rsplit("/", 1)[-1]
        if path_id in seen:
            continue
        seen.add(path_id)
        text = re.sub(r"<[^>]+>", "", inner).replace("\n", " ")
        tm = _LISTING_TEXT_RE.search(text)
        if not tm:
            continue
        national = tm.group(1)
        try:
            msg_count = int(tm.group(2))
        except ValueError:
            continue
        out.append(
            ReceiveSmsCatalogEntry(
                inbox_url=inbox_url,
                phone_e164=f"+1{national}",
                message_count=msg_count,
                path_id=path_id,
            )
        )
    return out


def collect_canada_listing_candidates(*, max_pages: int = 4) -> list[ReceiveSmsCatalogEntry]:
    merged: list[ReceiveSmsCatalogEntry] = []
    seen_url: set[str] = set()
    for page in range(1, max(1, max_pages) + 1):
        html = fetch_receive_sms_cc_html(_listing_page_url(page))
        for entry in parse_canada_listing_html(html):
            if entry.inbox_url in seen_url:
                continue
            seen_url.add(entry.inbox_url)
            merged.append(entry)
    merged.sort(key=lambda e: (e.message_count, e.path_id))
    return merged


def allocate_clean_canada_inboxes(
    count: int,
    *,
    max_pages: int = 5,
    max_probe: int = 60,
) -> list[ReceiveSmsInboxAllocation]:
    """
    Retourne ``count`` boîtes dont la page publique ne contient pas (encore) de SMS « From Amazon ».

    Amazon peut quand même refuser le numéro (liste interne VoIP) — best effort only.
    """
    need = max(1, min(10, int(count)))
    candidates = collect_canada_listing_candidates(max_pages=max_pages)
    allocated: list[ReceiveSmsInboxAllocation] = []
    probed = 0
    for entry in candidates:
        if len(allocated) >= need:
            break
        if probed >= max_probe:
            break
        probed += 1
        html = fetch_receive_sms_cc_html(entry.inbox_url)
        messages = parse_receive_sms_cc_html(html)
        has_amazon = amazon_history_on_inbox(messages)
        if has_amazon:
            continue
        allocated.append(
            ReceiveSmsInboxAllocation(
                inbox_url=entry.inbox_url,
                phone_e164=entry.phone_e164,
                amazon_history_visible=False,
                message_count=len(messages),
            )
        )
    if len(allocated) < need:
        raise RuntimeError(
            f"Seulement {len(allocated)} numéro(s) sans Amazon visible "
            f"(demandé {need}, {probed} testés). Réessayez ou réduisez le lot."
        )
    return allocated
