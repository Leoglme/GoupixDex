"""
Bootstrap base vide : exécute les seeders uniquement si les tables concernées sont vides.

- ``users`` vide → ``user_seeder.py`` (nécessite ``SEED_USER_EMAIL`` / ``SEED_USER_PASSWORD``)
- ``margin_settings`` vide (et au moins un utilisateur) → ``margin_seeder.py``
- ``articles`` vide + variable d’environnement ``SEED_DEV_ARTICLES`` truthy → ``article_seeder.py``

À lancer depuis le dossier ``api/`` (CI / VPS après déploiement, ou en local)::

    python seeders/conditional_seed.py

Voir aussi ``run_all.py`` pour forcer tous les seeders sans condition.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SEEDERS_DIR = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ROOT / ".env")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _run_sub(name: str) -> None:
    script = _SEEDERS_DIR / name
    print(f"\n{'=' * 60}\n  conditional_seed → {name}\n{'=' * 60}\n")
    r = subprocess.run([sys.executable, str(script)], cwd=_ROOT)
    if r.returncode != 0:
        print(f"\nStopped: {name} exited with code {r.returncode}.", file=sys.stderr)
        raise SystemExit(r.returncode)


def _table_counts() -> tuple[int, int, int]:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from sqlalchemy.orm import Session

    from core.database import SessionLocal
    from models.article import Article
    from models.margin_settings import MarginSettings
    from models.user import User

    db: Session = SessionLocal()
    try:
        n_users = db.query(User).count()
        n_margins = db.query(MarginSettings).count()
        n_articles = db.query(Article).count()
        return n_users, n_margins, n_articles
    finally:
        db.close()


def main() -> None:
    _load_dotenv()

    n_users, n_margins, n_articles = _table_counts()
    print(
        f"[conditional_seed] counts: users={n_users}, margin_settings={n_margins}, articles={n_articles}",
    )

    if n_users == 0:
        print("[conditional_seed] table users vide → user_seeder")
        _run_sub("user_seeder.py")
        n_users, n_margins, n_articles = _table_counts()
        print(f"[conditional_seed] après user: users={n_users}, margins={n_margins}, articles={n_articles}")

    if n_margins == 0 and n_users > 0:
        print("[conditional_seed] table margin_settings vide → margin_seeder")
        _run_sub("margin_seeder.py")
        n_users, n_margins, n_articles = _table_counts()
        print(f"[conditional_seed] après margin: users={n_users}, margins={n_margins}, articles={n_articles}")

    if n_articles == 0 and n_users > 0 and _env_truthy("SEED_DEV_ARTICLES"):
        print("[conditional_seed] table articles vide + SEED_DEV_ARTICLES → article_seeder")
        _run_sub("article_seeder.py")
    elif n_articles == 0 and _env_truthy("SEED_DEV_ARTICLES") and n_users == 0:
        print(
            "[conditional_seed] articles vides mais aucun utilisateur — "
            "article_seeder ignoré (exécutez user_seeder d’abord).",
            file=sys.stderr,
        )
    elif n_articles == 0:
        print(
            "[conditional_seed] table articles vide — article_seeder ignoré "
            "(définissez SEED_DEV_ARTICLES=1 pour insérer les cartes de dev).",
        )

    print("\n[conditional_seed] terminé.\n")


if __name__ == "__main__":
    main()
