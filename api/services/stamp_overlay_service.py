"""Overlay optional La Poste stamp PDFs onto label sheets at native scale (no shrinking)."""

from __future__ import annotations

import base64
import logging
import re
from io import BytesIO

import fitz  # PyMuPDF

from services.shipping_label_service import (
    HORIZONTAL_PITCH_MM,
    LABEL_WIDTH_MM,
    LABELS_PER_PAGE,
    LEFT_MARGIN_MM,
    TOP_MARGIN_MM,
    VERTICAL_PITCH_MM,
)

logger = logging.getLogger(__name__)

PAIRS_PER_PAGE = 4
MAX_STAMP_PDF_BYTES = 3 * 1024 * 1024
STAMP_GAP_MM = 3.0

_MM_TO_PT = 72.0 / 25.4


def mm_to_pt(mm_val: float) -> float:
    return mm_val * _MM_TO_PT


def pt_to_mm(pt_val: float) -> float:
    return pt_val * 25.4 / 72.0


def decode_stamp_pdf_base64(raw: str | None) -> bytes | None:
    """Return PDF bytes or ``None``. Raises ``ValueError`` on invalid input."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    if "," in s and re.match(r"^\s*data:", s, re.IGNORECASE):
        s = s.split(",", 1)[1].strip()
    try:
        decoded = base64.b64decode(s, validate=True)
    except Exception as exc:
        raise ValueError("Invalid stamp Base64 encoding.") from exc
    if len(decoded) > MAX_STAMP_PDF_BYTES:
        raise ValueError(f"Stamp PDF is too large (max {MAX_STAMP_PDF_BYTES // (1024 * 1024)} MiB).")
    if not decoded.startswith(b"%PDF"):
        raise ValueError("Stamp file must be a PDF.")
    return decoded


def _stamp_artwork_clip_rect(sp_page: fitz.Page) -> fitz.Rect | None:
    """
    Bounding box of the stamp as drawn by La Poste: images, vector strokes (dashed crop marks), and text.
    """
    mediabox = sp_page.rect
    union: fitz.Rect | None = None

    def add_rect(fr: fitz.Rect) -> None:
        nonlocal union
        if fr.is_empty:
            return
        union = fr if union is None else union | fr

    try:
        for info in sp_page.get_images(full=True):
            xref = info[0]
            try:
                for ir in sp_page.get_image_rects(xref):
                    add_rect(ir)
            except Exception:
                continue
    except Exception:
        pass

    try:
        for drawing in sp_page.get_drawings():
            rr = drawing.get("rect")
            if rr is None:
                continue
            add_rect(fitz.Rect(rr))
    except Exception:
        pass

    try:
        blocks = sp_page.get_text("dict").get("blocks", [])
        for block in blocks:
            bb = block.get("bbox")
            if bb is None:
                continue
            add_rect(fitz.Rect(bb))
    except Exception:
        pass

    if union is None or union.is_empty:
        return None

    pad_pt = 1.5
    expanded = union + (-pad_pt, -pad_pt, pad_pt, pad_pt)
    return expanded & mediabox


def _below_sender_safe(slot_index: int, parcels_on_page: int) -> bool:
    """
    True if no later parcel on this page shares our column and occupies the recipient row
    immediately below our sender (which would make a stamp under our sender overlap it).
    """
    return parcels_on_page <= slot_index + 2


def _bottom_edge_below_sender_mm(slot_index: int) -> float:
    """Bottom edge of this parcel's sender sticker (mm from physical top of sheet)."""
    sender_row = (slot_index // 2) * 2 + 1
    return TOP_MARGIN_MM + (sender_row + 1) * VERTICAL_PITCH_MM


def _pair_vertical_bounds_mm(slot_index: int) -> tuple[float, float]:
    """Top / bottom of recipient+sender pair (mm from top of sheet)."""
    rrow = (slot_index // 2) * 2
    top_mm = TOP_MARGIN_MM + rrow * VERTICAL_PITCH_MM
    bottom_mm = TOP_MARGIN_MM + (rrow + 2) * VERTICAL_PITCH_MM
    return top_mm, bottom_mm


def _bottom_edge_below_recipient_mm(label_idx_on_page: int) -> float:
    """Bottom edge of a single recipient sticker (mm from physical top of sheet)."""
    row = label_idx_on_page // 2
    return TOP_MARGIN_MM + (row + 1) * VERTICAL_PITCH_MM


def _recipient_vertical_bounds_mm(label_idx_on_page: int) -> tuple[float, float]:
    row = label_idx_on_page // 2
    top_mm = TOP_MARGIN_MM + row * VERTICAL_PITCH_MM
    bottom_mm = TOP_MARGIN_MM + (row + 1) * VERTICAL_PITCH_MM
    return top_mm, bottom_mm


def _below_recipient_safe(label_idx_on_page: int, labels_on_page: int) -> bool:
    """True if no recipient sticker is printed directly below on the same column."""
    below_idx = label_idx_on_page + 2
    return below_idx >= labels_on_page


def _paint_stamp_recipient_only(
    target_page: fitz.Page,
    *,
    label_idx_on_page: int,
    labels_on_page: int,
    stamp_bytes: bytes,
) -> bool:
    """Place stamp for recipient-only sheets (8 labels per page, no sender row)."""
    src = fitz.open(stream=stamp_bytes, filetype="pdf")
    try:
        if src.page_count < 1:
            return False
        sp = src[0]
        clip = _stamp_artwork_clip_rect(sp)
        if clip is None or clip.is_empty:
            return False

        pr = target_page.rect
        w_pt, h_pt = pr.width, pr.height
        stamp_w, stamp_h = clip.width, clip.height
        bottom_margin_pt = mm_to_pt(2)
        margin_pt = mm_to_pt(4)

        recipient_bottom_mm = _bottom_edge_below_recipient_mm(label_idx_on_page)
        y0_below_pt = mm_to_pt(recipient_bottom_mm + STAMP_GAP_MM)
        y1_below_pt = y0_below_pt + stamp_h

        if (
            _below_recipient_safe(label_idx_on_page, labels_on_page)
            and y1_below_pt <= h_pt - bottom_margin_pt
        ):
            col = label_idx_on_page % 2
            cell_left_mm = LEFT_MARGIN_MM + col * HORIZONTAL_PITCH_MM
            x_center_mm = cell_left_mm + LABEL_WIDTH_MM / 2
            stamp_w_mm = pt_to_mm(stamp_w)
            x0_pt = mm_to_pt(x_center_mm - stamp_w_mm / 2)
            x0_pt = max(margin_pt, min(x0_pt, w_pt - margin_pt - stamp_w))
            dest = fitz.Rect(x0_pt, y0_below_pt, x0_pt + stamp_w, y1_below_pt)
            if dest.x1 <= w_pt - margin_pt + 0.01:
                target_page.show_pdf_page(dest, src, 0, clip=clip)
                return True

        top_mm, bottom_mm = _recipient_vertical_bounds_mm(label_idx_on_page)
        y_top_mm = (top_mm + bottom_mm) / 2 - pt_to_mm(stamp_h) / 2
        y0_right_pt = mm_to_pt(y_top_mm)
        y1_right_pt = y0_right_pt + stamp_h
        x0_right_pt = w_pt - margin_pt - stamp_w
        if (
            x0_right_pt >= margin_pt - 0.01
            and y0_right_pt >= margin_pt - 0.01
            and y1_right_pt <= h_pt - bottom_margin_pt + 0.01
        ):
            dest_r = fitz.Rect(x0_right_pt, y0_right_pt, x0_right_pt + stamp_w, y1_right_pt)
            target_page.show_pdf_page(dest_r, src, 0, clip=clip)
            return True
        return False
    finally:
        src.close()


def _paint_stamp_native(
    target_page: fitz.Page,
    *,
    slot_index: int,
    parcels_on_page: int,
    stamp_bytes: bytes,
) -> bool:
    """
    Place stamp at 1:1 (dest size matches clip).

    Priority:
    1) Just **below** this parcel's sender vignette when no sticker is printed directly underneath (same column);
       centred on its column (not pinned to page bottom).
    2) Else **right-aligned** on the sheet, vertically centred on this parcel's recipient+sender pair.
    """
    src = fitz.open(stream=stamp_bytes, filetype="pdf")
    try:
        if src.page_count < 1:
            return False
        sp = src[0]
        clip = _stamp_artwork_clip_rect(sp)
        if clip is None or clip.is_empty:
            logger.warning("stamp pdf: could not derive artwork bbox; skip parcel overlay")
            return False

        pr = target_page.rect
        w_pt, h_pt = pr.width, pr.height
        stamp_w, stamp_h = clip.width, clip.height
        bottom_margin_pt = mm_to_pt(2)
        margin_pt = mm_to_pt(4)

        sender_bottom_mm = _bottom_edge_below_sender_mm(slot_index)
        y_below_mm = sender_bottom_mm + STAMP_GAP_MM
        y0_below_pt = mm_to_pt(y_below_mm)
        y1_below_pt = y0_below_pt + stamp_h

        if (
            _below_sender_safe(slot_index, parcels_on_page)
            and y1_below_pt <= h_pt - bottom_margin_pt
        ):
            col = slot_index % 2
            cell_left_mm = LEFT_MARGIN_MM + col * HORIZONTAL_PITCH_MM
            x_center_mm = cell_left_mm + LABEL_WIDTH_MM / 2
            stamp_w_mm = pt_to_mm(stamp_w)
            x0_mm = x_center_mm - stamp_w_mm / 2
            x0_pt = mm_to_pt(x0_mm)
            x0_pt = max(margin_pt, min(x0_pt, w_pt - margin_pt - stamp_w))
            dest = fitz.Rect(x0_pt, y0_below_pt, x0_pt + stamp_w, y1_below_pt)
            if dest.x1 <= w_pt - margin_pt + 0.01:
                target_page.show_pdf_page(dest, src, 0, clip=clip)
                return True

        # Unsafe under sender (another parcel below on same column): skip straight to right edge.
        pair_top_mm, pair_bottom_mm = _pair_vertical_bounds_mm(slot_index)
        stamp_h_mm = pt_to_mm(stamp_h)
        y_center_mm = (pair_top_mm + pair_bottom_mm) / 2
        y_top_mm = y_center_mm - stamp_h_mm / 2
        y0_right_pt = mm_to_pt(y_top_mm)
        y1_right_pt = y0_right_pt + stamp_h

        x0_right_pt = w_pt - margin_pt - stamp_w
        if (
            x0_right_pt >= margin_pt - 0.01
            and y0_right_pt >= margin_pt - 0.01
            and y1_right_pt <= h_pt - bottom_margin_pt + 0.01
        ):
            dest_r = fitz.Rect(x0_right_pt, y0_right_pt, x0_right_pt + stamp_w, y1_right_pt)
            target_page.show_pdf_page(dest_r, src, 0, clip=clip)
            return True

        return False
    finally:
        src.close()


def _append_stamp_overflow_page(doc: fitz.Document, stamp_bytes: bytes) -> None:
    """Append a new A4 page and paint the stamp once at native 1:1 (centered)."""
    src = fitz.open(stream=stamp_bytes, filetype="pdf")
    try:
        if src.page_count < 1:
            return
        sp = src[0]
        clip = _stamp_artwork_clip_rect(sp)
        if clip is None or clip.is_empty:
            return
        np = doc.new_page(width=doc[-1].rect.width, height=doc[-1].rect.height)
        pr = np.rect
        sw, sh = clip.width, clip.height
        x0 = max(mm_to_pt(4), (pr.width - sw) / 2)
        y0 = max(mm_to_pt(4), (pr.height - sh) / 2)
        dest = fitz.Rect(x0, y0, x0 + sw, y0 + sh)
        np.show_pdf_page(dest, src, 0, clip=clip)
    finally:
        src.close()


def overlay_stamps_on_labels_pdf(
    labels_pdf_bytes: bytes,
    stamps_by_parcel_index: list[bytes | None],
    *,
    paired_sender_layout: bool = True,
) -> bytes:
    """
    Composite stamps at native PDF scale.

    ``paired_sender_layout`` must match ``render_labels_pdf(..., sender=...)``: paired when sender labels are printed.
    """
    if not any(stamps_by_parcel_index):
        return labels_pdf_bytes

    slots_per_page = PAIRS_PER_PAGE if paired_sender_layout else LABELS_PER_PAGE

    doc = fitz.open(stream=labels_pdf_bytes, filetype="pdf")
    try:
        total_parcels = len(stamps_by_parcel_index)
        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            remaining = total_parcels - page_idx * slots_per_page
            if remaining <= 0:
                break
            slots_on_page = min(slots_per_page, remaining)
            start = page_idx * slots_per_page
            for slot in range(slots_per_page):
                parcel_i = start + slot
                if parcel_i >= len(stamps_by_parcel_index):
                    break
                stamp_bytes = stamps_by_parcel_index[parcel_i]
                if not stamp_bytes:
                    continue
                try:
                    if paired_sender_layout:
                        placed = _paint_stamp_native(
                            page,
                            slot_index=slot,
                            parcels_on_page=slots_on_page,
                            stamp_bytes=stamp_bytes,
                        )
                    else:
                        placed = _paint_stamp_recipient_only(
                            page,
                            label_idx_on_page=slot,
                            labels_on_page=slots_on_page,
                            stamp_bytes=stamp_bytes,
                        )
                    if not placed:
                        _append_stamp_overflow_page(doc, stamp_bytes)
                except Exception as exc:
                    logger.warning("stamp overlay failed parcel_index=%s: %s", parcel_i, exc)

        out = BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()
