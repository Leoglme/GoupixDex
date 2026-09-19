# -*- coding: utf-8 -*-
"""Convertit l'index d'empreintes pHash (DCT whole+art, 512 bits) en binaire
compact chargé par le scanner web.

Entrée : un `scan-index.json` façon TailTCG — `{cards: [[id, locale, name,
setId, hashesB64, image], …]}`, `hashesB64` = 64 octets base64 (32 « carte
entière » + 32 « illustration »).

Sorties dans `web/public/scan-index/` :
- `phash-v1.bin`  — en-tête `GPXH` + u32 version + u32 count + u32 réservé,
  puis `count` enregistrements de 64 octets (whole[32] ++ art[32]) ;
- `phash-v1.json` — `{version, count, cards: [[tcgdexCardId, locale, name,
  setId, localId], …]}`, même ordre que le binaire.

Usage : `python build_phash_index.py <scan-index.json source>`
"""
from __future__ import annotations

import base64
import json
import struct
import sys
from pathlib import Path

VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR.parent.parent / "web" / "public" / "scan-index"


def local_id(card_id: str, set_id: str) -> str:
    """Numéro de la carte dans son set (déduit de l'identifiant TCGdex)."""
    prefix = f"{set_id}-"
    if card_id.startswith(prefix):
        return card_id[len(prefix):]
    return card_id.rsplit("-", 1)[-1]


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not src or not src.exists():
        raise SystemExit("source scan-index.json introuvable")
    data = json.loads(src.read_text(encoding="utf-8"))
    rows = data["cards"]

    meta: list[list[str]] = []
    blob = bytearray()
    skipped = 0
    for row in rows:
        card_id, locale, name, set_id, hashes_b64 = row[0], row[1], row[2], row[3], row[4]
        raw = base64.b64decode(hashes_b64)
        if len(raw) != 64:
            skipped += 1
            continue
        blob += raw
        meta.append([card_id, locale, name or "", set_id or "", local_id(card_id, set_id or "")])

    count = len(meta)
    header = b"GPXH" + struct.pack("<III", VERSION, count, 0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "phash-v1.bin").write_bytes(header + bytes(blob))
    (OUT_DIR / "phash-v1.json").write_text(
        json.dumps({"version": VERSION, "count": count, "cards": meta}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_bin = (16 + count * 64) / 1_000_000
    print(f"phash-v1: {count} cartes, {skipped} ignorées | bin {size_bin:.1f} Mo")


if __name__ == "__main__":
    main()
