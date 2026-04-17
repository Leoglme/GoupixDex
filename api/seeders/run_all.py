"""Force-run all seeders (user → margin → dev articles).

For an already populated database, prefer ``conditional_seed.py`` (CI / first deploy),
which runs each script only when the target table is empty (articles: optional
``SEED_DEV_ARTICLES``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SEEDERS_DIR = Path(__file__).resolve().parent

_SCRIPTS: tuple[str, ...] = (
    "user_seeder.py",
    "margin_seeder.py",
    "article_seeder.py",
)


def main() -> None:
    for name in _SCRIPTS:
        script_path = _SEEDERS_DIR / name
        print(f"\n{'=' * 60}\n  {name}\n{'=' * 60}\n")
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=_ROOT,
        )
        if result.returncode != 0:
            print(f"\nStopped: {name} exited with code {result.returncode}.", file=sys.stderr)
            raise SystemExit(result.returncode)

    print(f"\n{'=' * 60}\n  All seeders finished successfully.\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
