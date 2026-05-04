"""Windows: Proactor event-loop policy (useful outside uvicorn). With hot reload, use
``python run_dev.py`` (sets the policy before ``uvicorn.run``) and ``loop="asyncio"`` (see
``core.nodriver_uvicorn_loop``).
"""

from __future__ import annotations

import asyncio
import sys


def ensure_proactor_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
