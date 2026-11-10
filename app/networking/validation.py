"""Per-connection message limits and sequence checks."""

from time import monotonic

MAX_MESSAGE_BYTES = 4096


class SequenceTracker:
    def __init__(self) -> None:
        self.last = -1

    def accept(self, sequence: int) -> bool:
        if sequence <= self.last:
            return False
        self.last = sequence
        return True


class RateLimiter:
    def __init__(self, limit: int = 20, window: float = 1.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: list[float] = []

    def allow(self) -> bool:
        now = monotonic()
        self._hits = [stamp for stamp in self._hits if now - stamp < self.window]
        if len(self._hits) >= self.limit:
            return False
        self._hits.append(now)
        return True
