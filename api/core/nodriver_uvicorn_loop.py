"""Asyncio event loop for uvicorn + nodriver on Windows.

With ``--reload``, uvicorn may pick ``SelectorEventLoop``, which is incompatible with
``create_subprocess_exec`` (Chrome / nodriver).

For a **custom** ``--loop``, uvicorn imports **one** object and passes it to
``asyncio.Runner``: it must be the **loop class** (e.g. ``ProactorEventLoop``),
instantiated with no arguments — **not** a factory like
``lambda: ProactorEventLoop()`` (see ``uvicorn.config.Config.get_loop_factory``).

Value to pass to ``uvicorn --loop`` on Windows:
"""

from __future__ import annotations

# Stdlib event-loop class (importable only on Windows).
UVICORN_WINDOWS_NODRIVER_LOOP = "asyncio.windows_events:ProactorEventLoop"
