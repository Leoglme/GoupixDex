"""Execute SQL migration files in order (``001_*.sql``, ``002_*.sql``, ...).

Chaque fichier n’est exécuté qu’une fois : le nom du fichier est enregistré dans
``schema_migrations``. Les fichiers SQL doivent rester idempotents lorsque c’est
possible (ex. ``CREATE TABLE IF NOT EXISTS``, ``ADD COLUMN IF NOT EXISTS``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running ``python migrations/run_migrations.py`` puts ``migrations/`` on sys.path, not the app root.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, text

_SCHEMA_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  name VARCHAR(255) NOT NULL PRIMARY KEY,
  applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def _split_statements(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            parts.append("\n".join(buf))
            buf = []
    if buf:
        parts.append("\n".join(buf))
    return parts


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    from config import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url)
    migrations_dir = Path(__file__).resolve().parent
    files = sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        print("No migration files found.", file=sys.stderr)
        raise SystemExit(1)

    with engine.begin() as conn:
        conn.execute(text(_SCHEMA_TABLE_DDL))

    for path in files:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM schema_migrations WHERE name = :n"),
                {"n": path.name},
            ).first()
        if row is not None:
            print(f"Skipped (already applied): {path.name}")
            continue

        sql_text = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for stmt in _split_statements(sql_text):
                stmt = stmt.rstrip()
                if stmt.endswith(";"):
                    stmt = stmt[:-1].strip()
                if not stmt:
                    continue
                conn.execute(text(stmt))
            conn.execute(
                text("INSERT INTO schema_migrations (name) VALUES (:n)"),
                {"n": path.name},
            )
        print(f"Applied: {path.name}")


if __name__ == "__main__":
    main()
