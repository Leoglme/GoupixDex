"""Open Leboncoin login in Chrome (manual sign-in). Run: python scripts/test_leboncoin_open_login.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.win32_asyncio import ensure_proactor_event_loop
from services.leboncoin_service import LeboncoinService

ensure_proactor_event_loop()


async def main() -> None:
    r = await LeboncoinService.open_login_browser()
    print("Opened:", r)
    print("Sign in in the Chrome window, then press Ctrl+C here when done.")
    try:
        while True:
            await asyncio.sleep(5)
            tab = LeboncoinService._tab
            if tab is None:
                break
            ok = not await LeboncoinService._page_shows_login_gate(tab)
            print("logged_in_probe:", ok)
            if ok:
                print("Session OK — you can close Chrome and run publish.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        LeboncoinService.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
