"""Start the API with reload and a nodriver-friendly asyncio loop (Windows)."""

from __future__ import annotations

import os
import sys

import uvicorn

from core.nodriver_uvicorn_loop import UVICORN_WINDOWS_NODRIVER_LOOP
from core.win32_asyncio import ensure_proactor_event_loop

if __name__ == "__main__":
    # Before uvicorn sets up the loop (otherwise main:app is not imported yet).
    ensure_proactor_event_loop()
    loop = UVICORN_WINDOWS_NODRIVER_LOOP if sys.platform == "win32" else "auto"
    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
        loop=loop,
    )
