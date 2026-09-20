"""Dry-run Leboncoin publish (opens Chrome, stops at login or form fill)."""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.win32_asyncio import ensure_proactor_event_loop
from models.article import Article
from services.leboncoin_publish_service import publish_article_to_leboncoin

ensure_proactor_event_loop()


async def main() -> None:
    a = Article()
    a.id = 99999
    a.title = "Carte Pokémon Dracaufeu Near Mint"
    a.description = "Carte Pokémon en excellent état, envoi soigné sous sleeve."
    a.purchase_price = Decimal("5")
    a.sell_price = Decimal("12")

    # Use a tiny public image URL for materialize test (or skip if no network)
    sources = [
        "https://aapjpybdkzqtgxavjjem.supabase.co/storage/v1/object/public/GoupixDex/1/12/9ddc3e6cc6f249d3bcd66d12ea8d936b.jpg",
    ]

    logs: list[str] = []

    async def progress(ev: dict) -> None:
        msg = ev.get("message") or ev.get("type")
        logs.append(str(msg))
        print("[progress]", msg)

    result = await publish_article_to_leboncoin(
        a,
        sources,
        postal_code="35000",
        progress=progress,
    )
    print("RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())
