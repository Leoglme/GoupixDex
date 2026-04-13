"""
Proxy HTTP vers api.pokewallet.io (contournement Cloudflare / IP).
cPanel : fichier de démarrage = main.py, variable WSGI = application (voir passenger_wsgi.py).
"""

from __future__ import annotations

import os

import httpx
from flask import Flask, Response, request

TARGET = os.environ.get("POKE_WALLET_TARGET", "https://api.pokewallet.io").rstrip("/")
API_KEY = (os.environ.get("POKE_WALLET_API_KEY") or "").strip()
PROXY_SECRET = (os.environ.get("PROXY_SECRET") or "").strip()
USER_AGENT = (
    os.environ.get("POKE_WALLET_USER_AGENT") or "GoupixDex/1.0 (+https://goupixdex.dibodev.fr)"
).strip()

app = Flask(__name__)


def _upstream_headers() -> dict[str, str]:
    if not API_KEY:
        raise RuntimeError("POKE_WALLET_API_KEY manquant dans l'environnement.")
    return {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "X-API-Key": API_KEY,
    }


@app.route("/", defaults={"path": ""}, methods=["GET", "HEAD"])
@app.route("/<path:path>", methods=["GET", "HEAD"])
def forward(path: str) -> Response:
    if not PROXY_SECRET:
        return Response("PROXY_SECRET non configuré", status=500, mimetype="text/plain")
    if request.headers.get("X-Proxy-Secret", "") != PROXY_SECRET:
        return Response("Forbidden", status=403, mimetype="text/plain")
    try:
        hdrs = _upstream_headers()
    except RuntimeError as e:
        return Response(str(e), status=500, mimetype="text/plain")

    # Chemin + query tels que reçus (ex. /v1/foo?bar=1)
    url = TARGET + request.full_path

    try:
        r = httpx.request(
            request.method,
            url,
            headers=hdrs,
            timeout=60.0,
        )
    except httpx.RequestError as e:
        return Response(f"Upstream error: {e}", status=502, mimetype="text/plain")

    out = [("Content-Type", r.headers.get("content-type", "application/json"))]
    return Response(r.content, status=r.status_code, headers=out)


application = app
