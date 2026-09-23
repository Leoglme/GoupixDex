"""One-shot : renseigne ``purchase_price_eur`` sur les cartes de collection d'un utilisateur.

Chaque entrée (set + numéro + prix) est rapprochée d'une carte de la collection de l'utilisateur
par set/numéro **normalisés** (casse, tirets et zéros de tête ignorés), puis le prix d'achat est écrit.

Source des données : variable d'env ``PURCHASE_PRICES_JSON`` (liste JSON) ou ``--file <chemin>``.
Chaque item : ``{"set": "M1L", "number": "064", "price": 6}``.

Cible : l'utilisateur admin (``is_admin=1``, compte seedé) ; sinon ``TARGET_USER_EMAIL``.

Toujours faire un ``--dry-run`` d'abord : il affiche le rapprochement carte → prix sans rien écrire.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

# ``python scripts/set_purchase_prices.py`` met ``scripts/`` sur sys.path, pas la racine appli.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from config import get_settings
from models.collection_card import CollectionCard
from models.user import User


def _norm_set(value: str | None) -> str:
    """Normalise un code de set pour le rapprochement (majuscules, alphanumérique seul)."""
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def _norm_num(value: str | None) -> str:
    """Normalise un numéro de carte (partie avant ``/``, chiffres sans zéros de tête)."""
    head = str(value or "").strip().split("/")[0]
    digits = "".join(ch for ch in head if ch.isdigit())
    return digits.lstrip("0") or "0"


def _load_entries(file_path: str | None) -> list[dict[str, Any]]:
    """Charge la liste d'entrées depuis ``--file`` ou l'env ``PURCHASE_PRICES_JSON``."""
    raw: str | None
    if file_path:
        raw = Path(file_path).read_text(encoding="utf-8")
    else:
        raw = os.environ.get("PURCHASE_PRICES_JSON")
    if not raw:
        raise SystemExit("Aucune donnée : passe --file <json> ou définis PURCHASE_PRICES_JSON.")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise SystemExit("Le JSON doit être une liste d'objets {set, number, price}.")
    return data


def _resolve_user(db: Session) -> User | None:
    """Retourne l'utilisateur cible : admin seedé, sinon celui de ``TARGET_USER_EMAIL``."""
    email = os.environ.get("TARGET_USER_EMAIL")
    if email:
        return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    admins = db.query(User).filter(User.is_admin.is_(True)).all()
    if len(admins) == 1:
        return admins[0]
    return None


def main() -> None:
    """Point d'entrée : rapproche puis (hors dry-run) écrit les prix d'achat."""
    parser = argparse.ArgumentParser(description="Renseigne les prix d'achat des cartes de collection.")
    parser.add_argument("--file", default=None, help="Chemin d'un JSON [{set, number, price}].")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le rapprochement sans rien écrire.")
    args = parser.parse_args()

    entries = _load_entries(args.file)

    # Charge api/.env explicitement (indépendant du CWD), comme run_migrations.py.
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as db:
        user = _resolve_user(db)
        if user is None:
            raise SystemExit("Utilisateur cible introuvable (admin unique ou TARGET_USER_EMAIL).")
        print(f"Utilisateur cible : #{user.id} <{user.email}>")

        cards = (
            db.query(CollectionCard)
            .filter(CollectionCard.user_id == user.id, CollectionCard.is_placeholder.is_(False))
            .all()
        )
        index: dict[tuple[str, str], list[CollectionCard]] = {}
        for card in cards:
            index.setdefault((_norm_set(card.set_code), _norm_num(card.card_number)), []).append(card)
        print(f"Cartes possédées de l'utilisateur : {len(cards)}")

        matched = 0
        updated = 0
        problems: list[str] = []
        for entry in entries:
            set_code = str(entry.get("set", "")).strip()
            number = str(entry.get("number", "")).strip()
            price = Decimal(str(entry.get("price"))).quantize(Decimal("0.01"))
            found = index.get((_norm_set(set_code), _norm_num(number)), [])
            label = f"{set_code} {number} → {price} €"
            if len(found) == 0:
                problems.append(f"  ✗ NON TROUVÉE : {label}")
                continue
            if len(found) > 1:
                ids = ", ".join(f"#{c.id} {c.display_name}" for c in found)
                problems.append(f"  ✗ AMBIGUË : {label} ({ids})")
                continue
            card = found[0]
            matched += 1
            before = card.purchase_price_eur
            note = f" (était {before} €)" if before is not None else ""
            print(f"  ✓ {label}  →  #{card.id} {card.display_name}{note}")
            if not args.dry_run and before != price:
                card.purchase_price_eur = price
                updated += 1

        if problems:
            print("\nÀ vérifier :")
            print("\n".join(problems))

        if args.dry_run:
            print(f"\n[DRY-RUN] {matched}/{len(entries)} rapprochées, aucune écriture.")
        else:
            db.commit()
            print(f"\nÉcrit : {updated} prix mis à jour ({matched}/{len(entries)} rapprochées).")


if __name__ == "__main__":
    main()
