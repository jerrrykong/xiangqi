"""Game Service v2.0 - Room Timers

Manages thinking time and move timeout using asyncio.
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MoveTimer:
    """Asyncio-based move timer for a room.

    Tracks remaining time for each player and handles timeout.
    """

    def __init__(self, initial_time: int = 600, increment: int = 10,
                 on_timeout: Optional[Callable] = None):
        self._initial_time = initial_time
        self._increment = increment
        self._on_timeout = on_timeout

        self._red_remaining: float = float(initial_time)
        self._black_remaining: float = float(initial_time)
        self._current_side: str = "red"
        self._timer_task: Optional[asyncio.Task] = None
        self._last_tick: Optional[float] = None
        self._running = False

    @property
    def red_remaining(self) -> int:
        return max(0, int(self._red_remaining))

    @property
    def black_remaining(self) -> int:
        return max(0, int(self._black_remaining))

    def start(self, current_side: str = "red") -> None:
        """Start the timer for the given side."""
        self._current_side = current_side
        self._running = True
        self._last_tick = asyncio.get_event_loop().time()
        self._schedule_tick()

    def switch_side(self) -> None:
        """Switch to the other side's timer. Add increment to the side that just moved."""
        if not self._running:
            return

        # Add increment to the side that just moved
        if self._current_side == "red":
            self._red_remaining += self._increment
            self._current_side = "black"
        else:
            self._black_remaining += self._increment
            self._current_side = "red"

        self._last_tick = asyncio.get_event_loop().time()

    def stop(self) -> None:
        """Stop the timer."""
        self._running = False
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = None

    def get_current_remaining(self) -> int:
        """Get remaining time for the current side."""
        if self._current_side == "red":
            return self.red_remaining
        return self.black_remaining

    def _schedule_tick(self) -> None:
        """Schedule a timer tick."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        """Tick loop that decrements remaining time."""
        try:
            while self._running:
                await asyncio.sleep(0.1)  # 100ms tick interval

                if not self._running:
                    break

                now = asyncio.get_event_loop().time()
                if self._last_tick is not None:
                    elapsed = now - self._last_tick
                    self._last_tick = now

                    if self._current_side == "red":
                        self._red_remaining -= elapsed
                        if self._red_remaining <= 0:
                            self._red_remaining = 0
                            self._running = False
                            if self._on_timeout:
                                await self._on_timeout("red")
                            return
                    else:
                        self._black_remaining -= elapsed
                        if self._black_remaining <= 0:
                            self._black_remaining = 0
                            self._running = False
                            if self._on_timeout:
                                await self._on_timeout("black")
                            return

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Timer error: {e}", exc_info=True)
