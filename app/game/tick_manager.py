"""Fixed-timestep scheduler. The callback must stay free of database I/O."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic

from app.observability.metrics import observe_tick

logger = logging.getLogger(__name__)


class TickManager:
    def __init__(self, tick_rate: int, update: Callable[[float], Awaitable[None]]) -> None:
        if not 1 <= tick_rate <= 60:
            raise ValueError("Invalid tick rate")
        self.tick_rate = tick_rate
        self.interval = 1.0 / tick_rate
        self.running = False
        self.tick = 0
        self._update = update

    def stop(self) -> None:
        self.running = False

    async def run(self) -> None:
        self.running = True
        next_tick = monotonic()
        while self.running:
            now = monotonic()
            if now < next_tick:
                await asyncio.sleep(next_tick - now)
            if not self.running:
                break
            started = monotonic()
            await self._update(self.interval)
            self.tick += 1
            elapsed = monotonic() - started
            next_tick += self.interval
            observe_tick(elapsed, elapsed > self.interval)
            if elapsed > self.interval:
                logger.warning("Tick overran the interval by %.4fs", elapsed - self.interval)
                next_tick = monotonic()
