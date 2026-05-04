"""
Dedicated asyncio loop: nodriver requires the Browser to be created and used
on the same event loop (no repeated asyncio.run() from the FastAPI thread).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


class DedicatedAsyncLoop:
    """Singleton: one thread + event loop for all nodriver work."""

    _instance: DedicatedAsyncLoop | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    @classmethod
    def instance(cls) -> DedicatedAsyncLoop:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance._start_thread()
            return cls._instance

    def _start_thread(self) -> None:
        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True, name="nodriver-async-loop")
        self._thread.start()
        if not self._ready.wait(timeout=20):
            raise RuntimeError("Timeout starting nodriver asyncio loop")

    def run(self, coro: Coroutine[Any, Any, T], timeout: float = 600) -> T:
        if self._loop is None:
            raise RuntimeError("Loop not initialized")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def run_sync(self, fn: Callable[[], T], timeout: float = 120) -> T:
        """Run a synchronous function on the loop thread (e.g. browser.stop())."""
        if self._loop is None:
            raise RuntimeError("Loop not initialized")
        out: concurrent.futures.Future[T] = concurrent.futures.Future()

        def wrapper() -> None:
            try:
                out.set_result(fn())
            except Exception as e:
                out.set_exception(e)

        self._loop.call_soon_threadsafe(wrapper)
        return out.result(timeout=timeout)
