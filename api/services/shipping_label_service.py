"""Generate an A4 sheet of shipping labels (Avery L7173 — 99×57 mm, 8 per page)."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from services.address_formatter_service import format_label_lines

logger = logging.getLogger(__name__)

# Avery L7173 layout (DL envelope-friendly half label, 99 × 57 mm).
# A4 = 210 × 297 mm. Two columns × four rows = 8 labels per sheet.
# Side margins ~5.5 mm, top/bottom ~21.5 mm, vertical/horizontal gutters 0 mm.
PAGE_WIDTH_MM, PAGE_HEIGHT_MM = 210, 297
LABEL_WIDTH_MM, LABEL_HEIGHT_MM = 99, 57
COLS, ROWS = 2, 4
HORIZONTAL_PITCH_MM = 100  # 1 mm gutter between columns (Avery L7173 spec)
VERTICAL_PITCH_MM = LABEL_HEIGHT_MM
TOP_MARGIN_MM = 21.5
LEFT_MARGIN_MM = 4.5
LABELS_PER_PAGE = COLS * ROWS

INNER_PADDING_MM = 5
LOGO_BOX_MM = 14  # max box for the logo in the top-left corner
LOGO_TEXT_GAP_MM = 8  # horizontal breathing room between the logo and the recipient block on its right
LINE_GAP_MM = 1.4  # extra gap between text lines (on top of leading)

NAME_FONT_NAME = "Helvetica-Bold"
NAME_FONT_SIZE_PT = 13
ADDRESS_FONT_NAME = "Helvetica"
ADDRESS_FONT_SIZE_PT = 12

BORDER_COLOR = HexColor("#9CA3AF")  # tailwind gray-400 — fine cut guide
BORDER_WIDTH_PT = 0.4

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "goupixdex-logo.png"


@dataclass(frozen=True)
class LabelAddress:
    """Single recipient block printed on one Avery L7173 cell."""

    full_name: str
    line1: str
    line2: str | None
    postal_code: str
    city: str
    state: str | None
    country_code: str | None


def _draw_label_border(c: canvas.Canvas, x_mm: float, y_mm: float) -> None:
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(BORDER_WIDTH_PT)
    c.rect(x_mm * mm, y_mm * mm, LABEL_WIDTH_MM * mm, LABEL_HEIGHT_MM * mm, stroke=1, fill=0)


def _draw_logo(c: canvas.Canvas, x_mm: float, y_mm: float) -> None:
    """Top-left logo (no GoupixDex text, per spec)."""
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


def _draw_address_block(c: canvas.Canvas, x_mm: float, y_mm: float, lines: list[str]) -> None:
    """Recipient block in the lower-right area of the label, large enough to be machine-readable."""
    if not lines:
        return

    name_line = lines[0]
    rest = lines[1:]

    name_height_mm = NAME_FONT_SIZE_PT / mm * 1.2  # converts pt → mm and adds 20% leading
    rest_line_heights_mm = [
        ADDRESS_FONT_SIZE_PT / mm * 1.2 + LINE_GAP_MM for _ in rest
    ]
    block_height_mm = name_height_mm + sum(rest_line_heights_mm)

    # Recipient block sits in the strip on the right of the logo so nothing is printed underneath
    # it; vertical centering uses the full inner height of the cell.
    text_region_top_mm = y_mm + LABEL_HEIGHT_MM - INNER_PADDING_MM
    text_region_bottom_mm = y_mm + INNER_PADDING_MM
    available_h_mm = text_region_top_mm - text_region_bottom_mm
    centering_offset_mm = max(0.0, (available_h_mm - block_height_mm) / 2.0)
    text_top_mm = text_region_top_mm - centering_offset_mm

    text_left_mm = x_mm + INNER_PADDING_MM + LOGO_BOX_MM + LOGO_TEXT_GAP_MM

    c.setFillColorRGB(0, 0, 0)
    c.setFont(NAME_FONT_NAME, NAME_FONT_SIZE_PT)
    c.drawString(text_left_mm * mm, text_top_mm * mm, name_line)

    cursor_mm = text_top_mm - name_height_mm
    c.setFont(ADDRESS_FONT_NAME, ADDRESS_FONT_SIZE_PT)
    for idx, line in enumerate(rest):
        c.drawString(text_left_mm * mm, cursor_mm * mm, line)
        cursor_mm -= rest_line_heights_mm[idx]


def _draw_label(c: canvas.Canvas, col: int, row: int, address: LabelAddress) -> None:
    x_mm = LEFT_MARGIN_MM + col * HORIZONTAL_PITCH_MM
    # ReportLab's origin is bottom-left, so we flip the row index for top-down ordering.
    y_mm = PAGE_HEIGHT_MM - TOP_MARGIN_MM - (row + 1) * VERTICAL_PITCH_MM

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
    _draw_address_block(c, x_mm, y_mm, lines)


def render_labels_pdf(addresses: list[LabelAddress]) -> bytes:
    """
    Render an A4 PDF (Avery L7173 grid). Empty cells beyond the supplied addresses stay blank,
    extra addresses spill over to additional pages (8 per page).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("GoupixDex — Étiquettes d'envoi")
    c.setAuthor("GoupixDex")

    if not addresses:
        # Blank A4 with the cut guides only — keeps the preview valid even with zero entries.
        for r in range(ROWS):
            for col in range(COLS):
                x_mm = LEFT_MARGIN_MM + col * HORIZONTAL_PITCH_MM
                y_mm = PAGE_HEIGHT_MM - TOP_MARGIN_MM - (r + 1) * VERTICAL_PITCH_MM
                _draw_label_border(c, x_mm, y_mm)
        c.showPage()
        c.save()
        return buf.getvalue()

    for index, addr in enumerate(addresses):
        if index > 0 and index % LABELS_PER_PAGE == 0:
            c.showPage()
        position = index % LABELS_PER_PAGE
        row = position // COLS
        col = position % COLS
        _draw_label(c, col, row, addr)

    c.showPage()
    c.save()
    return buf.getvalue()
