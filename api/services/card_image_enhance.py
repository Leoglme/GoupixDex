"""
Light, conservative image cleanup applied *just before* the Groq OCR call.

The phone already ships a perspective-deskewed card (OpenCV warp in the Web
Worker), but mobile cameras still send slightly soft, contrasty-or-flat frames
depending on flash / lighting. A small auto-contrast + unsharp mask pass
recovers a noticeable amount of OCR accuracy on the marginal frames without
ever distorting an already-clean one.

Pure Pillow + stdlib — no numpy, no new dependency.
"""

from __future__ import annotations

import io
import logging

from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

#: Long edge cap. Groq vision has its own resize anyway; trimming here cuts
#: upload + decode time without losing legibility for cards.
_MAX_EDGE = 1280
#: Histogram clip for auto-contrast — keeps highlights/shadows that matter.
_AUTOCONTRAST_CUTOFF = 1
#: Unsharp mask params tuned for printed text on small-edge images.
_USM_RADIUS = 1.4
_USM_PERCENT = 140
_USM_THRESHOLD = 3


def enhance_for_ocr(image_bytes: bytes) -> bytes:
    """
    Return a JPEG with mild contrast + sharpening applied. Fails open: any
    decode/processing error returns the original bytes unchanged.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        w, h = img.size
        long_edge = max(w, h)
        if long_edge > _MAX_EDGE:
            scale = _MAX_EDGE / float(long_edge)
            img = img.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )

        img = ImageOps.autocontrast(img, cutoff=_AUTOCONTRAST_CUTOFF)
        img = img.filter(
            ImageFilter.UnsharpMask(
                radius=_USM_RADIUS,
                percent=_USM_PERCENT,
                threshold=_USM_THRESHOLD,
            )
        )

        out = io.BytesIO()
        img.save(out, "JPEG", quality=92, optimize=True)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001 - cleanup must never break the pipeline
        logger.debug("enhance_for_ocr fail-open: %s", exc)
        return image_bytes
