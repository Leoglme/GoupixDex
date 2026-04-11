"""Async delays shared across automation steps."""

import asyncio


class TimerService:
    """Small utility for millisecond-based waits (matches prior TS behaviour)."""

    @staticmethod
    async def wait(milliseconds: int) -> None:
        """
        Pause execution for the given duration.

        Args:
            milliseconds: Sleep duration in milliseconds.

        Returns:
            None
        """
        await asyncio.sleep(milliseconds / 1000.0)
