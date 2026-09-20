"""Titres et descriptions Leboncoin (français, règles de diffusion)."""

from __future__ import annotations

import re

from models.article import Article

from services.leboncoin_listing_maps import leboncoin_etat_from_app_condition

_MAX_TITLE_LEN = 200

_SHIPPING_SNIPPET = (
    "Envoi soigné : protection sleeve et protège-cartes rigide, expédition rapide et emballage renforcé."
)

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.\w+")
_PHONE_RE = re.compile(r"(?:\+33|0)\s*[1-9](?:[\s.-]*\d{2}){4}")


def _title_for_leboncoin(article: Article) -> str:
    raw = (article.title or "").strip() or "Carte Pokémon"
    raw = re.sub(r"\s+", " ", raw)
    if len(raw) > _MAX_TITLE_LEN:
        raw = raw[: _MAX_TITLE_LEN - 1].rstrip() + "…"
    return raw


def _sanitize_description_line(line: str) -> str | None:
    s = line.strip()
    if not s:
        return ""
    low = s.lower()
    if any(x in low for x in ("vinted", "ebay", "cardmarket", "goupixdex", "http", "www.")):
        return None
    s = _URL_RE.sub("", s)
    s = _EMAIL_RE.sub("", s)
    s = _PHONE_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else None


def _sanitize_description_body(base: str) -> str:
    out: list[str] = []
    for line in base.splitlines():
        cleaned = _sanitize_description_line(line)
        if cleaned is None:
            continue
        out.append(cleaned)
    return "\n".join(out).strip()


def _graded_footer(article: Article) -> str | None:
    if not article.is_graded:
        return None
    parts: list[str] = ["Carte gradée par un professionnel."]
    if article.graded_cert_number and article.graded_cert_number.strip():
        parts.append(f"Numéro certificat : {article.graded_cert_number.strip()}.")
    return " ".join(parts)


def build_leboncoin_listing_copy(article: Article) -> tuple[str, str]:
    """
    Retourne (titre, description) pour le dépôt Leboncoin.

    Texte orienté modération LBC : français, pas de liens, pas de mention plateforme concurrente.
    """
    title = _title_for_leboncoin(article)
    base = _sanitize_description_body((article.description or "").strip())
    etat_lbc = leboncoin_etat_from_app_condition(article.condition, is_graded=article.is_graded)

    lines: list[str] = []
    if base:
        lines.append(base)
    else:
        lines.append(title)

    if not re.search(r"^\s*État\s*:", "\n".join(lines), re.MULTILINE | re.IGNORECASE):
        lines.append(f"État : {etat_lbc}.")

    body_joined = "\n".join(lines).lower()
    if "envoi" not in body_joined and "expédition" not in body_joined:
        lines.append("")
        lines.append(_SHIPPING_SNIPPET)

    graded = _graded_footer(article)
    if graded and "gradée" not in body_joined and "psa" not in body_joined and "cgc" not in body_joined:
        lines.append("")
        lines.append(graded)

    description = "\n".join(lines).strip()
    return title, description
