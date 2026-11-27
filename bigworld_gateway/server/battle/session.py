"""Lobby START handoff and in-match MatchSession seam.

HallMatchSession owns Athlete START -> matchBattleGround -> delayed _enter_battle.
MatchSession is the per-address in-match seam: entity ids, ordered sends, timeline
callbacks, inbound dispatch, and auto-loaded battle/modules register(session) hooks.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import struct
import sys
import time
import traceback
from pathlib import Path

import account_link
import athlete_requests
from battle import player_entity
from battle.flow import MatchFlow
from battle.timeline import MatchTimeline, load_phase_durations

HALL_TEAM_MAP_GROUP = 1   # const.DtsMapBaseType.MAP_4K (client default, map 700)

HALL_START_SEQUENCE = (
    "getOpenMaintenanceFightTipFlag",
    "createHallTeam",
    "getReadyForBattleGround",
    "changeOccupation",
    "reqPayedPartnerRel",
    "matchBattleGround",
)

_CANCEL_START = ("notReadyForBattleGround", "cancelMatchBattleGround")

# Gateway-local entity id ranges (not original-server ids). Env overrides for experiments.
SPACE_ENTITY_ID = int(os.environ.get("SPACE_ENTITY_ID", "20001"))
PLANE_ENTITY_ID = int(os.environ.get("PLANE_ENTITY_ID", "20002"))
PROP_ID_BASE = int(os.environ.get("PROP_ENTITY_ID_BASE", "30000"))
BOT_ID_BASE = int(os.environ.get("BOT_ENTITY_ID_BASE", "40000"))

DEFAULT_MODULES_DIR = Path(__file__).resolve().parent / "modules"


class HallMatchSession:
    """Athlete base calls from the hall START button through matchBattleGround."""

    def __init__(self, gate):
        self._gate = gate

    def handle(self, name, rd, addr, *, athlete_method, py, hall_team_member):
        """Return reply bytes, or None if this module does not own the method."""
        if name == "getOpenMaintenanceFightTipFlag":
            return athlete_method("onGetOpenMaintenanceFightTipFlag", b"\x00" + struct.pack("<i", 0))

        if name == "createHallTeam":
            mode = rd.i32()
            self._gate._team[addr] = mode
            gid = account_link.current_gid()
            members = struct.pack("<I", 1) + hall_team_member(addr)
            print(f"      [BASEAPP] createHallTeam mode={mode} -> onEnterHallTeam (solo, leader {gid})")
            return athlete_method(
                "onEnterHallTeam",
                struct.pack("<iQb", mode, gid, 1) + members
                + struct.pack("<i", HALL_TEAM_MAP_GROUP) + b"\x00\x00",
            )

        if name == "getReadyForBattleGround":
            gid = account_link.current_gid()
            print(f"      [BASEAPP] getReadyForBattleGround -> ready + MATCHING")
            now = int(athlete_requests.game_now())
            return (
                athlete_method("syncReadyState", struct.pack("<QBB", gid, 1, 0))
                + athlete_method("syncMatchState", struct.pack("<hqB", 1, now, 0) + py(None))
                + athlete_method("syncMatchingProgress", struct.pack("<iif", 1, 100, 0.0))
            )

        if name == "changeOccupation":
            # Lobby START often sends a single BOOL/INT8; .def may list INT32. Only unpack
            # when a full INT32 is present so a 1-byte payload does not raise and abort.
            if rd.i + 4 <= len(rd.b):
                rd.i32()
            elif rd.i < len(rd.b):
                rd.i8()
            return b""

        if name == "reqPayedPartnerRel":
            return b""

        if name == "matchBattleGround":
            if rd.i < len(rd.b):
                rd.i8()
            print(f"      [BASEAPP] matchBattleGround -> ENTERING")
            bf = self._gate._last_bf.get(addr)
            if bf is not None:
                self._gate._handoff_bf[addr] = bytes(bf)
            if os.environ.get("BATTLE_ENTER", "on") == "on":
                asyncio.get_event_loop().call_later(
                    float(os.environ.get("BATTLE_DELAY", "3")),
                    self._gate._enter_battle,
                    addr,
                )
            now = int(athlete_requests.game_now())
            return athlete_method("syncMatchState", struct.pack("<hqB", 2, now, 0) + py(None))

        if name in _CANCEL_START:
            gid = account_link.current_gid()
            print(f"      [BASEAPP] {name} -> not ready + NONE")
            return (
                athlete_method("syncReadyState", struct.pack("<QBB", gid, 0, 0))
                + athlete_method("syncMatchState", struct.pack("<hqB", 0, 0, 0) + py(None))
            )

        return None


class FakeClock:
    """Deterministic clock + call_later queue for MatchSession timeline tests."""

    def __init__(self, start=0.0):
        self.now = float(start)
        self._jobs = []  # (when, seq, callback, args, kwargs)
        self._seq = 0

    def time(self):
        return self.now

    def call_later(self, delay, callback, *args, **kwargs):
        when = self.now + float(delay)
        self._seq += 1
        job = (when, self._seq, callback, args, kwargs)
        self._jobs.append(job)
        self._jobs.sort(key=lambda j: (j[0], j[1]))
        return job

    def cancel(self, job):
        try:
            self._jobs.remove(job)
        except ValueError:
            pass

    def advance(self, dt):
        """Move time forward and run due callbacks in order."""
        target = self.now + float(dt)
        while self._jobs and self._jobs[0][0] <= target + 1e-12:
            when, _seq, callback, args, kwargs = self._jobs.pop(0)
            self.now = when
            callback(*args, **kwargs)
        self.now = target


class MatchSession:
    """Per-client in-match seam. Match state is gateway-local (no FastAPI package imports).

    Modules under battle/modules/ expose ``register(session)`` and may call
    ``session.on_inbound``, ``session.enqueue``, ``session.schedule``, and the
    id allocators. When no module is loaded, hooks are no-ops and ros_server
    keeps the existing battle_flow / trigger_battle.txt path.
    """

    def __init__(self, addr, send_fn, *, clock=None, scheduler=None, log=print):
        self.addr = addr
        self._send_fn = send_fn
        self._log = log
        self._clock = clock
        self._scheduler = scheduler
        self._queue = []
        self._draining = False
        self._inbound = []  # list of (predicate_or_name, handler)
        self._timers = []
        self.modules = []
        self.space_id = SPACE_ENTITY_ID
        self.plane_id = PLANE_ENTITY_ID
        self._next_prop = PROP_ID_BASE
        self._next_bot = BOT_ID_BASE
        self.closed = False
        self.player = player_entity.new_human_player()
        self.combatants = {self.player.player_id: self.player}
        # One clock and one stage controller per match. Modules attach to these instead of
        # building their own timelines; load_battle_modules starts the timeline once.
        self.timeline = MatchTimeline(load_phase_durations())
        self.flow = MatchFlow(self)
        self.flow.attach_timeline(self.timeline)
        # The match clock starts when the client is in the world (first non-origin position report,
        # LOBBY_FINDINGS "Auto timeline"), not when the modules load: entities sent during the map
        # loading screen were never seen and the whole match ran before the player arrived.
        self.client_ready = False
        self._t0 = self._now()
        self._close_hooks = []      # module cleanups (leaveAoI of their entities), newest first      # battle entry: BigWorld.serverTime 1.0 (setGameTime, ros_server)

    # ---- entity ids -----------------------------------------------------------------

    def alloc_space_id(self):
        """Fixed BattleGroundSpace id (default 20001)."""
        return self.space_id

    def alloc_plane_id(self):
        """Fixed Plane id (default 20002)."""
        return self.plane_id

    def alloc_prop_id(self):
        """Next DtsProp entity id (default base 30000)."""
        eid = self._next_prop
        self._next_prop += 1
        return eid

    def alloc_bot_id(self):
        """Next Robot / bot entity id (default base 40000)."""
        eid = self._next_bot
        self._next_bot += 1
        return eid

    # ---- ordered send queue ---------------------------------------------------------

    def enqueue(self, body):
        """Queue bytes for ordered delivery through the gate send function."""
        if body is None or self.closed:
            return
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError("enqueue expects bytes")
        self._queue.append(bytes(body))
        self.flush()

    def flush(self):
        """Send queued bodies in FIFO order. Re-entrant safe."""
        if self._draining or self.closed:
            return
        self._draining = True
        try:
            while self._queue:
                body = self._queue.pop(0)
                try:
                    self._send_fn(body)
                except Exception as e:
                    self._log(f"      [BATTLE SESSION] send failed: {e!r}")
        finally:
            self._draining = False

    # ---- timeline -------------------------------------------------------------------

    def _now(self):
        if self._clock is not None:
            return float(self._clock.time())
        return time.monotonic()

    def schedule(self, delay, callback, *args, **kwargs):
        """Run callback after delay seconds on the session scheduler / asyncio loop."""
        if self.closed:
            return None

        def _safe():
            if self.closed:
                return
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self._log(f"      [BATTLE SESSION] timeline callback failed: {e!r}")
                self._log(traceback.format_exc())

        delay = float(delay)
        if self._scheduler is not None:
            handle = self._scheduler.call_later(delay, _safe)
        elif self._clock is not None and hasattr(self._clock, "call_later"):
            handle = self._clock.call_later(delay, _safe)
        else:
            handle = asyncio.get_event_loop().call_later(delay, _safe)
        self._timers.append(handle)
        return handle

    # ---- inbound dispatch -----------------------------------------------------------

    def on_inbound(self, name_or_msgid, handler):
        """Register an in-battle handler.

        ``name_or_msgid`` may be a method name string, an integer msgid, or a
        callable predicate ``(msgid, payload) -> bool``. Handler signature:
        ``handler(msgid, payload) -> bytes | None``. Returning None means
        "not handled" so ros_server can fall through to battle_flow.
        """
        self._inbound.append((name_or_msgid, handler))

    def dispatch_inbound(self, msgid, payload, *, method_name=None):
        """Run the first matching module handler. Return bytes, empty bytes, or None.

        None = no module handled the message (caller keeps legacy path).
        bytes (including b'') = module handled it; do not also run battle_flow.
        """
        if self.closed:
            return None
        if not self.client_ready and 0x80 <= msgid <= 0xBF:
            self._start_on_avatar_request(msgid, payload)
        for key, handler in list(self._inbound):
            matched = False
            if callable(key) and not isinstance(key, type):
                try:
                    matched = bool(key(msgid, payload))
                except Exception as e:
                    self._log(f"      [BATTLE SESSION] inbound predicate failed: {e!r}")
                    continue
            elif isinstance(key, int):
                matched = key == msgid
            elif isinstance(key, str):
                matched = method_name is not None and key == method_name
            if not matched:
                continue
            try:
                result = handler(msgid, payload)
            except Exception as e:
                self._log(f"      [BATTLE SESSION] inbound handler failed: {e!r}")
                self._log(traceback.format_exc())
                return b""
            if result is None:      # not handled: let the next matching handler try
                continue
            return result
        return None

    def server_time(self):
        """BigWorld.serverTime the client sees now: 1.0 + seconds since battle entry (the gateway's
        setGameTime keepalive uses the same origin, ros_server._battle_t0)."""
        return 1.0 + (self._now() - self._t0)

    # ---- match start ----------------------------------------------------------------

    def on_client_position(self, x, y, z):
        """Client position report (msg 3). The first one away from the origin starts the match."""
        if self.client_ready or self.closed:
            return False
        if abs(float(x)) < 1.0 and abs(float(y)) < 1.0 and abs(float(z)) < 1.0:
            return False
        if "position" not in os.environ.get("MATCH_START_ON", "avatar,position"):
            return False
        return self.start_match("client in world (%.0f, %.0f, %.0f)" % (x, y, z))

    def _start_on_avatar_request(self, msgid, payload):
        """The client's first BattleGroundAvatar cell request means its avatar is in the world.
        Measured on LDPlayer 2026-11-27: 6 s after battle entry the client sends
        onRecvClientFrameLevel, getOnTrain, then onRecvClientFPS every second (render-loop stats),
        while an idle player sends no position report at all."""
        try:
            import battle_flow

            req = battle_flow.decode_request(msgid, payload)
        except Exception:
            return False
        if req is None or req[1] != "BattleGroundAvatar" or req[0] not in (0, battle_flow.AVATAR_ID):
            return False
        seen = self.__dict__.setdefault("_pre_start_requests", set())
        if req[2] not in seen:              # evidence: what the client sends while it loads
            seen.add(req[2])
            self._log("      [BATTLE SESSION] pre-start client request: %s" % req[2])
        if "avatar" not in os.environ.get("MATCH_START_ON", "avatar,position"):
            return False
        return self.start_match("client in world: %s" % req[2])

    def start_timeout(self, limit):
        if self.client_ready or self.closed:
            return
        record = {"stage": "loading", "expected": "client avatar request or position report",
                  "elapsed": limit, "human_ready": False, "bots_ready": False,
                  "pending_messages": len(self._queue), "reason": "no start signal",
                  "recovery": "start match"}
        self.flow.timeouts.append(record)
        self._log("      [FLOW] TIMEOUT %s" % " ".join("%s=%s" % (k, v) for k, v in record.items()))
        self.start_match("start timeout after %.0fs" % limit)

    def start_match(self, reason="start"):
        """Start the match timeline once (waiting stage first). Returns True on the first call."""
        if self.client_ready or self.closed:
            return False
        self.client_ready = True
        self._log("      [BATTLE SESSION] match start: %s" % reason)
        self.timeline.start(self)
        return True

    # ---- lifecycle ------------------------------------------------------------------

    def on_close(self, callback):
        """Run ``callback()`` once when the session closes, before its queue is dropped (modules send
        leaveAoI for their entities here). Replaces wrapping ``session.close``, which let a later
        module drop an earlier module's cleanup and could make a wrapper call itself."""
        if callback not in self._close_hooks:
            self._close_hooks.append(callback)

    def close(self):
        if self.closed:
            return
        for callback in reversed(list(self._close_hooks)):
            try:
                callback()
            except Exception as e:
                self._log(f"      [BATTLE SESSION] close hook failed: {e!r}")
        self._close_hooks.clear()
        self.closed = True
        self._queue.clear()
        self._inbound.clear()
        for handle in self._timers:
            cancel = getattr(handle, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception:
                    pass
            elif self._clock is not None and hasattr(self._clock, "cancel"):
                try:
                    self._clock.cancel(handle)
                except Exception:
                    pass
        self._timers.clear()
        self.modules.clear()


def load_battle_modules(session, modules_dir=None, *, log=print):
    """Import ``*.py`` from battle/modules/ and call ``register(session)``.

    Missing directory = no modules (legacy path only). A module that raises
    during import or register is logged; the session continues.
    """
    root = Path(modules_dir) if modules_dir is not None else DEFAULT_MODULES_DIR
    if not root.is_dir():
        return []
    loaded = []
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"battle.modules.{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                log(f"      [BATTLE SESSION] skip module {path.name}: no loader")
                continue
            module = importlib.util.module_from_spec(spec)
            # Register before executing: @dataclass (results.py) looks its module up in sys.modules,
            # and without this the module failed to import, so results never loaded live.
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if register is None:
                log(f"      [BATTLE SESSION] skip module {path.name}: no register()")
                continue
            register(session)
            session.modules.append(module)
            loaded.append(module)
            log(f"      [BATTLE SESSION] loaded module {path.name}")
        except Exception as e:
            log(f"      [BATTLE SESSION] module {path.name} failed: {e!r}")
            log(traceback.format_exc())
    # MATCH_START=immediate starts the timeline now (tests, debugging); the default waits for the
    # client's first position report (MatchSession.on_client_position).
    if loaded and os.environ.get("MATCH_START", "client") == "immediate" and hasattr(session, "start_match"):
        session.start_match("MATCH_START=immediate")
    elif loaded and hasattr(session, "start_match"):
        # No start signal at all (no avatar request, no position report): record why and start anyway
        # so the match is not stuck forever before the waiting stage (QA 2026-11-27).
        limit = float(os.environ.get("MATCH_START_TIMEOUT", "120"))
        session.schedule(limit, session.start_timeout, limit)
    return loaded
