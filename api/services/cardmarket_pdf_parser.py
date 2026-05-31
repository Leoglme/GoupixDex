"""Parse Cardmarket FR purchase PDFs (text layer)."""

from __future__ import annotations

import datetime as dt
import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedCardLine:
    """One Pokémon card row from the PDF."""

    quantity: int
    pokemon_name_raw: str
    card_number: str
    language_code: str
    condition_label: str
    set_code: str
    variant_token: str
    unit_price_eur: Decimal
    invoice_line_text: str


@dataclass(frozen=True)
class ParsedCardmarketPdf:
    """Structured data extracted from a Cardmarket purchase PDF."""

    external_order_id: str
    seller_username: str | None
    seller_display_name: str | None
    seller_country_code: str | None
    paid_at: dt.datetime | None
    shipped_at: dt.datetime | None
    delivered_at: dt.datetime | None
    items_subtotal: Decimal
    shipping_fee: Decimal
    order_total: Decimal
    lines: list[ParsedCardLine]


_COUNTRY_FR_TO_ISO: dict[str, str] = {
    "france": "FR",
    "italie": "IT",
    "allemagne": "DE",
    "espagne": "ES",
    "royaume-uni": "GB",
    "belgique": "BE",
    "belgium": "BE",
    "pays-bas": "NL",
    "luxembourg": "LU",
    "autriche": "AT",
    "suisse": "CH",
    "portugal": "PT",
    "pologne": "PL",
    "republique tcheque": "CZ",
    "hongrie": "HU",
    "suede": "SE",
    "norvege": "NO",
    "danemark": "DK",
    "finlande": "FI",
    "grece": "GR",
    "irlande": "IE",
    "canada": "CA",
    "etats-unis": "US",
    "usa": "US",
    "japon": "JP",
}


def extract_pdf_text(data: bytes) -> str:
    """
    Extract plain text from a PDF byte payload.

    @param data - Raw PDF bytes.
    @returns Concatenated page text.
    """
    reader = PdfReader(io.BytesIO(data))
    chunks: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            chunks.append(t)
    return "\n".join(chunks)


def _normalize_ascii_lower(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return folded.lower().strip()


def normalize_pokemon_key(name: str | None) -> str:
    """
    Normalize a Pokémon name for stable matching (accent-fold, lower, collapse spaces).

    @param name - Raw display name.
    @returns Normalized key string.
    """
    if not name:
        return ""
    return " ".join(_normalize_ascii_lower(name).split())


def normalize_card_number_token(raw: str | None) -> str:
    """
    Normalize card number for equality checks (first segment before slash).

    @param raw - OCR or user input like ``185`` or ``185/193``.
    @returns Canonical segment used for matching.
    """
    if not raw:
        return ""
    s = raw.strip()
    if "/" in s:
        return s.split("/", maxsplit=1)[0].strip()
    return s


_RE_ORDER_ID = re.compile(r"Achat\s*#\s*(\d+)", re.IGNORECASE)
_RE_MONEY_EUR = re.compile(r"([\d,]+)\s*EUR", re.IGNORECASE)
# Unit price at end of a card line (supports ``4,00`` and ``4.00``).
_RE_LINE_UNIT_EUR = re.compile(r"([\d]+(?:[.,]\d{1,2})?)\s*EUR\s*$", re.IGNORECASE)
_RE_DATETIME_TOKEN = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?")

# Cardmarket invoice columns after quantity:
# name… | card # | LANG | condition | set | variant | [optional seller note…] | price
_KNOWN_CM_LANG_CODES: frozenset[str] = frozenset(
    {
        "JP",
        "EN",
        "DE",
        "FR",
        "IT",
        "ES",
        "PT",
        "NL",
        "KO",
        "ZH",
        "CS",
        "PL",
        "RU",
        "TH",
        "VI",
        "ID",
        "TW",
        "HK",
        "UK",
        "US",
        "CA",
        "AU",
        "MX",
        "BR",
        "NO",
        "SE",
        "DK",
        "FI",
        "GR",
        "CZ",
        "HU",
        "RO",
        "BG",
        "HR",
        "SI",
        "SK",
        "LT",
        "LV",
        "EE",
        "IE",
        "PH",
        "MY",
        "SG",
        "NZ",
        "ZA",
        "AE",
        "SA",
        "IL",
        "UA",
        "BY",
        "MD",
        "MT",
        "CY",
        "LU",
        "IS",
        "LI",
        "CH",
        "BE",
        "AT",
        "MC",
        "AD",
        "SM",
        "VA",
    }
)

_KNOWN_CM_CONDITIONS: frozenset[str] = frozenset(
    {
        "M",
        "NM",
        "EX",
        "GD",
        "LP",
        "PL",
        "PO",
        "MP",
        "HP",
        "DMG",
        "PR",
    }
)

_KNOWN_CM_VARIANTS: frozenset[str] = frozenset(
    {
        "ART",
        "UR",
        "CHR",
        "HIR",
        "AR",
        "SIR",
        "FA",
        "RH",
        "V",
        "VMAX",
        "VSTAR",
        "EX",
        "GX",
        "LV",
        "LVX",
        "PROMO",
        "HOLO",
        "REV",
    }
)


def _looks_like_card_number_token(tok: str) -> bool:
    """
    Heuristic: Cardmarket card index token before the language column.

    @param tok - Single whitespace-split token from the invoice line.
    @returns True when plausible as card number / collector number segment.
    """
    if not tok or len(tok) > 24:
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9\-/\.]*$", tok))


def _is_uppercase_lang_token(tok: str) -> bool:
    """Cardmarket language column is always an uppercase two-letter code."""
    return len(tok) == 2 and tok.isupper() and tok in _KNOWN_CM_LANG_CODES


def _looks_like_set_code(tok: str) -> bool:
    """Set/expansion code (``sv9a``, ``m2a``, ``s8b``, ``m1L``…)."""
    if not tok or len(tok) > 16:
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9\-/\.]*$", tok))


def _looks_like_variant_token(tok: str) -> bool:
    """Card type / rarity column (``ART``, ``UR``, ``CHR``…)."""
    if not tok or len(tok) > 12:
        return False
    upper = tok.upper()
    if upper in _KNOWN_CM_VARIANTS:
        return True
    return bool(re.match(r"^[A-Z0-9]{2,8}$", upper))


def _find_fixed_column_block_idx(rest: list[str]) -> int | None:
    """
    Locate the card-number index of the fixed Cardmarket column block.

    Columns: card # | LANG | condition | set | variant
    When several candidates match, keep the last one (closest to the seller note).
    """
    last_match: int | None = None
    for i in range(2, len(rest) - 4):
        if not _looks_like_card_number_token(rest[i]):
            continue
        if not _is_uppercase_lang_token(rest[i + 1]):
            continue
        if rest[i + 2].upper() not in _KNOWN_CM_CONDITIONS:
            continue
        if not _looks_like_set_code(rest[i + 3]):
            continue
        if not _looks_like_variant_token(rest[i + 4]):
            continue
        last_match = i
    return last_match


def _parse_invoice_rest_tokens(
    rest: list[str],
    qty: int,
    unit_price: Decimal,
    invoice_line_text: str,
) -> ParsedCardLine:
    """
    Parse tokens between quantity and ``… EUR`` using Cardmarket fixed columns.

    @param rest - Tokens including leading quantity.
    @param qty - Parsed quantity (must match rest[0]).
    @param unit_price - Parsed unit price.
    @param invoice_line_text - Original PDF line for storage.
    @returns Parsed line.
    @raises ValueError - When the fixed column block cannot be located.
    """
    if len(rest) < 7:
        raise ValueError(f"Could not parse Cardmarket line (too few tokens): {invoice_line_text!r}")

    block_idx = _find_fixed_column_block_idx(rest)
    if block_idx is None:
        raise ValueError(f"Could not parse Cardmarket line (fixed columns not found): {invoice_line_text!r}")

    name_tokens = rest[1:block_idx]
    if not name_tokens:
        raise ValueError(f"Could not parse Cardmarket line (empty card name): {invoice_line_text!r}")

    pokemon_raw = " ".join(name_tokens)
    card_no = rest[block_idx]
    lang = rest[block_idx + 1]
    condition_label = rest[block_idx + 2]
    set_code = rest[block_idx + 3]
    variant_base = rest[block_idx + 4]
    seller_note_tokens = rest[block_idx + 5 :]
    variant_token = variant_base if not seller_note_tokens else f"{variant_base} {' '.join(seller_note_tokens)}"

    return ParsedCardLine(
        quantity=qty,
        pokemon_name_raw=pokemon_raw,
        card_number=card_no,
        language_code=lang.upper(),
        condition_label=condition_label,
        set_code=set_code,
        variant_token=variant_token,
        unit_price_eur=unit_price,
        invoice_line_text=invoice_line_text,
    )


def _parse_decimal_eu(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ".").strip())


def _parse_dt_from_match(m: re.Match[str]) -> dt.datetime:
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = m.group(4), m.group(5)
    if hh is not None and mm is not None:
        return dt.datetime(y, mo, d, int(hh), int(mm), tzinfo=dt.UTC)
    return dt.datetime(y, mo, d, 0, 0, tzinfo=dt.UTC)


def _extract_money_after_label(text: str, label: str) -> Decimal | None:
    idx = text.lower().find(label.lower())
    if idx < 0:
        return None
    window = text[idx : idx + 80]
    m = _RE_MONEY_EUR.search(window)
    if not m:
        return None
    return _parse_decimal_eu(m.group(1))


def _extract_order_dates(long_line: str) -> tuple[dt.datetime | None, dt.datetime | None, dt.datetime | None]:
    matches = list(_RE_DATETIME_TOKEN.finditer(long_line))
    if len(matches) >= 4:
        return (
            _parse_dt_from_match(matches[1]),
            _parse_dt_from_match(matches[2]),
            _parse_dt_from_match(matches[3]),
        )
    if len(matches) == 3:
        return (
            _parse_dt_from_match(matches[0]),
            _parse_dt_from_match(matches[1]),
            _parse_dt_from_match(matches[2]),
        )
    if len(matches) == 2:
        return _parse_dt_from_match(matches[0]), _parse_dt_from_match(matches[1]), None
    if len(matches) == 1:
        return _parse_dt_from_match(matches[0]), None, None
    return None, None, None


def _parse_seller_block_and_country(text: str) -> tuple[str | None, str | None, str | None]:
    lower = text.lower()
    buyer_idx = lower.find("acheteur")
    block_end = buyer_idx if buyer_idx >= 0 else len(text)
    block = text[:block_end]
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    seller_username: str | None = None
    seller_display: str | None = None
    country_code: str | None = None
    for i, ln in enumerate(lines):
        if ln.lower().startswith("vendeur"):
            rest = re.sub(r"^vendeur\s*-\s*", "", ln, flags=re.IGNORECASE).strip()
            if rest:
                seller_username = rest
            if i + 1 < len(lines) and not lines[i + 1].lower().startswith("via"):
                seller_display = lines[i + 1]
            break
    tail_lines = lines[-4:] if len(lines) >= 4 else lines
    for ln in reversed(tail_lines):
        if ln.lower().startswith("acheteur"):
            continue
        key = _normalize_ascii_lower(ln)
        if key in _COUNTRY_FR_TO_ISO:
            country_code = _COUNTRY_FR_TO_ISO[key]
            break
        for fr_name, iso in _COUNTRY_FR_TO_ISO.items():
            if key == fr_name or key.endswith(" " + fr_name):
                country_code = iso
                break
        if country_code:
            break
    return seller_username, seller_display, country_code


def _parse_lines_section(body: str) -> list[ParsedCardLine]:
    """Locate the ``… Cartes:`` block (encoding varies in extracted PDF text)."""
    start = -1
    m_hdr = re.search(r"(?i)Pok\w*\s*Cartes\s*:", body)
    if m_hdr:
        start = m_hdr.end()
    if start < 0:
        lower = body.lower()
        for mk in ("pokémon cartes:", "pokemon cartes:", "cartes:"):
            idx = lower.find(mk)
            if idx >= 0:
                start = idx + len(mk)
                break
    if start < 0:
        return []
    section = body[start:]
    out: list[ParsedCardLine] = []
    for raw_ln in section.splitlines():
        ln = raw_ln.strip()
        if not ln:
            continue
        if ln.startswith("--"):
            break
        parts = ln.split()
        if len(parts) < 7:
            continue
        m_price = _RE_LINE_UNIT_EUR.search(ln)
        if not m_price:
            continue
        unit_price = _parse_decimal_eu(m_price.group(1))
        rest = ln[: m_price.start()].strip().split()
        if len(rest) < 7:
            continue
        qty_s = rest[0]
        if not qty_s.isdigit():
            continue
        qty = int(qty_s)
        out.append(_parse_invoice_rest_tokens(rest, qty, unit_price, ln))
    return out


def parse_cardmarket_order_pdf(text: str) -> ParsedCardmarketPdf:
    """
    Parse Cardmarket FR invoice text into structured fields.

    @param text - Full PDF text (French labels).
    @returns Parsed payload ready for persistence.
    @raises ValueError - When the document is not recognized as a Cardmarket purchase PDF.
    """
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    m_id = _RE_ORDER_ID.search(norm)
    if not m_id:
        raise ValueError("Cardmarket order id not found (expected 'Achat #…').")
    external_order_id = m_id.group(1)
    seller_username, seller_display_name, seller_country = _parse_seller_block_and_country(norm)

    items_subtotal = _extract_money_after_label(norm, "valeur de l'article") or Decimal("0")
    shipping_fee = _extract_money_after_label(norm, "frais de port") or Decimal("0")
    order_total = _extract_money_after_label(norm, "total") or (items_subtotal + shipping_fee)

    paid_at: dt.datetime | None = None
    shipped_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    for ln in norm.splitlines():
        ln_low = ln.lower()
        if "payer" in ln_low and re.search(r"\d{2}\.\d{2}\.\d{4}", ln):
            paid_at, shipped_at, delivered_at = _extract_order_dates(ln)
            break

    lines = _parse_lines_section(norm)
    if not lines:
        raise ValueError("No Pokemon card lines found in PDF (expected lines after the Cartes section).")

    return ParsedCardmarketPdf(
        external_order_id=external_order_id,
        seller_username=seller_username,
        seller_display_name=seller_display_name,
        seller_country_code=seller_country,
        paid_at=paid_at,
        shipped_at=shipped_at,
        delivered_at=delivered_at,
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
        order_total=order_total,
        lines=lines,
    )


def parse_cardmarket_pdf_bytes(data: bytes) -> ParsedCardmarketPdf:
    """
    Extract text from PDF bytes and parse Cardmarket fields.

    @param data - Raw PDF.
    @returns Parsed payload.
    """
    txt = extract_pdf_text(data)
    if not txt.strip():
        raise ValueError("Could not extract text from PDF (empty or image-only).")
    return parse_cardmarket_order_pdf(txt)
