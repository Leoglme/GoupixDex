"""CLI entry: load ``items.json``, sign in to Vinted (nodriver), list each item."""

import json
import logging
import os

import nodriver as uc

from app_types.payload import ItemPayload
from config import config
from core.win32_asyncio import ensure_proactor_event_loop
from services.os_service import get_project_root
from services.timer_service import TimerService
from services.vinted_service import VintedService

ensure_proactor_event_loop()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _load_dotenv() -> None:
    """Load ``.env`` from project root if ``python-dotenv`` is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = get_project_root()
    load_dotenv(root / ".env")


async def main() -> None:
    """
    Read credentials and items, launch the browser, sign in, then create each listing.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    _load_dotenv()

    root = get_project_root()
    items_path = root / "items.json"
    vinted_items: list[ItemPayload] = json.loads(
        items_path.read_text(encoding="utf-8"),
    )

    email = os.environ.get("VINTED_EMAIL_OR_USERNAME")
    password = os.environ.get("VINTED_PASSWORD")
    if not email or not password:
        logging.error(
            "Vinted credentials are missing. Set VINTED_EMAIL_OR_USERNAME and "
            "VINTED_PASSWORD in the environment or in a .env file at the project root.",
        )
        raise SystemExit(1)

    await VintedService.init_browser()
    await VintedService.init_page()
    await TimerService.wait(400)
    await VintedService.ensure_sign_in(email, password)

    for vinted_item in vinted_items:
        await VintedService.open_sell_item_page()
        await VintedService.wait_for_listing_form()
        await VintedService.fill_item_details(
            vinted_item,
            config["category_path"],
            config["brand"],
            config["package_size"],
        )
        await TimerService.wait(2000)
        # await VintedService.publish()


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
