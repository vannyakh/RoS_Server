"""Solo BR fill settings for MatchSession (RO-110).

Loads gateway-local proposed defaults (1 human, N bots, warmup seconds).
Does not create entities, invent Mercury opcodes, or claim original matchmaking.
RO-069 (bots module) consumes ``session.solo_fill.bot_count``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SOLO_FILL_PATH = DATA_DIR / "solo_fill.json"

# Proposed first-playable defaults — unverified against original RoS.
_BUILTIN = {
    "human_count": 1,
    "bot_count": 9,
    "warmup_seconds": 30.0,
    "bot_scale_targets": [29, 59, 119],
    "map_id": None,
    "mode_id": None,
    "remaining_issues": [
        "map_id for Solo BR selection is unknown until researched",
        "mode_id / lobby teamType for Solo matchmaking is unknown until researched",
    ],
}


def _coerce_optional_id(value):
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ("", "null", "none", "unknown"):
        return None
    return int(value)


class SoloFillConfig:
    """Immutable view of Solo fill settings attached to a MatchSession."""

    __slots__ = (
        "human_count",
        "bot_count",
        "warmup_seconds",
        "bot_scale_targets",
        "map_id",
        "mode_id",
        "remaining_issues",
        "source_path",
    )

    def __init__(
        self,
        *,
        human_count,
        bot_count,
        warmup_seconds,
        bot_scale_targets,
        map_id,
        mode_id,
        remaining_issues,
        source_path=None,
    ):
        self.human_count = int(human_count)
        self.bot_count = int(bot_count)
        self.warmup_seconds = float(warmup_seconds)
        self.bot_scale_targets = [int(n) for n in bot_scale_targets]
        self.map_id = map_id
        self.mode_id = mode_id
        self.remaining_issues = list(remaining_issues)
        self.source_path = source_path

    @property
    def alive_num(self):
        """Gateway convention: humans + bots for space aliveNum (see BOT_ENTITIES.md)."""
        return self.human_count + self.bot_count

    def as_dict(self):
        return {
            "human_count": self.human_count,
            "bot_count": self.bot_count,
            "warmup_seconds": self.warmup_seconds,
            "bot_scale_targets": list(self.bot_scale_targets),
            "map_id": self.map_id,
            "mode_id": self.mode_id,
            "remaining_issues": list(self.remaining_issues),
            "alive_num": self.alive_num,
        }


def load_solo_fill(path=None):
    """Load Solo fill JSON. Missing file falls back to built-in proposed defaults."""
    root = Path(path) if path is not None else DEFAULT_SOLO_FILL_PATH
    data = dict(_BUILTIN)
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in (
            "human_count",
            "bot_count",
            "warmup_seconds",
            "bot_scale_targets",
            "map_id",
            "mode_id",
            "remaining_issues",
        ):
            if key in raw:
                data[key] = raw[key]
    if "SOLO_BOT_COUNT" in os.environ:
        data["bot_count"] = int(os.environ["SOLO_BOT_COUNT"])
    if "SOLO_HUMAN_COUNT" in os.environ:
        data["human_count"] = int(os.environ["SOLO_HUMAN_COUNT"])
    if "SOLO_WARMUP_SECONDS" in os.environ:
        data["warmup_seconds"] = float(os.environ["SOLO_WARMUP_SECONDS"])
    return SoloFillConfig(
        human_count=data["human_count"],
        bot_count=data["bot_count"],
        warmup_seconds=data["warmup_seconds"],
        bot_scale_targets=data["bot_scale_targets"],
        map_id=_coerce_optional_id(data.get("map_id")),
        mode_id=_coerce_optional_id(data.get("mode_id")),
        remaining_issues=data.get("remaining_issues") or [],
        source_path=str(root) if root.is_file() else None,
    )


class SoloFillModule:
    """Attaches fill settings to MatchSession; sends no wire bytes."""

    def __init__(self, session, *, data_path=None):
        self.session = session
        self.config = load_solo_fill(data_path)

    def attach(self):
        if self.session.closed:
            return self
        self.session.solo_fill = self.config
        self.session._log(
            "      [BATTLE] solo_fill human=%s bots=%s warmup=%.1fs alive_num=%s map_id=%s mode_id=%s"
            % (
                self.config.human_count,
                self.config.bot_count,
                self.config.warmup_seconds,
                self.config.alive_num,
                self.config.map_id,
                self.config.mode_id,
            )
        )
        return self


def register(session):
    """MatchSession module entry point (GATEWAY_BATTLE_SESSION.md)."""
    mod = SoloFillModule(session)
    mod.attach()
    return mod
