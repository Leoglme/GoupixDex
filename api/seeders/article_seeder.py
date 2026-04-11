"""Insert fake articles for local dev (idempotent via [DEV] title prefix)."""

from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DEV_PREFIX = "[DEV] "


class _ArticleSeed(TypedDict):
    title: str
    description: str
    pokemon_name: str | None
    set_code: str | None
    card_number: str | None
    condition: str
    purchase_price: Decimal
    sell_price: Decimal | None
    is_sold: bool
    sold_at: dt.datetime | None
    images: list[str]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ROOT / ".env")


def main() -> None:
    _load_dotenv()

    email = (
        os.environ.get("SEED_ARTICLE_USER_EMAIL", "").strip()
        or os.environ.get("SEED_USER_EMAIL", "").strip()
    )
    if not email:
        print(
            "Set SEED_ARTICLE_USER_EMAIL or SEED_USER_EMAIL to the target account email.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from sqlalchemy.orm import Session

    from core.database import SessionLocal
    from models.article import Article
    from models.image import Image
    from models.user import User

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user is None:
            print(f"No user with email {email!r}. Run seeders/user_seeder.py first.", file=sys.stderr)
            raise SystemExit(1)

        removed = (
            db.query(Article)
            .filter(Article.user_id == user.id, Article.title.like(f"{_DEV_PREFIX}%"))
            .delete(synchronize_session=False)
        )
        if removed:
            print(f"Removed {removed} previous dev article(s).")

        now = dt.datetime.now(dt.UTC)
        samples: list[_ArticleSeed] = [
            {
                "title": f"{_DEV_PREFIX}Pikachu — Couronne Stellaire SV8 025/162 NM",
                "description": "Langue : Japonais\nSérie : Couronne Stellaire\nÉtat : Near Mint\nCarte de test seed.",
                "pokemon_name": "Pikachu",
                "set_code": "SV8",
                "card_number": "025/162",
                "condition": "Near Mint",
                "purchase_price": Decimal("3.50"),
                "sell_price": None,
                "is_sold": False,
                "sold_at": None,
                "images": ["/uploads/dev/seed-pikachu-front.jpg"],
            },
            {
                "title": f"{_DEV_PREFIX}Mewtwo ex — M1L 131/086",
                "description": "Exemple listing FR / test données.\nNuméro : 131/086\nÉtat : Near Mint",
                "pokemon_name": "Mewtwo",
                "set_code": "M1L",
                "card_number": "131/086",
                "condition": "Near Mint",
                "purchase_price": Decimal("12.00"),
                "sell_price": Decimal("22.90"),
                "is_sold": True,
                "sold_at": now,
                "images": [
                    "/uploads/dev/seed-mewtwo-1.jpg",
                    "/uploads/dev/seed-mewtwo-2.jpg",
                ],
            },
            {
                "title": f"{_DEV_PREFIX}Herbizarre AR — Mega Brave 065/063",
                "description": "Langue : Japonais\nNom : Herbizarre / Ivysaur\nNuméro : 065/063 AR",
                "pokemon_name": "Herbizarre",
                "set_code": "M1L",
                "card_number": "065/063",
                "condition": "Near Mint",
                "purchase_price": Decimal("8.25"),
                "sell_price": None,
                "is_sold": False,
                "sold_at": None,
                "images": [],
            },
            {
                "title": f"{_DEV_PREFIX}Évoli promo — SV-P 040",
                "description": "Carte promo seed.\nÉtat : Near Mint",
                "pokemon_name": "Évoli",
                "set_code": "SV-P",
                "card_number": "040",
                "condition": "Near Mint",
                "purchase_price": Decimal("1.00"),
                "sell_price": None,
                "is_sold": False,
                "sold_at": None,
                "images": ["/uploads/dev/seed-eevee.jpg"],
            },
        ]

        for s in samples:
            imgs = s["images"]
            article = Article(
                user_id=user.id,
                title=s["title"],
                description=s["description"],
                pokemon_name=s["pokemon_name"],
                set_code=s["set_code"],
                card_number=s["card_number"],
                condition=s["condition"],
                purchase_price=s["purchase_price"],
                sell_price=s["sell_price"],
                is_sold=s["is_sold"],
                sold_at=s["sold_at"],
            )
            db.add(article)
            db.flush()
            for url in imgs:
                db.add(Image(article_id=article.id, image_url=url))

        db.commit()
        print(f"Seeded {len(samples)} dev articles for {user.email} (user_id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
