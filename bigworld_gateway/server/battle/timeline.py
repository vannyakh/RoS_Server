"""Named match phases for the gateway battle MatchSession.

Phase lengths are gateway parameters from environment or battle/data/timeline.json.
They are not original Rules of Survival timings. app/game/rules.py (countdown 3s,
drop 8s) is only a reference for the separate JSON simulator.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PHASES = ("warmup", "boarding", "flight", "play")

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_TIMELINE_PATH = DATA_DIR / "timeline.json"

# Env overrides (seconds). Unset -> fall back to data/timeline.json.
_ENV_KEYS = {
    "warmup": "BATTLE_PHASE_WARMUP",
    "boarding": "BATTLE_PHASE_BOARDING",
    "flight": "BATTLE_PHASE_FLIGHT",
    "play": "BATTLE_PHASE_PLAY",
}

# Legacy alias: BATTLE_PREPARE was the old ros_server countdown length.
_LEGACY_WARMUP_ENV = "BATTLE_PREPARE"

_DEFAULTS = {
    "warmup": 3.0,
    "boarding": 2.0,
    "flight": 8.0,
    "play": 0.0,
}


def load_phase_durations(path=None):
    """Return {phase: seconds} from JSON data file, with environment overrides."""
    root = Path(path) if path is not None else DEFAULT_TIMELINE_PATH
    durations = dict(_DEFAULTS)
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for name in PHASES:
            if name in raw:
                durations[name] = float(raw[name])
    for name, env_key in _ENV_KEYS.items():
        if env_key in os.environ:
            durations[name] = float(os.environ[env_key])
    # Prefer explicit BATTLE_PHASE_WARMUP; else allow legacy BATTLE_PREPARE.
    if "BATTLE_PHASE_WARMUP" not in os.environ and _LEGACY_WARMUP_ENV in os.environ:
        durations["warmup"] = float(os.environ[_LEGACY_WARMUP_ENV])
    return {name: float(durations[name]) for name in PHASES}


class MatchTimeline:
    """Drive named phases on a MatchSession clock (real or FakeClock).

    ``start(session)`` schedules phase-enter callbacks via ``session.schedule``.
    Tests advance a FakeClock to step phases without sleeping.
    """

    def __init__(self, durations=None, *, data_path=None):
        self.durations = dict(durations) if durations is not None else load_phase_durations(data_path)
        for name in PHASES:
            self.durations.setdefault(name, float(_DEFAULTS[name]))
        self.phase = None
        self._callbacks = {name: [] for name in PHASES}
        self._started = False
        self._finished = False

    def on_phase(self, name, callback):
        """Register ``callback(phase_name)`` to run when ``name`` begins."""
        if name not in PHASES:
            raise KeyError("unknown phase %r; expected one of %s" % (name, PHASES))
        self._callbacks[name].append(callback)

    def phase_offset(self, name):
        """Seconds from timeline start until ``name`` begins."""
        if name not in PHASES:
            raise KeyError(name)
        total = 0.0
        for p in PHASES:
            if p == name:
                return total
            total += float(self.durations[p])
        return total

    def total_duration(self):
        return sum(float(self.durations[p]) for p in PHASES)

    def start(self, session):
        """Schedule all phase entries on ``session``. Idempotent."""
        if self._started or getattr(session, "closed", False):
            return
        self._started = True
        for name in PHASES:
            delay = self.phase_offset(name)
            session.schedule(delay, self._enter, name)

    def _enter(self, name):
        self.phase = name
        if name == PHASES[-1] and float(self.durations[name]) <= 0.0:
            self._finished = True
        for cb in list(self._callbacks.get(name, ())):
            cb(name)
        # Zero-length trailing play still marks finished after enter.
        if name == PHASES[-1]:
            self._finished = True

    @property
    def finished(self):
        return self._finished
