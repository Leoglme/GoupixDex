"""One-shot : aligne « Ma Collection » sur les articles en vente.

1. Crée la carte de collection des articles **non vendus** qui n'en ont pas encore (résolution
   TCGdex depuis set/numéro/noms, repli minimal avec la photo de l'article, prix d'achat repris).
2. Avec ``--repair`` : ré-résout **en place** les cartes déjà reliées restées sans fiche TCGdex ou
   dont la langue contredit leur set (id, classeurs, quantité, notes et prix d'achat conservés).

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
    """Point d'entrée : crée les cartes manquantes, puis (``--repair``) corrige les cartes reliées."""
    parser = argparse.ArgumentParser(description="Aligne « Ma Collection » sur les articles en vente.")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le plan sans rien écrire.")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Ré-résout en place les cartes reliées sans fiche TCGdex ou à la langue incohérente.",
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

        articles = (
            db.query(Article)
            .filter(Article.user_id == user.id, Article.is_sold.is_(False))
            .order_by(Article.id.asc())
            .all()
        )
        cards_by_article = {
            card.article_id: card
            for card in db.query(CollectionCard)
            .filter(CollectionCard.user_id == user.id, CollectionCard.article_id.is_not(None))
            .all()
        }
        pending = [a for a in articles if a.id not in cards_by_article]
        to_repair = (
            [
                (cards_by_article[a.id], a)
                for a in articles
                if a.id in cards_by_article and collection_article_sync_service.needs_refresh(cards_by_article[a.id], a)
            ]
            if args.repair
            else []
        )
        print(f"Articles en vente : {len(articles)} · déjà dans la collection : {len(cards_by_article)}")
        print(f"--- À créer : {len(pending)} ---")
        for a in pending:
            print(f"  #{a.id} {a.title} · {a.set_code or '—'} {a.card_number or '—'} · achat {float(a.purchase_price):.2f} €")
        if args.repair:
            print(f"--- À réparer : {len(to_repair)} ---")
            for card, a in to_repair:
                print(f"  carte #{card.id} {card.display_name} [{card.tcgdex_card_id} · {card.language}] ← article #{a.id}")

        if args.dry_run:
            print("\n[DRY-RUN] aucune écriture.")
            return

        created = 0
        for a in pending:
            card = collection_article_sync_service.ensure_collection_card_for_article(db, a)
            if card is not None:
                created += 1
                print(f"  créé : carte #{card.id} ({card.display_name}) ← article #{a.id}")
        repaired = 0
        for card, a in to_repair:
            changed = collection_article_sync_service.refresh_collection_card_from_article(db, card, a)
            repaired += int(changed)
            state = "réparée" if changed else "inchangée"
            print(f"  {state} : carte #{card.id} → {card.display_name} [{card.tcgdex_card_id} · {card.language}]")
        print(f"\nCréées : {created} / {len(pending)} · Réparées : {repaired} / {len(to_repair)}.")


if __name__ == "__main__":
    main()
