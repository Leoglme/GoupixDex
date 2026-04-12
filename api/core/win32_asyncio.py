"""Windows: politique Proactor (utile hors uvicorn). Avec ``uvicorn --reload``, préférer
``python run_dev.py`` ou ``--loop core.nodriver_uvicorn_loop:loop_factory`` (voir README).
"""

from __future__ import annotations

import asyncio
import sys


def ensure_proactor_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
