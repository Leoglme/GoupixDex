"""One-shot : enregistre des annonces Leboncoin déjà en ligne sur les articles d'un utilisateur.

Sert quand une publication Leboncoin a réussi sans être enregistrée (worker arrêté après le dépôt) ou sans
l'identifiant de l'annonce : l'article est marqué en ligne sur Leboncoin avec son annonce, comme après une
publication confirmée par le worker.

Source des données : ``--file <chemin>`` (liste JSON). Chaque item :
``{"article_id": 119, "listing_id": "3278016312", "published_at": "2026-09-27T19:11:48+00:00"}``
(``published_at`` : première mise en ligne sur Leboncoin, gardée si l'article en a déjà une).

Cible : l'utilisateur admin (``is_admin=1``, compte seedé) ; sinon ``TARGET_USER_EMAIL``.

Toujours faire un ``--dry-run`` d'abord : il affiche chaque article et le changement prévu sans rien écrire.
Les journaux du dépôt sont publics : rien d'autre que l'article, son prix et l'annonce n'est affiché.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

# ``python scripts/set_leboncoin_listings.py`` met ``scripts/`` sur sys.path, pas la racine appli.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from config import get_settings
from models.article import Article
from models.user import User


def _load_entries(file_path: str) -> list[dict[str, Any]]:
    """Charge la liste des annonces à enregistrer depuis ``--file``."""
    data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Le JSON doit être une liste d'objets {article_id, listing_id, published_at}.")
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
    """Point d'entrée : affiche puis (hors dry-run) enregistre les annonces Leboncoin."""
    parser = argparse.ArgumentParser(description="Enregistre des annonces Leboncoin déjà en ligne sur des articles.")
    parser.add_argument("--file", required=True, help="Chemin d'un JSON [{article_id, listing_id, published_at}].")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les changements sans rien écrire.")
    args = parser.parse_args()

    entries = _load_entries(args.file)

    # Charge api/.env explicitement (indépendant du CWD), comme run_migrations.py.
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        user = _resolve_user(db)
        if user is None:
            raise SystemExit("Utilisateur cible introuvable (admin unique ou TARGET_USER_EMAIL).")
        print(f"Utilisateur cible : #{user.id}")

        updated = 0
        for entry in entries:
            article_id = int(entry["article_id"])
            listing_id = str(entry["listing_id"]).strip()
            published_at = dt.datetime.fromisoformat(str(entry["published_at"]))
            article = db.query(Article).filter(Article.id == article_id, Article.user_id == user.id).first()
            if article is None:
                print(f"  ✗ #{article_id} introuvable pour cet utilisateur")
                continue
            if article.is_sold:
                print(f"  ✗ #{article_id} {article.title} : vendu, ignoré")
                continue
            before = "en ligne" if article.published_on_leboncoin else "hors ligne"
            print(
                f"  ✓ #{article.id} {article.title} (prix {article.sell_price} €) : Leboncoin {before}, "
                f"annonce {article.leboncoin_listing_id or '—'} → en ligne, annonce {listing_id}"
            )
            if args.dry_run:
                continue
            article.published_on_leboncoin = True
            article.leboncoin_listing_id = listing_id
            if article.leboncoin_published_at is None:
                article.leboncoin_published_at = published_at
            article.offers_for_sale = True
            updated += 1

        if args.dry_run:
            print(f"\n[DRY-RUN] {len(entries)} annonce(s) examinée(s), aucune écriture.")
        else:
            db.commit()
            print(f"\nÉcrit : {updated} article(s) mis à jour.")


if __name__ == "__main__":
    main()
