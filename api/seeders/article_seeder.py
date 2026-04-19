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


class _ArticleSeed(TypedDict, total=False):
    title: str
    description: str
    pokemon_name: str | None
    set_code: str | None
    card_number: str | None
    condition: str
    purchase_price: Decimal
    sell_price: Decimal | None
    sold_price: Decimal | None
    sale_source: str | None
    is_sold: bool
    sold_at: dt.datetime | None
    published_on_vinted: bool
    published_on_ebay: bool
    images: list[str]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ROOT / ".env")


def _specs() -> list[tuple[str, str, str]]:
    """(pokemon, set_code, card_number) — long list for pagination / dashboard tests."""
    return [
        ("Pikachu", "SV8", "025/162"),
        ("Mewtwo", "M1L", "131/086"),
        ("Herbizarre", "M1L", "065/063"),
        ("Évoli", "SV-P", "040"),
        ("Dracaufeu", "SV3", "125/198"),
        ("Tortank", "SV3", "184/198"),
        ("Florizarre", "SV3", "003/198"),
        ("Lucario", "SV4", "078/182"),
        ("Amphinobi", "SV2", "054/198"),
        ("Garchomp", "SV4", "096/182"),
        ("Tyranocif", "SV4", "066/182"),
        ("Métalosse", "SV4", "112/182"),
        ("Zacian", "SSH", "138/202"),
        ("Zamazenta", "SSH", "139/202"),
        ("Éthernatos", "SV4", "141/182"),
        ("Palkia", "SV5", "204/191"),
        ("Dialga", "SV5", "205/191"),
        ("Rayquaza", "SV6", "029/167"),
        ("Latias", "SV6", "073/167"),
        ("Latios", "SV6", "074/167"),
        ("Mew", "SV4", "053/182"),
        ("Celebi", "SV4", "004/182"),
        ("Ho-Oh", "SV4", "144/182"),
        ("Lugia", "SV4", "145/182"),
        ("Kyogre", "SV5", "032/191"),
        ("Groudon", "SV5", "033/191"),
        ("Giratina", "SV5", "130/191"),
        ("Arceus", "SV5", "166/191"),
        ("Darkrai", "SV5", "077/191"),
        ("Genesect", "SV5", "181/191"),
        ("Volcanion", "SV6", "136/167"),
        ("Magearna", "SV6", "131/167"),
        ("Marshadow", "SV6", "080/167"),
        ("Zeraora", "SV6", "152/167"),
        ("Évoli V", "SWSH", "065/203"),
        ("Évoli VMAX", "SWSH", "066/203"),
        ("Pikachu V", "SWSH", "043/172"),
        ("Pikachu VMAX", "SWSH", "044/172"),
        ("Raichu", "SV1", "026/198"),
        ("Raichu Alola", "SV1", "027/198"),
        ("Mimiqui", "SV2", "097/198"),
        ("Boréas", "SV3", "144/198"),
        ("Fulguris", "SV3", "145/198"),
        ("Démétéros", "SV3", "146/198"),
        ("Kyurem", "SV3", "047/198"),
        ("Reshiram", "SV3", "048/198"),
        ("Zekrom", "SV3", "049/198"),
        ("Nymphali", "SV8", "075/162"),
        ("Aquali", "SV8", "076/162"),
        ("Pyroli", "SV8", "077/162"),
        ("Voltali", "SV8", "078/162"),
        ("Phyllali", "SV8", "079/162"),
        ("Givrali", "SV8", "080/162"),
        ("Noctali", "SV8", "081/162"),
        ("Mentali", "SV8", "082/162"),
        ("Dimoret", "SV8", "083/162"),
        ("Nigosier", "SV8", "084/162"),
        ("Couverdure", "SV8", "085/162"),
        ("Motisma", "SV8", "086/162"),
        ("Motisma", "SV8", "087/162"),
        ("Motisma", "SV8", "088/162"),
    ]


def _build_samples(now: dt.datetime) -> list[_ArticleSeed]:
    specs = _specs()
    out: list[_ArticleSeed] = []
    for i, (pokemon, set_code, card_number) in enumerate(specs):
        n = i + 1
        purchase = Decimal("2.00") + Decimal(i % 17) * Decimal("1.25")
        sell = (purchase * Decimal("1.35")).quantize(Decimal("0.01"))
        # Mix: many sold vs in-stock; varied marketplace flags
        sold = i % 5 != 0 and i % 7 != 1
        vinted_pub = not sold and (i % 3 == 0 or i % 11 == 2)
        ebay_pub = not sold and (i % 4 == 1) and (i % 6 != 0)

        sold_at: dt.datetime | None = None
        sold_price: Decimal | None = None
        sale_src: str | None = None
        if sold:
            sold_at = now - dt.timedelta(days=(i % 90) + 1)
            sale_src = "ebay" if i % 3 == 0 else "vinted"
            # Realized price sometimes slightly below listed price
            sold_price = (sell - Decimal("0.50")) if i % 5 == 0 else sell

        seed_url = f"https://picsum.photos/seed/goupix-dev-{n}/400/560"
        imgs: list[str] = [] if i % 9 == 0 else [seed_url]
        if i % 13 == 0:
            imgs = [seed_url, f"https://picsum.photos/seed/goupix-dev-{n}b/400/560"]

        row: _ArticleSeed = {
            "title": f"{_DEV_PREFIX}{pokemon} — {set_code} {card_number}",
            "description": f"Seed dev #{n}\nSérie {set_code}\nÉtat Near Mint",
            "pokemon_name": pokemon,
            "set_code": set_code,
            "card_number": card_number,
            "condition": "Near Mint",
            "purchase_price": purchase,
            "sell_price": None if sold and i % 8 == 3 else sell,
            "sold_price": sold_price,
            "sale_source": sale_src,
            "is_sold": sold,
            "sold_at": sold_at,
            "published_on_vinted": vinted_pub,
            "published_on_ebay": ebay_pub,
            "images": imgs,
        }
        out.append(row)

    return out


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
        samples = _build_samples(now)

        for s in samples:
            imgs = s.get("images") or []
            article = Article(
                user_id=user.id,
                title=s["title"],
                description=s["description"],
                pokemon_name=s.get("pokemon_name"),
                set_code=s.get("set_code"),
                card_number=s.get("card_number"),
                condition=s.get("condition") or "Near Mint",
                purchase_price=s["purchase_price"],
                sell_price=s.get("sell_price"),
                sold_price=s.get("sold_price"),
                sale_source=s.get("sale_source"),
                is_sold=bool(s.get("is_sold")),
                sold_at=s.get("sold_at"),
                published_on_vinted=bool(s.get("published_on_vinted")),
                published_on_ebay=bool(s.get("published_on_ebay")),
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
