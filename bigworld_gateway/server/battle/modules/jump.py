"""Jump, parachute, glider and landing (RO-063).

Answers BattleGroundAvatar exposed requests ``requestGetOffPlane``,
``chooseParachute`` and ``chooseGlider`` (decoded via ``battle.requests``,
RO-060) only while the Plane module reports ``inJumpArea``. Players still on
the plane when the jump window ends are force-dropped.

Leave-plane / land replies use evidenced RO-059 property updates and
``forcedPosition`` (0x59) from ``LOBBY_FINDINGS`` / ``battle_flow.FLIGHT_STEPS``.
``playerGetOffPlane`` / ``onForceLeavePlane`` live on BattleGroundSpace
**CellMethods** (not ClientMethods, not Exposed), so this module does not
emit invented S2C opcodes for them.

Drop point: the plane's position when the player leaves (LOBBY_FINDINGS update 25,
``battle_flow.Match.release_from_plane``). After the jump the fall follows the client's own
position reports (``battle/position_sync.py`` -> ``session.player.position``, the msg-3 xyz that
``battle_flow.Match.on_position`` reads):

- fall phases stepped by height as fractions of the drop from the jump point to FLIGHT_GROUND
  (``battle_flow.Match._parachute_phase``, update 23): 2 % BEFORE_OPEN_PARACHUTE (skydive HUD),
  CHUTE_BUTTON 0.6 CAN_OPEN_PARACHUTE (parachute button), CHUTE_AUTO 0.95 PARACHUTE_OPENED;
- landing when the reports stop falling after a long fall (``Match.on_position``, updates 22/25):
  fallPhase 0, flightStage 2, battleState Normal, hasLanded 1, no teleport (the client stands on
  the real terrain).

The timed landing (forcedPosition to the evidenced land point) is only the fallback when the
client sends no usable position. Device run 3 (logs/checklist/run3/server.log) showed why: the
first report came 22 s after the drop, at y 19300, and the client then fell for 46 s to y -677,
long after an 8 s timed landing had already declared it on the ground.
"""

from __future__ import annotations

import os
import struct

import battle_flow as bf
from battle import requests as reqs
from battle.timeline import MatchTimeline, load_phase_durations, shared_timeline

# const.FlightStage / FallPhase / PlayerState / GlidePhase (LOBBY_FINDINGS update 15, 21).
FLIGHT_STAGE_FLY = 1
FLIGHT_STAGE_GROUND = 2
FALL_NORMAL = 0
FALL_CAN_FALL = 2
FALL_BEFORE_OPEN = 3
FALL_CAN_OPEN = 4
FALL_PARACHUTE_OPENED = 5
BATTLE_STATE_NORMAL = 0
BATTLE_STATE_PARACHUTE = 4
GLIDE_FREE = 7

# Evidenced drop / land points (LOBBY_FINDINGS updates 15–16, 22), not original balance.
DEFAULT_DROP_POS = tuple(bf.FLIGHT_START)  # (698, 19300, -373): only without a flying plane
DEFAULT_LAND_POS = (698.0, -677.0, -373.0)
DEFAULT_LAND_DELAY = 8.0            # fallback check interval after the jump

FALL_TICK = 0.2                     # s between reads of the client's reported position
FLIGHT_GROUND = -677.0              # measured terrain under FLIGHT_START (update 23)
LAND_MIN_FALL = 1000.0              # Match.on_position: a long fall first ...
LAND_STILL_SECS = 1.0               # ... then no vertical movement for this long
LAND_STILL_DY = 0.5
# Fallback limits (gateway parameters, sized from device run 3: 22 s without reports + 46 s fall).
NO_REPORT_LAND = 90.0               # no position report at all since the jump
REPORT_STALE = 10.0                 # reports stopped after they started
LAND_MAX = 300.0                    # hard cap after the jump

JUMP_METHODS = frozenset(
    {"requestGetOffPlane", "chooseParachute", "chooseGlider"}
)

# Match PlaneModule jump-window fractions when scheduling force-drop.
_JUMP_END_FRAC = 0.75


def _env_float(key, default):
    if key in os.environ:
        return float(os.environ[key])
    return float(default)


def _env_vec3(key, default):
    raw = os.environ.get(key)
    if not raw:
        return tuple(float(v) for v in default)
    parts = [float(v) for v in raw.split(",")]
    if len(parts) != 3:
        return tuple(float(v) for v in default)
    return tuple(parts)


def forced_position(x, y, z, *, eid=None, space_id=1, vehicle_id=0):
    """ClientInterface 0x59 fixed-36 forcedPosition (same layout as battle_flow tp)."""
    if eid is None:
        eid = bf.AVATAR_ID
    return bytes([bf.MSG_FORCED_POSITION]) + struct.pack(
        "<III3f3f",
        int(eid),
        int(space_id),
        int(vehicle_id),
        float(x),
        float(y),
        float(z),
        0.0,
        0.0,
        0.0,
    )


class JumpModule:
    """Owns get-off-plane / parachute / glider / fall / land for one MatchSession."""

    def __init__(self, session, *, timeline=None, own_timeline=None):
        self.session = session
        self.avatar_id = bf.AVATAR_ID
        self.drop_pos = _env_vec3("JUMP_DROP_POS", DEFAULT_DROP_POS)
        self.land_pos = _env_vec3("JUMP_LAND_POS", DEFAULT_LAND_POS)
        self.land_delay = _env_float("JUMP_LAND_DELAY", DEFAULT_LAND_DELAY)
        self.jump_end_frac = _env_float("PLANE_JUMP_END_FRAC", _JUMP_END_FRAC)
        self.ground_y = _env_float("FLIGHT_GROUND", FLIGHT_GROUND)
        self.no_report_land = _env_float("JUMP_NO_REPORT_LAND", NO_REPORT_LAND)
        self.report_stale = _env_float("JUMP_REPORT_STALE", REPORT_STALE)
        self.land_max = _env_float("JUMP_LAND_MAX", LAND_MAX)
        self.off_plane = False
        self.landed = False
        self.landed_by = None           # "position" | "fallback"
        self.choice = None  # None | "parachute" | "glider"
        self.force_dropped = False
        self.jump_point = None
        self.jumped_at = None
        self.fall_phase = None
        self.fall_started = False
        self.chute_open = False
        self.reports = 0                # position reports seen since the jump
        self._land_job = None
        self._report_obj = None
        self._last_y = None
        self._last_report_at = None
        self._max_y = None
        self._still_since = None
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            shared = shared_timeline(session, "space_module", "plane_module")
            if shared is not None:
                self.timeline = shared
                self._owns_timeline = False if own_timeline is None else bool(own_timeline)
            else:
                self.timeline = MatchTimeline(load_phase_durations())
                self._owns_timeline = True if own_timeline is None else bool(own_timeline)

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_jump_request, self._on_jump_request)
        self.session.on_inbound(self._is_fall_request, self._on_fall_request)
        self.timeline.on_phase("flight", self._on_flight)
        self.timeline.on_phase("play", self._on_play)
        if self._owns_timeline:
            self.timeline.start(self.session)
        self.session.jump_module = self
        self.session._log("      [BATTLE] jump module started")

    # ---- phase / window -------------------------------------------------------------

    def plane_in_jump_area(self):
        """True while the Plane module reports inJumpArea (jump window)."""
        if self.session.closed:
            return False
        plane = getattr(self.session, "plane_module", None)
        if plane is None:
            return False
        return bool(getattr(plane, "in_jump_area", False))

    def in_jump_window(self):
        """Legal phase for the three jump requests: Plane.inJumpArea is on."""
        return self.plane_in_jump_area()

    def _on_flight(self, _phase):
        if self.session.closed:
            return
        flight_dur = float(self.timeline.durations.get("flight", 0.0))
        if flight_dur <= 0.0:
            self.session.schedule(0.0, self._force_drop_if_needed)
            return
        end = max(0.0, min(1.0, self.jump_end_frac)) * flight_dur
        # Slightly after Plane clears inJumpArea so voluntary jumps in-window win.
        self.session.schedule(end + 0.01, self._force_drop_if_needed)

    def _on_play(self, _phase):
        self._force_drop_if_needed()

    def _force_drop_if_needed(self):
        if self.session.closed or self.off_plane:
            return
        self.force_dropped = True
        self.session._log("      [BATTLE] jump force-drop (end of path / window)")
        self._leave_plane(reason="force")

    # ---- inbound --------------------------------------------------------------------

    def _is_jump_request(self, msgid, payload):
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return call is not None and call.method in JUMP_METHODS

    def _on_jump_request(self, msgid, payload):
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        if call is None or call.method not in JUMP_METHODS:
            return b""
        # AC1: answer only while the plane is in the jump window.
        if not self.in_jump_window():
            self.session._log(
                "      [BATTLE] ignore %s outside jump window (off_plane=%s)"
                % (call.method, self.off_plane)
            )
            return b""
        if call.method == "requestGetOffPlane":
            if self.off_plane:
                return b""
            self._leave_plane(reason="request")
        elif call.method == "chooseParachute":
            self._choose_parachute()
        elif call.method == "chooseGlider":
            self._choose_glider()
        return b""

    def _is_fall_request(self, msgid, payload):
        if not self.off_plane or self.landed:
            return False
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"")
        return call is not None and call.method == "changeFallPhase"

    def _on_fall_request(self, msgid, payload):
        """Observe the client's changeFallPhase (its parachute button sends 5, update 23) so the
        server stepping does not override it. Returns None: the legacy path still answers."""
        call = reqs.decode(int(msgid), payload or b"")
        if call is not None and call.args:
            phase = struct.unpack("<b", call.args[:1])[0]
            self.fall_phase = phase
            if phase == FALL_PARACHUTE_OPENED:
                self.chute_open = True
        return None

    # ---- actions --------------------------------------------------------------------

    def _drop_point(self, plane):
        """JUMP_DROP_POS override, else where the plane is now (update 25), else FLIGHT_START."""
        if "JUMP_DROP_POS" not in os.environ and plane is not None:
            current = getattr(plane, "current_position", None)
            pos = current() if callable(current) else None
            if pos is not None:
                return tuple(float(v) for v in pos)
        return tuple(float(v) for v in self.drop_pos)

    def _leave_plane(self, *, reason):
        if self.off_plane or self.session.closed:
            return
        self.off_plane = True
        flow = getattr(self.session, "flow", None)
        if flow is not None:
            flow.enter("parachute", reason)
        plane = getattr(self.session, "plane_module", None)
        x, y, z = self._drop_point(plane)
        self.jump_point = (x, y, z)
        self.jumped_at = self.session._now()
        self.fall_phase = FALL_CAN_FALL
        player = getattr(self.session, "player", None)
        self._report_obj = getattr(player, "position", None)   # only later reports count
        if player is not None:
            from battle import player_entity as pe

            player.lifecycle = pe.LIFECYCLE_PARACHUTE
        self.session.enqueue(
            bf.update_property("BattleGroundAvatar", "planeID", bf.i32(0))
        )
        self.session.enqueue(forced_position(x, y, z, eid=self.avatar_id))
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "fallPhase", bf.i8(FALL_CAN_FALL)
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "battleState",
                bf.i8(BATTLE_STATE_PARACHUTE),
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "flightStage",
                bf.i32(FLIGHT_STAGE_FLY),
            )
        )
        if plane is not None and callable(getattr(plane, "human_left", None)):
            plane.human_left()
        elif plane is not None:
            left = max(0, int(getattr(plane, "left_on_plane", 1)) - 1)
            plane.left_on_plane = left
            self.session.enqueue(
                bf.update_property(
                    "BattleGroundAvatar",
                    "leftPlayerNumOnPlane",
                    bf.i32(left),
                )
            )
        # CellMethods playerGetOffPlane / onForceLeavePlane are not ClientMethods;
        # evidenced client leave path is planeID + forcedPosition + fallPhase above.
        self.session._log(
            "      [BATTLE] jump leave plane reason=%s drop=(%.0f,%.0f,%.0f)"
            % (reason, x, y, z)
        )
        self._schedule_land()
        self.session.schedule(FALL_TICK, self._fall_tick)

    def _choose_parachute(self):
        if not self.off_plane:
            self._leave_plane(reason="parachute")
        self.choice = "parachute"
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "fallPhase",
                bf.i8(FALL_PARACHUTE_OPENED),
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "battleState",
                bf.i8(BATTLE_STATE_PARACHUTE),
            )
        )
        self.session._log("      [BATTLE] jump chooseParachute fallPhase=%s" % FALL_PARACHUTE_OPENED)

    def _choose_glider(self):
        if not self.off_plane:
            self._leave_plane(reason="glider")
        self.choice = "glider"
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "glidePhase", bf.i8(GLIDE_FREE)
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "battleState",
                bf.i8(BATTLE_STATE_PARACHUTE),
            )
        )
        # Evidenced Avatar ClientMethod (bwdefs); not an invented opcode.
        self.session.enqueue(
            bf.client_call(
                "BattleGroundAvatar",
                "onChangeToGliderAppear",
                self.avatar_id,
                b"",
            )
        )
        self.session._log("      [BATTLE] jump chooseGlider glidePhase=%s" % GLIDE_FREE)

    # ---- fall, from the client's position reports -----------------------------------

    def _new_report(self):
        """The latest reported (x, y, z) if a report arrived since the last read, else None.
        position_sync stores a new tuple per report, so identity tells a new report apart."""
        player = getattr(self.session, "player", None)
        pos = getattr(player, "position", None)
        if pos is None or pos is self._report_obj:
            return None
        self._report_obj = pos
        return tuple(float(v) for v in pos)

    def _fall_tick(self):
        if self.landed or self.session.closed:
            return
        pos = self._new_report()
        if pos is not None:
            self.on_fall_position(*pos)
            if self.landed:
                return
        self.session.schedule(FALL_TICK, self._fall_tick)

    def on_fall_position(self, x, y, z):
        """One client position after the jump: step the fall phase, detect the landing."""
        if self.landed or not self.off_plane or self.jump_point is None:
            return
        now = self.session._now()
        self.reports += 1
        last_y = self._last_y
        self._last_y, self._last_report_at = float(y), now
        jump_y = float(self.jump_point[1])
        drop = max(jump_y - self.ground_y, 1.0)
        done = (jump_y - y) / drop                  # 0 at the jump point, 1 on FLIGHT_GROUND
        # Reports sent before the forcedPosition arrives carry the old position (update 23):
        # start once a report is near the jump height.
        if not self.fall_started:
            if done > 0.05:
                return
            self.fall_started = True
            self._max_y = float(y)
            self.session._log("      [BATTLE] jump: fall started at y %.0f" % y)
            return
        self._max_y = max(self._max_y, float(y))
        self._step_fall_phase(done, y)
        if self._max_y - y < _env_float("LAND_MIN_FALL", LAND_MIN_FALL):
            return
        if last_y is None or abs(y - last_y) > LAND_STILL_DY:
            self._still_since = None
            return
        if self._still_since is None:
            self._still_since = now
        if now - self._still_since + 1e-9 < _env_float("LAND_STILL_SECS", LAND_STILL_SECS):
            return
        self._land_at((x, y, z), by="position")

    def _step_fall_phase(self, done, y):
        """battle_flow.Match._parachute_phase (LOBBY_FINDINGS update 23)."""
        if self.chute_open:
            return
        phase = self.fall_phase if self.fall_phase is not None else FALL_CAN_FALL
        new = phase
        if phase < FALL_BEFORE_OPEN and done >= 0.02:
            new = FALL_BEFORE_OPEN
        elif os.environ.get("CHUTE_MODE", "server") == "client":
            pass                     # the client's own height check opens it (07.10)
        elif phase == FALL_BEFORE_OPEN and done >= _env_float("CHUTE_BUTTON", 0.6):
            new = FALL_CAN_OPEN
        # fallPhase 5 from the server only changes the HUD icon; the canopy needs the client's
        # button (update 23). Late fallback only.
        elif phase == FALL_CAN_OPEN and done >= _env_float("CHUTE_AUTO", 0.95):
            new = FALL_PARACHUTE_OPENED
            self.chute_open = True
        if new == phase:
            return
        self.fall_phase = new
        self.session._log("      [BATTLE] fall %.0f%% (y %.0f) -> fallPhase %d" % (done * 100, y, new))
        self.session.enqueue(
            bf.update_property("BattleGroundAvatar", "fallPhase", bf.i8(new))
        )

    def client_falling(self):
        """True while recent reports show the player still in the air after the jump."""
        if self._last_report_at is None:
            return False
        if self.session._now() - self._last_report_at >= self.report_stale:
            return False
        return self._still_since is None

    def _land_at(self, pos, *, by):
        """Landing at the client's reported position (Match.on_position): no teleport."""
        if self.landed or self.session.closed:
            return
        if self._landed_elsewhere():
            return
        self.landed = True
        self.landed_by = by
        for name, value in (
            ("fallPhase", bf.i8(FALL_NORMAL)),
            ("flightStage", bf.i32(FLIGHT_STAGE_GROUND)),
            ("battleState", bf.i8(BATTLE_STATE_NORMAL)),
            ("hasLanded", bf.i8(1)),
        ):
            self.session.enqueue(bf.update_property("BattleGroundAvatar", name, value))
        player = getattr(self.session, "player", None)
        if player is not None:
            from battle import player_entity as pe

            player.lifecycle = pe.LIFECYCLE_GROUND
        # After the landing bodies, so the ground stage's zone updates (FIGHT, circles) follow them.
        flow = getattr(self.session, "flow", None)
        if flow is not None:
            flow.enter("ground", "landed")
        self.session._log(
            "      [BATTLE] jump landed (client position, %s) at (%.0f, %.0f, %.0f) -> fallPhase 0 flightStage 2"
            % ((by,) + tuple(float(v) for v in pos))
        )

    def _landed_elsewhere(self):
        """The flow is already at ground (e.g. the legacy height landing in ros_server landed the
        player): stop here without sending a second landing or teleport."""
        flow = getattr(self.session, "flow", None)
        reached = getattr(flow, "reached", None)
        if not callable(reached) or not reached("ground"):
            return False
        self.landed = True
        self.landed_by = "flow"
        self.session._log("      [BATTLE] jump: already on the ground (flow stage %s), no landing sent" % flow.stage)
        return True

    # ---- fallback landing -----------------------------------------------------------

    def _schedule_land(self):
        if self.landed or self.session.closed:
            return
        delay = max(0.0, float(self.land_delay))
        self._land_job = self.session.schedule(delay, self._fallback_check)

    def _fallback_check(self):
        """Timed landing, only when the client's reports cannot land the player."""
        if self.landed or self.session.closed:
            return
        now = self.session._now()
        since = now - (self.jumped_at if self.jumped_at is not None else now)
        if since + 1e-9 >= self.land_max:
            self._land(force=True)
            return
        if self._last_report_at is None:
            if since + 1e-9 >= self.no_report_land:
                self.session._log(
                    "      [BATTLE] jump: no position report %.0fs after the jump" % since
                )
                self._land(force=True)
                return
        elif now - self._last_report_at + 1e-9 >= self.report_stale:
            # Reports stopped (an idle client sends none): it stays where it last was.
            player = getattr(self.session, "player", None)
            self._land_at(getattr(player, "position", self.land_pos), by="fallback")
            return
        self._schedule_land()

    def _land(self, force=False):
        """Timed landing: forcedPosition to the evidenced land point. Also the MatchFlow parachute
        recovery path, which is refused while the client's reports show it still falling."""
        if self.landed or self.session.closed:
            return
        if not force and self.client_falling():
            self.session._log(
                "      [BATTLE] jump: timed landing skipped, client still falling (y %.0f)" % self._last_y
            )
            return
        if self._landed_elsewhere():
            return
        self.landed = True
        self.landed_by = "fallback"
        x, y, z = self.land_pos
        self.session.enqueue(forced_position(x, y, z, eid=self.avatar_id))
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "fallPhase", bf.i8(FALL_NORMAL)
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "flightStage",
                bf.i32(FLIGHT_STAGE_GROUND),
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "battleState",
                bf.i8(BATTLE_STATE_NORMAL),
            )
        )
        player = getattr(self.session, "player", None)
        if player is not None:
            player.sync_position(x, y, z)
            from battle import player_entity as pe

            player.lifecycle = pe.LIFECYCLE_GROUND
        # After the landing bodies, so the ground stage's zone updates (FIGHT, circles) follow them.
        flow = getattr(self.session, "flow", None)
        if flow is not None:
            flow.enter("ground", "landed")
        self.session._log(
            "      [BATTLE] jump landed (timed fallback) at (%.0f, %.0f, %.0f) -> fallPhase 0 flightStage 2"
            % (x, y, z)
        )


def register(session):
    """MatchSession module entry point (GATEWAY_BATTLE_SESSION.md).

    Deferred so plane.py / space.py can own the shared MatchTimeline first.
    """
    mod = JumpModule(session)
    session.schedule(0.0, _deferred_start, mod)
    return mod


def _deferred_start(mod):
    if mod.session.closed:
        return
    space = getattr(mod.session, "space_module", None)
    plane = getattr(mod.session, "plane_module", None)
    shared = None
    if space is not None:
        shared = getattr(space, "timeline", None)
    if shared is None and plane is not None:
        shared = getattr(plane, "timeline", None)
    if shared is not None and mod._owns_timeline:
        mod.timeline = shared
        mod._owns_timeline = False
    mod.start()
