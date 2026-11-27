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

import os
import time

STAGES = ("waiting", "aircraft", "parachute", "ground", "results", "lobby")
# MatchTimeline phase -> stage it starts (flight and play keep the stage the player is in).
PHASE_STAGE = {"warmup": "waiting", "boarding": "aircraft"}
# What ends each stage, for the timeout record.
EXPECT = {
    "waiting": "countdown ends (timeline boarding phase)",
    "aircraft": "player jumps or is force-dropped at the end of the jump window (jump.py)",
    "parachute": "player lands (jump.py timed landing or legacy height landing)",
    "ground": "match ends: death, victory or quit (results.py)",
    "results": "return to the lobby after RESULTS_LOBBY_DELAY (results.py)",
}
# Extra seconds a stage may run past its planned length before it is reported as timed out.
TIMEOUT_GRACE = 15.0


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
        self.bots_ready = False          # server-side bots initialised (bots.py); no client acks
        self.timeouts = []               # recorded timeout dicts

    # ---- time -----------------------------------------------------------------------------

    def now(self):
        if self._clock is not None:
            return float(self._clock.time())
        session_now = getattr(self.session, "_now", None)
        return float(session_now()) if callable(session_now) else time.monotonic()

    # ---- stages ---------------------------------------------------------------------------

    def on_enter(self, stage, callback, *, first=False):
        """Call ``callback(stage)`` when ``stage`` starts (once per match). ``first=True`` runs it
        before the listeners already registered (the space entity must exist before any module
        updates its properties)."""
        if stage not in STAGES:
            raise KeyError("unknown stage %r; expected one of %s" % (stage, STAGES))
        if first:
            self._listeners[stage].insert(0, callback)
        else:
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
        prev_at = self.history[-2][1] if len(self.history) > 1 else at
        log("      [FLOW] stage -> %s%s | after %.1fs | human_ready=%s bots_ready=%s slots=%s"
            % (stage, " (%s)" % reason if reason else "", at - prev_at, self.human_ready(),
               self.bots_ready, self.slots))
        for callback in list(self._listeners[stage]):
            try:
                callback(stage)
            except Exception as e:      # one listener must not stop the others
                log("      [FLOW] %s listener failed: %r" % (stage, e))
        self._watch(stage)
        return True

    # ---- timeouts ---------------------------------------------------------------------------

    def human_ready(self):
        return bool(getattr(self.session, "client_ready", True))

    def stage_limit(self, stage):
        """Planned length of a stage plus TIMEOUT_GRACE, or None for open-ended stages."""
        timeline = getattr(self.session, "timeline", None)
        d = dict(getattr(timeline, "durations", {}) or {})
        planned = {
            "waiting": d.get("warmup", 0.0),
            "aircraft": d.get("boarding", 0.0) + d.get("flight", 0.0),
            # jump.py lands from the client's fall reports; JUMP_LAND_MAX is its hard cap (a real drop
            # from the plane took ~70 s on LDPlayer, so the old 8 s timed landing was not a limit).
            "parachute": float(os.environ.get("JUMP_LAND_MAX", "300")),
            "results": float(os.environ.get("RESULTS_LOBBY_DELAY", "3")),
        }.get(stage)
        return None if planned is None else float(planned) + TIMEOUT_GRACE

    def _watch(self, stage):
        limit = self.stage_limit(stage)
        schedule = getattr(self.session, "schedule", None)
        if limit is None or not callable(schedule):
            return
        schedule(limit, self._check_timeout, stage, self.now())

    def _check_timeout(self, stage, since):
        if self.stage != stage or getattr(self.session, "closed", False):
            return
        queued = len(getattr(self.session, "_queue", []) or [])
        record = {
            "stage": stage, "expected": EXPECT.get(stage, ""), "elapsed": round(self.now() - since, 1),
            "human_ready": self.human_ready(), "bots_ready": self.bots_ready, "pending_messages": queued,
            "reason": "no completion within %.0fs" % (self.stage_limit(stage) or 0.0),
            "recovery": self._recover(stage),
        }
        self.timeouts.append(record)
        log = getattr(self.session, "_log", print)
        log("      [FLOW] TIMEOUT %s" % " ".join("%s=%s" % (k, v) for k, v in record.items()))

    def _recover(self, stage):
        """Finish the stage through its own normal path (never skip it)."""
        s = self.session
        if stage == "aircraft":
            jump = getattr(s, "jump_module", None)
            if jump is not None and hasattr(jump, "_force_drop_if_needed"):
                jump._force_drop_if_needed()
                return "jump force-drop"
        if stage == "parachute":
            jump = getattr(s, "jump_module", None)
            if jump is not None and hasattr(jump, "_land"):
                jump._land()
                return "jump land"
        if stage == "results":
            results = getattr(s, "results_module", None)
            if results is not None and hasattr(results, "_return_to_lobby"):
                results._return_to_lobby()
                return "return to lobby"
        return "none (logged)"

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
