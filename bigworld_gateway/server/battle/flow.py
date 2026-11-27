"""One match, one stage controller.

A MatchSession owns one MatchFlow. Stages follow the original game's order:

    waiting -> aircraft -> parachute -> ground -> results -> lobby

- waiting / aircraft follow the shared MatchTimeline (warmup / boarding phases).
- parachute starts when the player leaves the plane (Jump button or force-drop, jump.py).
- ground starts on landing (jump.py); loot, combat and the safe zone run during ground.
- results starts when the match ends for this player (results.end_match).
- lobby starts when the player is sent back to the lobby (results return / Quit).

Stages only move forward; asking for the current or an earlier stage is ignored and returns
False, so a late timeline callback cannot pull a landed player back into the plane. Modules
listen with ``flow.on_enter(stage, callback)`` instead of keeping their own timers.

The flow also keeps the per-match counters the results stage reports: start/land/end times,
kills, damage dealt and received, and the number of slots (human + bots) for placement.
"""
from __future__ import annotations

import time

STAGES = ("waiting", "aircraft", "parachute", "ground", "results", "lobby")
# MatchTimeline phase -> stage it starts (flight and play keep the stage the player is in).
PHASE_STAGE = {"warmup": "waiting", "boarding": "aircraft"}


class MatchFlow:
    def __init__(self, session, *, clock=None):
        self.session = session
        self._clock = clock
        self.stage = None
        self.history = []                     # [(stage, at, reason)]
        self._listeners = {name: [] for name in STAGES}
        self.humans = 1
        self.bots = 0
        self.kills = 0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.started_at = None
        self.jumped_at = None
        self.landed_at = None
        self.ended_at = None
        self.placement = None
        self.victory = False

    # ---- time -----------------------------------------------------------------------------

    def now(self):
        if self._clock is not None:
            return float(self._clock.time())
        session_now = getattr(self.session, "_now", None)
        return float(session_now()) if callable(session_now) else time.monotonic()

    # ---- stages ---------------------------------------------------------------------------

    def on_enter(self, stage, callback):
        """Call ``callback(stage)`` when ``stage`` starts (once per match)."""
        if stage not in STAGES:
            raise KeyError("unknown stage %r; expected one of %s" % (stage, STAGES))
        self._listeners[stage].append(callback)

    def reached(self, stage):
        """True once the flow is at ``stage`` or later."""
        return self.stage is not None and STAGES.index(self.stage) >= STAGES.index(stage)

    def enter(self, stage, reason=""):
        """Move forward to ``stage``. Returns False for an unknown, current or earlier stage."""
        if stage not in STAGES:
            raise KeyError("unknown stage %r" % (stage,))
        if self.stage is not None and STAGES.index(stage) <= STAGES.index(self.stage):
            return False
        at = self.now()
        self.stage = stage
        self.history.append((stage, at, reason))
        if stage == "waiting":
            self.started_at = at
        elif stage == "parachute":
            self.jumped_at = at
        elif stage == "ground":
            self.landed_at = at
        elif stage == "results":
            self.ended_at = at
        log = getattr(self.session, "_log", print)
        log("      [FLOW] stage -> %s%s" % (stage, " (%s)" % reason if reason else ""))
        for callback in list(self._listeners[stage]):
            try:
                callback(stage)
            except Exception as e:      # one listener must not stop the others
                log("      [FLOW] %s listener failed: %r" % (stage, e))
        return True

    def attach_timeline(self, timeline):
        """Drive the time-based stages from the session's MatchTimeline phases."""
        for phase, stage in PHASE_STAGE.items():
            timeline.on_phase(phase, lambda _phase, s=stage, p=phase: self.enter(s, "timeline:" + p))

    # ---- counters -------------------------------------------------------------------------

    @property
    def slots(self):
        return max(1, int(self.humans) + int(self.bots))

    def set_slots(self, *, humans=None, bots=None):
        if humans is not None:
            self.humans = max(1, int(humans))
        if bots is not None:
            self.bots = max(0, int(bots))

    def add_kill(self, n=1):
        self.kills += int(n)

    def add_damage(self, *, dealt=0, taken=0):
        self.damage_dealt += max(0, int(dealt))
        self.damage_taken += max(0, int(taken))

    def survival_seconds(self):
        if self.started_at is None:
            return 0.0
        end = self.ended_at if self.ended_at is not None else self.now()
        return max(0.0, end - self.started_at)

    def summary(self):
        """Counters for the results stage and the RoS_Server match record."""
        return {
            "stage": self.stage,
            "placement": self.placement,
            "victory": self.victory,
            "slots": self.slots,
            "kills": self.kills,
            "damage_dealt": self.damage_dealt,
            "damage_taken": self.damage_taken,
            "survival_seconds": round(self.survival_seconds(), 1),
            "stages": [s for s, _at, _r in self.history],
        }
