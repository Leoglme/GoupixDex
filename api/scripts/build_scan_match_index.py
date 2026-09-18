"""
Build the on-device scan-match index from TCGdex card images.

For every card with an image in the supported locales, this downloads the
``low.webp`` render, computes a 1024-bit perceptual hash (512 global dHash
bits + 512 text-band dHash bits) and writes two files consumed by the web
scanner (``web/public/scan-index/``):

- ``index-v{N}.bin``  — header ``GPXI`` + u32 version + u32 count, then
  ``count`` fixed 128-byte records (the hashes, order matches the JSON);
- ``index-v{N}.json`` — ``{version, cards: [[tcgdexCardId, locale, name,
  setId, localId], …]}``.

The hash spec MUST stay bit-identical with the client implementation in
``web/app/workers/cardDetector.worker.ts`` (grayscale ITU-R 601-2 integer
luma, BOX resize, row/column dHash, same band boxes) — a drifted spec makes
every phone scan miss the index.

Progress is cached in ``scan-index-work.json`` next to this script, so an
interrupted run resumes instead of re-downloading ~44k images.

Usage: ``python scripts/build_scan_match_index.py [--locales ja,en,fr]``
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

INDEX_VERSION = 1
LOCALES = ("ja", "en", "fr")
API_BASE = "https://api.tcgdex.net/v2"
USER_AGENT = "GoupixDex-scan-index/1.0"
DOWNLOAD_WORKERS = 10
RETRIES = 3

SCRIPT_DIR = Path(__file__).resolve().parent
WORK_FILE = SCRIPT_DIR / "scan-index-work.json"
OUT_DIR = SCRIPT_DIR.parent.parent / "web" / "public" / "scan-index"

# Text bands (fractions of the card image) — keep in sync with the worker.
NAME_BOX = (0.05, 0.025, 0.72, 0.10)
ATTACK_BOX = (0.08, 0.55, 0.92, 0.88)

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def http_get(url: str, timeout: float = 25.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {RETRIES} tries: {last}")


def dhash_bits(gray: Image.Image, w: int, h: int, cols: bool = False) -> list[int]:
    """dHash: BOX-resize then compare horizontal (rows) or vertical (cols) neighbours."""
    if cols:
        img = gray.resize((w, h + 1), Image.Resampling.BOX)
        px = list(img.getdata())
        return [1 if px[r * w + c] > px[(r + 1) * w + c] else 0 for r in range(h) for c in range(w)]
    img = gray.resize((w + 1, h), Image.Resampling.BOX)
    px = list(img.getdata())
    return [1 if px[r * (w + 1) + c] > px[r * (w + 1) + c + 1] else 0 for r in range(h) for c in range(w)]


def band(gray: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    w, h = gray.size
    return gray.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))


def card_hash_bytes(img: Image.Image) -> bytes:
    """1024-bit perceptual hash of a full card image, packed MSB-first (128 bytes)."""
    gray = img.convert("L")
    bits = (
        dhash_bits(gray, 16, 16)
        + dhash_bits(gray, 16, 16, cols=True)
        + dhash_bits(band(gray, NAME_BOX), 32, 8)
        + dhash_bits(band(gray, ATTACK_BOX), 32, 8)
    )
    out = bytearray(len(bits) // 8)
    for i, bit in enumerate(bits):
        if bit:
            out[i >> 3] |= 0x80 >> (i & 7)
    return bytes(out)


def load_work() -> dict[str, str]:
    if WORK_FILE.exists():
        try:
            return json.loads(WORK_FILE.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def hash_one(loc: str, brief: dict, work: dict[str, str]) -> tuple[str, dict, str | None]:
    key = f"{loc}:{brief['id']}"
    if key in work:
        return key, brief, work[key]
    try:
        raw = http_get(str(brief["image"]) + "/low.webp")
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        return key, brief, card_hash_bytes(img).hex()
    except Exception as exc:  # noqa: BLE001
        log(f"  skip {key}: {exc}")
        return key, brief, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locales", default=",".join(LOCALES))
    args = parser.parse_args()
    locales = [loc.strip() for loc in args.locales.split(",") if loc.strip()]

    work = load_work()
    entries: list[tuple[list, str]] = []  # (metadata row, hash hex)

    for loc in locales:
        briefs = json.loads(http_get(f"{API_BASE}/{loc}/cards", timeout=90.0))
        briefs = [b for b in briefs if isinstance(b, dict) and b.get("image") and b.get("id")]
        log(f"{loc}: {len(briefs)} cartes avec image")
        done = 0
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            for key, brief, hex_hash in pool.map(lambda b: hash_one(loc, b, work), briefs):
                done += 1
                if hex_hash is not None:
                    work[key] = hex_hash
                    cid = str(brief["id"])
                    set_id = cid.rsplit("-", 1)[0] if "-" in cid else cid
                    entries.append(
                        ([cid, loc, str(brief.get("name") or ""), set_id, str(brief.get("localId") or "")], hex_hash)
                    )
                if done % 500 == 0:
                    log(f"  {loc}: {done}/{len(briefs)} ({time.monotonic() - t0:.0f}s)")
                    WORK_FILE.write_text(json.dumps(work), encoding="utf-8")
        WORK_FILE.write_text(json.dumps(work), encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bin_path = OUT_DIR / f"index-v{INDEX_VERSION}.bin"
    json_path = OUT_DIR / f"index-v{INDEX_VERSION}.json"

    blob = bytearray(b"GPXI")
    blob += INDEX_VERSION.to_bytes(4, "little")
    blob += len(entries).to_bytes(4, "little")
    for _, hex_hash in entries:
        blob += bytes.fromhex(hex_hash)
    bin_path.write_bytes(bytes(blob))
    json_path.write_text(
        json.dumps({"version": INDEX_VERSION, "cards": [row for row, _ in entries]}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    log(f"écrit: {bin_path} ({len(blob)/1e6:.1f} MB) + {json_path} ({json_path.stat().st_size/1e6:.1f} MB), {len(entries)} cartes")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
