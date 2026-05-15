"""Generate an A4 PDF of Avery L7173 shipping labels (recipient and optional sender on separate stickers)."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from services.address_formatter_service import country_name, format_label_lines

logger = logging.getLogger(__name__)

PAGE_WIDTH_MM, PAGE_HEIGHT_MM = 210, 297

# Avery L7173 (99 × 57 mm), 8 per sheet.
LABEL_WIDTH_MM, LABEL_HEIGHT_MM = 99, 57
COLS, ROWS = 2, 4
HORIZONTAL_PITCH_MM = 100
VERTICAL_PITCH_MM = LABEL_HEIGHT_MM
TOP_MARGIN_MM = 21.5
LEFT_MARGIN_MM = 4.5
LABELS_PER_PAGE = COLS * ROWS

INNER_PADDING_MM = 5
LOGO_BOX_MM = 14
LOGO_TEXT_GAP_MM = 8
LINE_GAP_MM = 1.4

NAME_FONT_NAME = "Helvetica-Bold"
NAME_FONT_SIZE_PT = 13
ADDRESS_FONT_NAME = "Helvetica"
ADDRESS_FONT_SIZE_PT = 12

LABEL_BORDER_COLOR = HexColor("#9CA3AF")
LABEL_BORDER_WIDTH_PT = 0.4

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "goupixdex-logo.png"

# Recipient / sender pairs stack vertically (sender row = recipient row + 1, same column).
PAIRS_PER_PAGE = LABELS_PER_PAGE // 2

# Sender: hug border; single-line address; equal padding text ↔ crop rect on all four sides.
SENDER_PAD_MM = 2.8
SENDER_CROP_OUTER_TRIM_MM = 0.35
SENDER_NAME_PT_MAX = 11.0
SENDER_ADDR_PT_MAX = 10.5
SENDER_NAME_PT_MIN = 7.0
SENDER_ADDR_PT_MIN = 6.25
SENDER_LINE_GAP_MM = 0.85


@dataclass(frozen=True)
class LabelAddress:
    """Postal block for recipient or sender."""

    full_name: str
    line1: str
    line2: str | None
    postal_code: str
    city: str
    state: str | None
    country_code: str | None


def _cell_origin_mm(col: int, row: int) -> tuple[float, float]:
    x_mm = LEFT_MARGIN_MM + col * HORIZONTAL_PITCH_MM
    y_mm = PAGE_HEIGHT_MM - TOP_MARGIN_MM - (row + 1) * VERTICAL_PITCH_MM
    return x_mm, y_mm


def _position_to_col_row(position: int) -> tuple[int, int]:
    row = position // COLS
    col = position % COLS
    return col, row


def _recipient_sender_col_rows(pair_index_on_page: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Same column; sender directly below recipient on the physical sheet."""
    rec_col = pair_index_on_page % 2
    rec_row = (pair_index_on_page // 2) * 2
    return (rec_col, rec_row), (rec_col, rec_row + 1)


def _draw_label_border(c: canvas.Canvas, x_mm: float, y_mm: float) -> None:
    c.setStrokeColor(LABEL_BORDER_COLOR)
    c.setLineWidth(LABEL_BORDER_WIDTH_PT)
    c.rect(x_mm * mm, y_mm * mm, LABEL_WIDTH_MM * mm, LABEL_HEIGHT_MM * mm, stroke=1, fill=0)


def _draw_logo(c: canvas.Canvas, x_mm: float, y_mm: float) -> None:
    """Top-left logo (no GoupixDex text)."""
    if not LOGO_PATH.exists():
        logger.warning("shipping_label_service: logo missing at %s", LOGO_PATH)
        return
    logo_x_mm = x_mm + INNER_PADDING_MM
    logo_top_mm = y_mm + LABEL_HEIGHT_MM - INNER_PADDING_MM
    logo_y_mm = logo_top_mm - LOGO_BOX_MM
    c.drawImage(
        str(LOGO_PATH),
        logo_x_mm * mm,
        logo_y_mm * mm,
        width=LOGO_BOX_MM * mm,
        height=LOGO_BOX_MM * mm,
        mask="auto",
        preserveAspectRatio=True,
    )


def _compact_sender_one_line(addr: LabelAddress) -> str:
    """Single-line postal line (street, complement, CP city, country if abroad)."""
    parts: list[str] = []
    l1 = (addr.line1 or "").strip()
    l2 = (addr.line2 or "").strip() if addr.line2 else ""
    pc = (addr.postal_code or "").strip()
    city = (addr.city or "").strip().upper()
    st = (addr.state or "").strip() if addr.state else ""
    cc = (addr.country_code or "FR").strip().upper()
    if l1:
        parts.append(l1)
    if l2:
        parts.append(l2)
    if cc == "US":
        loc = city
        if st:
            loc = f"{city}, {st}".strip()
        if pc:
            loc = f"{loc} {pc}".strip()
        if loc:
            parts.append(loc)
    elif pc or city:
        parts.append(f"{pc} {city}".strip())
    if cc and cc != "FR":
        parts.append(country_name(cc))
    return ", ".join(p for p in parts if p)


def _truncate_to_width(c: canvas.Canvas, text: str, font: str, pt: float, max_width_pt: float) -> str:
    if not text:
        return ""
    if c.stringWidth(text, font, pt) <= max_width_pt:
        return text
    ell = "…"
    t = text
    while len(t) > 0:
        t = t[:-1].rstrip()
        if c.stringWidth((t + ell) if t else ell, font, pt) <= max_width_pt:
            return (t + ell) if t else ell
    return ell


def _draw_address_block(
    c: canvas.Canvas,
    x_mm: float,
    y_mm: float,
    lines: list[str],
    *,
    text_bottom_min_mm: float,
) -> None:
    """Recipient block: logo column reserved on the left; lines centred vertically."""
    if not lines:
        return

    name_line = lines[0]
    rest = lines[1:]

    name_height_mm = NAME_FONT_SIZE_PT / mm * 1.2
    rest_line_heights_mm = [
        ADDRESS_FONT_SIZE_PT / mm * 1.2 + LINE_GAP_MM for _ in rest
    ]
    block_height_mm = name_height_mm + sum(rest_line_heights_mm)

    text_region_top_mm = y_mm + LABEL_HEIGHT_MM - INNER_PADDING_MM
    text_region_bottom_mm = max(text_bottom_min_mm, y_mm + INNER_PADDING_MM)
    available_h_mm = text_region_top_mm - text_region_bottom_mm
    if available_h_mm <= 0:
        return
    centering_offset_mm = max(0.0, (available_h_mm - block_height_mm) / 2.0)
    text_top_mm = text_region_top_mm - centering_offset_mm

    text_left_mm = x_mm + INNER_PADDING_MM + LOGO_BOX_MM + LOGO_TEXT_GAP_MM
    inner_right_mm = x_mm + LABEL_WIDTH_MM - INNER_PADDING_MM
    max_w_pt = max((inner_right_mm - text_left_mm) * mm, 8.0)

    c.setFillColorRGB(0, 0, 0)
    c.setFont(NAME_FONT_NAME, NAME_FONT_SIZE_PT)
    name_draw = _truncate_to_width(c, name_line, NAME_FONT_NAME, NAME_FONT_SIZE_PT, max_w_pt)
    c.drawString(text_left_mm * mm, text_top_mm * mm, name_draw)

    cursor_mm = text_top_mm - name_height_mm
    c.setFont(ADDRESS_FONT_NAME, ADDRESS_FONT_SIZE_PT)
    for idx, line in enumerate(rest):
        if cursor_mm < text_region_bottom_mm:
            break
        line_draw = _truncate_to_width(c, line, ADDRESS_FONT_NAME, ADDRESS_FONT_SIZE_PT, max_w_pt)
        c.drawString(text_left_mm * mm, cursor_mm * mm, line_draw)
        cursor_mm -= rest_line_heights_mm[idx]


def _draw_sender_wrapped_with_hug_border(c: canvas.Canvas, x_mm: float, y_mm: float, sender: LabelAddress) -> None:
    """Sender: one address line under the name; crop rect; same inner padding top/right/bottom/left."""
    pad_mm = SENDER_PAD_MM
    gap_mm = SENDER_LINE_GAP_MM

    trim_mm = SENDER_CROP_OUTER_TRIM_MM
    bx_mm = x_mm + trim_mm
    bw_mm = LABEL_WIDTH_MM - 2 * trim_mm
    text_left_mm = bx_mm + pad_mm
    max_w_pt = max((bw_mm - 2 * pad_mm) * mm, 28.0)

    name_raw = (sender.full_name or "").strip()
    addr_raw = _compact_sender_one_line(sender)

    usable_height_mm = LABEL_HEIGHT_MM - INNER_PADDING_MM * 2
    name_pt = SENDER_NAME_PT_MAX
    addr_pt = SENDER_ADDR_PT_MAX

    for _ in range(52):
        name_step_mm = name_pt / mm * 1.18
        addr_step_mm = addr_pt / mm * 1.18
        box_h_mm = 2 * pad_mm + name_step_mm + gap_mm + addr_step_mm
        if box_h_mm > usable_height_mm + 0.25:
            addr_pt = max(SENDER_ADDR_PT_MIN, addr_pt - 0.2)
            name_pt = max(SENDER_NAME_PT_MIN, name_pt - 0.15)
            continue
        addr_w = c.stringWidth(addr_raw, ADDRESS_FONT_NAME, addr_pt)
        name_w = c.stringWidth(name_raw, NAME_FONT_NAME, name_pt)
        if addr_w <= max_w_pt and name_w <= max_w_pt:
            break
        addr_pt = max(SENDER_ADDR_PT_MIN, addr_pt - 0.18)
        name_pt = max(SENDER_NAME_PT_MIN, name_pt - 0.15)

    name_draw = (
        name_raw
        if c.stringWidth(name_raw, NAME_FONT_NAME, name_pt) <= max_w_pt
        else _truncate_to_width(c, name_raw, NAME_FONT_NAME, name_pt, max_w_pt)
    )
    addr_draw = (
        addr_raw
        if c.stringWidth(addr_raw, ADDRESS_FONT_NAME, addr_pt) <= max_w_pt
        else _truncate_to_width(c, addr_raw, ADDRESS_FONT_NAME, addr_pt, max_w_pt)
    )

    name_step_mm = name_pt / mm * 1.18
    addr_step_mm = addr_pt / mm * 1.18

    box_top_mm = y_mm + LABEL_HEIGHT_MM - INNER_PADDING_MM
    name_baseline_mm = box_top_mm - pad_mm - name_pt / mm * 0.75
    addr_baseline_mm = name_baseline_mm - name_step_mm - gap_mm
    box_bottom_mm = addr_baseline_mm - addr_pt / mm * 0.32 - pad_mm

    bh_mm = box_top_mm - box_bottom_mm

    c.setStrokeColor(LABEL_BORDER_COLOR)
    c.setLineWidth(LABEL_BORDER_WIDTH_PT)
    c.rect(bx_mm * mm, box_bottom_mm * mm, bw_mm * mm, bh_mm * mm, stroke=1, fill=0)

    c.setFillColorRGB(0, 0, 0)
    c.setFont(NAME_FONT_NAME, name_pt)
    c.drawString(text_left_mm * mm, name_baseline_mm * mm, name_draw)
    c.setFont(ADDRESS_FONT_NAME, addr_pt)
    c.drawString(text_left_mm * mm, addr_baseline_mm * mm, addr_draw)


def _draw_recipient_label(c: canvas.Canvas, col: int, row: int, address: LabelAddress) -> None:
    x_mm, y_mm = _cell_origin_mm(col, row)
    _draw_label_border(c, x_mm, y_mm)
    _draw_logo(c, x_mm, y_mm)
    lines = format_label_lines(
        full_name=address.full_name,
        line1=address.line1,
        line2=address.line2,
        postal_code=address.postal_code,
        city=address.city,
        state=address.state,
        country_code=address.country_code,
    )
    floor_mm = y_mm + INNER_PADDING_MM
    _draw_address_block(c, x_mm, y_mm, lines, text_bottom_min_mm=floor_mm)


def _draw_sender_label(c: canvas.Canvas, col: int, row: int, sender: LabelAddress) -> None:
    x_mm, y_mm = _cell_origin_mm(col, row)
    _draw_sender_wrapped_with_hug_border(c, x_mm, y_mm, sender)


def render_labels_pdf(
    recipients: list[LabelAddress],
    *,
    sender: LabelAddress | None = None,
) -> bytes:
    """
    Render Avery L7173 sheets (8 labels per page).

    Each recipient uses one full L7173 vignette (logo + address). When ``sender`` is set, the same sender is printed on
    the vignette **directly below** on the sheet (same column): crop rect nearly full width; name + **one-line** address;
    equal padding inside the crop marks on **all four sides** (font scales down before ellipsis).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("GoupixDex — Shipping labels")
    c.setAuthor("GoupixDex")

    if not recipients:
        for r in range(ROWS):
            for col in range(COLS):
                x_mm, y_mm = _cell_origin_mm(col, r)
                _draw_label_border(c, x_mm, y_mm)
        c.save()
        return buf.getvalue()

    if sender is None:
        for i, addr in enumerate(recipients):
            if i > 0 and i % LABELS_PER_PAGE == 0:
                c.showPage()
            col, row = _position_to_col_row(i % LABELS_PER_PAGE)
            _draw_recipient_label(c, col, row, addr)
        c.save()
        return buf.getvalue()

    for i, addr in enumerate(recipients):
        if i > 0 and i % PAIRS_PER_PAGE == 0:
            c.showPage()
        pair_slot = i % PAIRS_PER_PAGE
        (rcol, rrow), (scol, srow) = _recipient_sender_col_rows(pair_slot)
        _draw_recipient_label(c, rcol, rrow, addr)
        _draw_sender_label(c, scol, srow, sender)

    c.save()
    return buf.getvalue()
