"""
Build the on-device scan EMBEDDING index (v3) from TCGdex card images.

v2 (MobileNetV2 GAP, ImageNet) échouait sur le terrain : variantes reverse
holo + lumière naturelle chaude → la vraie carte plafonnait à ~0.39 quand des
voisins montaient à 0.63 (mesuré sur captures réelles). v3 embarque chaque
image avec le tour visuel de MobileCLIP-S0 (entraînement contrastif → robuste
à l'éclairage, au foil et au cadrage), quantifié int8 en 512-d BRUT — la
compression PCA-128 renormalisée détruisait la séparation signal/bruit
(mesuré : décor↔carte-égout 0.30 en 512-d → 0.63 après PCA-128).

Outputs (``web/public/scan-index/``):
- ``embed-v3.bin``  — ``GPXE`` + u32 version + u32 count + u32 dim, puis par
  carte : dim×int8 + f32 scale (dot(int8,int8)·sa·sb ≈ cosinus) ;
- ``embed-v3.json`` — ``{version, dim, cards: [[id, locale, name, setId, localId], …]}``.

Le MODÈLE (``web/public/scan-model/mobileclip-s0-vision-fp16.onnx``, fp16 :
moitié du poids, cos fp32↔fp16 ≥ 0.9999) doit être le
fichier exact que le navigateur exécute — les deux côtés embarquent avec les
mêmes poids sinon l'espace dérive. Préprocessing : 256×256 BILINEAR, pixels
bruts [0,1] SANS normalisation ImageNet (config CLIPFeatureExtractor de
MobileCLIP), entrée ``pixel_values``. Les embeddings bruts 512-d sont mis en
cache dans ``scan-embed-work-v3.npy`` / ``.keys.json`` — un run interrompu
reprend.

Usage: ``python scripts/build_scan_embed_index_v3.py``
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

INDEX_VERSION = 3
RAW_DIM = 512
INPUT_EDGE = 256
LOCALES = ("ja", "en", "fr")
API_BASE = "https://api.tcgdex.net/v2"
USER_AGENT = "GoupixDex-scan-index/3.0"
DOWNLOAD_WORKERS = 12
BATCH = 16
RETRIES = 3

SCRIPT_DIR = Path(__file__).resolve().parent
WORK_EMB = SCRIPT_DIR / "scan-embed-work-v3.npy"
WORK_KEYS = SCRIPT_DIR / "scan-embed-work-v3.keys.json"
MODEL_PATH = SCRIPT_DIR.parent.parent / "web" / "public" / "scan-model" / "mobileclip-s0-vision-fp16.onnx"
OUT_DIR = SCRIPT_DIR.parent.parent / "web" / "public" / "scan-index"

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


def preprocess(img: Image.Image) -> np.ndarray:
    """256×256 CHW float32 dans [0,1], sans normalisation — DOIT égaler le worker navigateur."""
    a = np.asarray(img.convert("RGB").resize((INPUT_EDGE, INPUT_EDGE), Image.Resampling.BILINEAR), dtype=np.float32)
    return (a / 255.0).transpose(2, 0, 1)


def main() -> None:
    sess = ort.InferenceSession(str(MODEL_PATH))
    input_name = sess.get_inputs()[0].name

    done: dict[str, int] = {}
    embs: list[np.ndarray] = []
    if WORK_EMB.exists() and WORK_KEYS.exists():
        stored = np.load(WORK_EMB)
        keys = json.loads(WORK_KEYS.read_text(encoding="utf-8"))
        for i, key in enumerate(keys):
            done[key] = i
        embs = [stored[i] for i in range(len(keys))]
        log(f"reprise: {len(done)} embeddings en cache")

    entries: list[tuple[list, int]] = []  # (metadata row, embedding index)

    def flush_work() -> None:
        np.save(WORK_EMB, np.stack(embs) if embs else np.zeros((0, RAW_DIM), dtype=np.float16))
        WORK_KEYS.write_text(json.dumps(list(done.keys())), encoding="utf-8")

    for loc in LOCALES:
        briefs = json.loads(http_get(f"{API_BASE}/{loc}/cards", timeout=90.0))
        briefs = [b for b in briefs if isinstance(b, dict) and b.get("image") and b.get("id")]
        log(f"{loc}: {len(briefs)} cartes avec image")

        todo = [b for b in briefs if f"{loc}:{b['id']}" not in done]

        def fetch(brief: dict) -> tuple[str, Image.Image | None]:
            key = f"{loc}:{brief['id']}"
            try:
                raw = http_get(str(brief["image"]) + "/low.webp")
                return key, Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception as exc:  # noqa: BLE001
                log(f"  skip {key}: {exc}")
                return key, None

        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            batch_keys: list[str] = []
            batch_arrays: list[np.ndarray] = []

            def run_batch() -> None:
                if not batch_keys:
                    return
                x = np.stack(batch_arrays)
                out = np.asarray(sess.run(None, {input_name: x})[0]).reshape(len(batch_keys), -1)
                for k, vec in zip(batch_keys, out):
                    norm = vec / (np.linalg.norm(vec) + 1e-9)
                    done[k] = len(embs)
                    embs.append(norm.astype(np.float16))
                batch_keys.clear()
                batch_arrays.clear()

            processed = 0
            for key, img in pool.map(fetch, todo):
                processed += 1
                if img is not None:
                    batch_keys.append(key)
                    batch_arrays.append(preprocess(img))
                    if len(batch_keys) >= BATCH:
                        run_batch()
                if processed % 500 == 0:
                    run_batch()
                    flush_work()
                    log(f"  {loc}: {processed}/{len(todo)} ({time.monotonic() - t0:.0f}s)")
            run_batch()
        flush_work()

        for b in briefs:
            key = f"{loc}:{b['id']}"
            if key in done:
                cid = str(b["id"])
                set_id = cid.rsplit("-", 1)[0] if "-" in cid else cid
                entries.append(
                    ([cid, loc, str(b.get("name") or ""), set_id, str(b.get("localId") or "")], done[key])
                )

    # --- 512-d brut, int8 par vecteur (le cosinus survit à la quantif ~0.99).
    reduced = np.stack([embs[i] for _, i in entries]).astype(np.float32)
    reduced /= np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9
    log(f"quantification int8 sur {reduced.shape}…")

    scales = np.abs(reduced).max(axis=1) / 127.0
    scales[scales == 0] = 1.0
    quantised = np.clip(np.round(reduced / scales[:, None]), -127, 127).astype(np.int8)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    blob = bytearray(b"GPXE")
    blob += INDEX_VERSION.to_bytes(4, "little")
    blob += len(entries).to_bytes(4, "little")
    blob += RAW_DIM.to_bytes(4, "little")
    for row_i in range(len(entries)):
        blob += quantised[row_i].tobytes()
        blob += np.float32(scales[row_i]).tobytes()
    (OUT_DIR / f"embed-v{INDEX_VERSION}.bin").write_bytes(bytes(blob))

    (OUT_DIR / f"embed-v{INDEX_VERSION}.json").write_text(
        json.dumps(
            {"version": INDEX_VERSION, "dim": RAW_DIM, "cards": [row for row, _ in entries]},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    log(f"écrit: embed-v{INDEX_VERSION}.bin ({len(blob) / 1e6:.1f} MB), {len(entries)} cartes")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
