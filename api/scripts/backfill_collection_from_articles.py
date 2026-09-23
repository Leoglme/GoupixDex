"""One-shot : crée dans « Ma Collection » les cartes possédées correspondant aux articles en vente.

Pour chaque article **non vendu** d'un utilisateur qui n'a pas encore de carte de collection
reliée, résout la carte TCGdex depuis son set/numéro et crée la carte (repli minimal avec la
photo de l'article si TCGdex ne répond pas), reprenant le prix d'achat de l'article.

Cible : l'utilisateur admin (``is_admin=1``), sinon ``TARGET_USER_EMAIL``.
Toujours lancer ``--dry-run`` d'abord.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from config import get_settings
from models.article import Article
from models.collection_card import CollectionCard
from models.user import User
from services import collection_article_sync_service


def _resolve_user(db: Session) -> User | None:
    """Utilisateur cible : celui de ``TARGET_USER_EMAIL``, sinon l'admin unique."""
    email = os.environ.get("TARGET_USER_EMAIL")
    if email:
        return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    admins = db.query(User).filter(User.is_admin.is_(True)).all()
    return admins[0] if len(admins) == 1 else None


def main() -> None:
    """Point d'entrée : crée les cartes de collection manquantes pour les articles en vente."""
    parser = argparse.ArgumentParser(description="Backfill « Ma Collection » depuis les articles en vente.")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le plan sans rien écrire.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DANGER : supprime d'abord les cartes déjà reliées à un article, puis les recrée "
        "(à n'utiliser que si aucune carte de collection n'a été reliée à la main).",
    )
    args = parser.parse_args()

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

        if args.reset:
            linked = (
                db.query(CollectionCard)
                .filter(CollectionCard.user_id == user.id, CollectionCard.article_id.is_not(None))
                .all()
            )
            print(f"[RESET] {len(linked)} carte(s) reliée(s) à un article seront supprimées puis recréées.")
            if not args.dry_run:
                for card in linked:
                    db.delete(card)
                db.commit()

        articles = (
            db.query(Article)
            .filter(Article.user_id == user.id, Article.is_sold.is_(False))
            .order_by(Article.id.asc())
            .all()
        )
        linked_article_ids = {
            row[0]
            for row in db.query(CollectionCard.article_id)
            .filter(CollectionCard.user_id == user.id, CollectionCard.article_id.is_not(None))
            .all()
        }
        pending = [a for a in articles if a.id not in linked_article_ids]
        print(f"Articles en vente : {len(articles)} · déjà dans la collection : {len(linked_article_ids)}")
        print(f"--- À créer : {len(pending)} ---")
        for a in pending:
            print(f"  #{a.id} {a.title} · {a.set_code or '—'} {a.card_number or '—'} · achat {float(a.purchase_price):.2f} €")

        if args.dry_run:
            print("\n[DRY-RUN] aucune écriture.")
            return

        created = 0
        for a in pending:
            card = collection_article_sync_service.ensure_collection_card_for_article(db, a)
            if card is not None:
                created += 1
                print(f"  créé : carte #{card.id} ({card.display_name}) ← article #{a.id}")
        print(f"\nCréés : {created} / {len(pending)}.")


if __name__ == "__main__":
    main()
