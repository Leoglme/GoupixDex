"""Windows: Proactor event-loop policy (useful outside uvicorn). With ``uvicorn --reload``, prefer
``python run_dev.py`` or ``--loop core.nodriver_uvicorn_loop:...`` (see README).
"""

from __future__ import annotations

import asyncio
import sys


def ensure_proactor_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
