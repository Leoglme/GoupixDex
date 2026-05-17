"""
Cheap pre-check run *before* any (paid) Groq vision call: does this frame
actually contain a sharp, framed trading card?

A phone camera in "cash register" mode streams many frames; without this gate
an empty desk, a blurry pan or a finger would each cost a Groq request and
trip 429s. Pure Pillow + stdlib — no numpy / OpenCV dependency.

Heuristics (all must pass):

* **detail**   — luminance stddev. An empty/uniform surface is flat.
* **focus**    — edge-energy spread (variance-of-Laplacian proxy). A blurry
  or motion-smeared frame has little high-frequency content.
* **framing**  — the "busy" region (thresholded edges) must fill a large,
  roughly centered, card-proportioned part of the frame, i.e. an actual card
  presented to the lens rather than clutter in a corner.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps, ImageStat

logger = logging.getLogger(__name__)

#: Long edge the frame is downscaled to before analysis (speed).
_ANALYZE_EDGE = 256
#: Edge-map binarisation threshold (0–255) for the "busy region" mask.
_EDGE_BIN_THRESHOLD = 38

# --- Acceptance thresholds (strict: better to skip a frame than to spam Groq;
#     a real card held in frame produces several qualifying frames anyway).
_MIN_DETAIL_STDDEV = 17.0
_MIN_FOCUS = 9.0
_MIN_FILL = 0.42
_CENTER_LO = 0.22
_CENTER_HI = 0.78
_CARD_AR_MIN = 0.45
_CARD_AR_MAX = 2.20


@dataclass(frozen=True)
class CardGateResult:
    """Outcome of :func:`assess_card_image`."""

    is_card: bool
    #: ``ok`` | ``unreadable`` | ``too_small`` | ``empty`` | ``blurry`` | ``no_card``
    reason: str
    detail: float
    focus: float
    fill: float


def _bbox_metrics(edges: Image.Image, w: int, h: int) -> tuple[float, bool, bool]:
    """Return ``(fill_ratio, centered, aspect_ok)`` for the thresholded edge map."""
    lut = [0 if i <= _EDGE_BIN_THRESHOLD else 255 for i in range(256)]
    box = edges.point(lut).getbbox()
    if not box:
        return 0.0, False, False
    bx0, by0, bx1, by1 = box
    bw = max(1, bx1 - bx0)
    bh = max(1, by1 - by0)
    fill = (bw * bh) / float(w * h)
    cx = (bx0 + bx1) / 2.0 / w
    cy = (by0 + by1) / 2.0 / h
    centered = _CENTER_LO <= cx <= _CENTER_HI and _CENTER_LO <= cy <= _CENTER_HI
    aspect = bw / bh
    aspect_ok = _CARD_AR_MIN <= aspect <= _CARD_AR_MAX
    return fill, centered, aspect_ok


def assess_card_image(image_bytes: bytes) -> CardGateResult:
    """
    Decide whether ``image_bytes`` looks like a card worth sending to OCR.

    Never raises — any decode/processing error is reported as a non-card so the
    caller simply skips the frame (no Groq call).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("L")
    except Exception:  # noqa: BLE001 - any malformed upload is just "not a card"
        return CardGateResult(False, "unreadable", 0.0, 0.0, 0.0)

    img.thumbnail((_ANALYZE_EDGE, _ANALYZE_EDGE))
    w, h = img.size
    if w < 48 or h < 48:
        return CardGateResult(False, "too_small", 0.0, 0.0, 0.0)

    detail = float(ImageStat.Stat(img).stddev[0])
    edges = img.filter(ImageFilter.FIND_EDGES)
    focus = float(ImageStat.Stat(edges).stddev[0])
    fill, centered, aspect_ok = _bbox_metrics(edges, w, h)

    if detail < _MIN_DETAIL_STDDEV:
        return CardGateResult(False, "empty", detail, focus, fill)
    if focus < _MIN_FOCUS:
        return CardGateResult(False, "blurry", detail, focus, fill)
    if fill < _MIN_FILL or not centered or not aspect_ok:
        return CardGateResult(False, "no_card", detail, focus, fill)
    return CardGateResult(True, "ok", detail, focus, fill)
