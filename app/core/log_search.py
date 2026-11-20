"""Search logs/server.log by time range, level, text and kind without loading the whole file.

Lines look like `2026-11-20 00:00:38,063 INFO ros.function {...}`; the time is the server's local
clock. Lines without that prefix (tracebacks) belong to the entry above them. The file is
read backwards in blocks, newest first, and reading stops once entries are older than `start`
or `limit` entries matched, so a recent, narrow search reads little of a large file.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HEADER = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) ([A-Z]+) (\S+) ?(.*)$")
BLOCK = 256 * 1024
REQUEST_KEYS = ("function_id", "function_name", "feature", "status", "duration_ms", "error_code", "error_message", "request_id", "player_id", "match_id")


@dataclass
class Entry:
    at: datetime
    millis: int
    level: str
    logger: str
    message: str
    extra: list[str] = field(default_factory=list)

    def view(self) -> dict:
        payload = {
            "at": f"{self.at:%Y-%m-%d %H:%M:%S}.{self.millis:03d}",
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "extra": self.extra,
            "request": None,
        }
        if self.logger == "ros.function" and self.message.startswith("{"):
            try:
                data = json.loads(self.message)
            except ValueError:
                data = None
            if isinstance(data, dict):
                payload["request"] = {key: data.get(key) for key in REQUEST_KEYS}
        return payload

    def text(self) -> str:
        return " ".join([self.level, self.logger, self.message, *self.extra]).lower()


def _reverse_lines(path: Path):
    """Lines from the end of the file to the start."""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        tail = b""
        while position > 0:
            size = min(BLOCK, position)
            position -= size
            handle.seek(position)
            chunk = handle.read(size) + tail
            lines = chunk.split(b"\n")
            tail = lines[0]
            for line in reversed(lines[1:]):
                yield line.decode("utf-8", errors="replace").rstrip("\r")
        if tail:
            yield tail.decode("utf-8", errors="replace").rstrip("\r")


def _reverse_entries(path: Path):
    """Entries newest first, each with its continuation lines in order."""
    pending: list[str] = []
    for line in _reverse_lines(path):
        match = HEADER.match(line)
        if not match:
            if line:
                pending.append(line)
            continue
        stamp, millis, level, logger, message = match.groups()
        try:
            at = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pending.append(line)
            continue
        yield Entry(at=at, millis=int(millis), level=level, logger=logger, message=message, extra=list(reversed(pending))[:40])
        pending = []


def search(
    path: Path,
    *,
    start: datetime | None,
    end: datetime | None,
    levels: set[str] | None,
    text: str | None,
    kind: str | None,
    limit: int,
) -> dict:
    if not path.is_file():
        return {"entries": [], "counts": {}, "truncated": False, "oldest": None, "newest": None}
    needle = (text or "").strip().lower()
    matched: list[Entry] = []
    counts: Counter[str] = Counter()
    truncated = False
    for entry in _reverse_entries(path):
        if start is not None and entry.at < start:
            break
        if end is not None and entry.at > end:
            continue
        if kind == "request" and entry.logger != "ros.function":
            continue
        if kind == "app" and entry.logger == "ros.function":
            continue
        if needle and needle not in entry.text():
            continue
        counts[entry.level] += 1
        if levels and entry.level not in levels:
            continue
        if len(matched) >= limit:
            truncated = True
            break
        matched.append(entry)
    matched.reverse()
    return {
        "entries": [entry.view() for entry in matched],
        "counts": dict(counts),
        "truncated": truncated,
        "oldest": matched[0].view()["at"] if matched else None,
        "newest": matched[-1].view()["at"] if matched else None,
    }
