"""One-shot : remplace TOUS les produits scellés d'un utilisateur par une liste fournie.

Supprime les scellés existants de l'utilisateur (leurs snapshots de prix suivent en
cascade), puis crée chaque item ``{name, edition, product_type, purchase_price_eur,
market_price_eur}`` avec la langue ``fr`` et une quantité de 1.

Source des données : ``--file <json>`` ou l'env ``SEALED_ITEMS_JSON`` (liste JSON).
Cible : l'utilisateur admin (``is_admin=1``), sinon ``TARGET_USER_EMAIL``.

Toujours lancer ``--dry-run`` d'abord : il liste ce qui serait supprimé puis créé.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ``python scripts/import_sealed_products.py`` met ``scripts/`` sur sys.path, pas la racine.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from config import get_settings
from models.sealed_product import SEALED_PRODUCT_TYPES, SealedProduct
from models.user import User
from services import sealed_product_service
from services.cardmarket_local_price_service import resolve_sealed_market_price_eur
from services.cardmarket_product_resolve_service import resolve_cardmarket_product


def _load_items(file_path: str | None) -> list[dict[str, Any]]:
    """Charge la liste d'items depuis ``--file`` ou l'env ``SEALED_ITEMS_JSON``."""
    raw = Path(file_path).read_text(encoding="utf-8") if file_path else os.environ.get("SEALED_ITEMS_JSON")
    if not raw:
        raise SystemExit("Aucune donnée : passe --file <json> ou définis SEALED_ITEMS_JSON.")
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise SystemExit("Le JSON doit être une liste non vide d'objets scellés.")
    for item in data:
        if str(item.get("product_type", "")) not in SEALED_PRODUCT_TYPES:
            raise SystemExit(f"product_type invalide : {item.get('product_type')!r} pour {item.get('name')!r}.")
    return data


def _resolve_user(db: Session) -> User | None:
    """Retourne l'utilisateur cible : celui de ``TARGET_USER_EMAIL``, sinon l'admin unique."""
    email = os.environ.get("TARGET_USER_EMAIL")
    if email:
        return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    admins = db.query(User).filter(User.is_admin.is_(True)).all()
    return admins[0] if len(admins) == 1 else None


def main() -> None:
    """Point d'entrée : remplace les scellés de l'utilisateur cible par la liste fournie."""
    parser = argparse.ArgumentParser(description="Remplace tous les produits scellés d'un utilisateur.")
    parser.add_argument("--file", default=None, help="Chemin d'un JSON [{name, edition, product_type, ...}].")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le plan sans rien écrire.")
    args = parser.parse_args()

    items = _load_items(args.file)

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

        existing = db.query(SealedProduct).filter(SealedProduct.user_id == user.id).all()
        print(f"\n--- Existants (seront supprimés) : {len(existing)} ---")
        for row in existing:
            price = f"{float(row.market_price_eur):.2f} €" if row.market_price_eur is not None else "—"
            print(f"  #{row.id} {row.name} · {row.set_name or '—'} · marché {price}")

        print(f"\n--- À créer : {len(items)} ---")
        for item in items:
            tags = ("[cm]" if item.get("cardmarket_id_product") else "") + ("[img]" if item.get("image_url") else "")
            print(
                f"  {item['name']} · {item.get('edition') or '—'} · {item['product_type']}"
                f" · achat {float(item['purchase_price_eur']):.2f} €"
                f" · marché {float(item['market_price_eur']):.2f} € {tags}"
            )

        if args.dry_run:
            print("\n[DRY-RUN] aucune écriture.")
            return

        for row in existing:
            db.delete(row)
        db.commit()

        for item in items:
            id_product = item.get("cardmarket_id_product")
            id_product = int(id_product) if id_product is not None else None
            image_url = item.get("image_url")
            market = float(item["market_price_eur"])
            cardmarket_url = item.get("cardmarket_url")

            # Best-effort : depuis l'URL Cardmarket, récupère l'idProduct (et l'image à défaut) si non fourni.
            if id_product is None and cardmarket_url:
                resolved = resolve_cardmarket_product(cardmarket_url)
                if resolved.get("id_product"):
                    id_product = int(resolved["id_product"])
                    if not image_url and resolved.get("image_url"):
                        image_url = resolved["image_url"]
                    print(f"  résolu Cardmarket : {item['name']} → idProduct {id_product}")

            # idProduct connu → prix marché scellé (trend Cardmarket) depuis le guide local (jamais écrasé s'il est absent).
            if id_product is not None:
                guide_price = resolve_sealed_market_price_eur(id_product)
                if guide_price is not None:
                    market = float(guide_price)

            sealed_product_service.create_sealed_product(
                db,
                user.id,
                name=item["name"],
                product_type=item["product_type"],
                set_name=item.get("edition"),
                language="fr",
                quantity=int(item.get("quantity", 1)),
                purchase_price_eur=float(item["purchase_price_eur"]),
                notes=None,
                image_url=image_url,
                cardmarket_id_product=id_product,
                cardmarket_url=cardmarket_url,
                market_price_eur=market,
                tcgplayer_id=(int(item["tcgplayer_id"]) if item.get("tcgplayer_id") is not None else None),
            )
        print(f"\nSupprimés : {len(existing)} · Créés : {len(items)}.")


if __name__ == "__main__":
    main()
