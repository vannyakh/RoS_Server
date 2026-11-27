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

Drop / land coordinates and timers are gateway parameters, not original RoS.
ClientInterface msg 3 position layout stays unknown here — landing is timer-
driven with an evidenced land point, not invented xyz decode.
"""

from __future__ import annotations

import os
import struct

import battle_flow as bf
from battle import requests as reqs
from battle.timeline import MatchTimeline, load_phase_durations

# const.FlightStage / FallPhase / PlayerState / GlidePhase (LOBBY_FINDINGS update 15).
FLIGHT_STAGE_FLY = 1
FLIGHT_STAGE_GROUND = 2
FALL_CAN_FALL = 2
FALL_PARACHUTE_OPENED = 5
FALL_NORMAL = 0
BATTLE_STATE_NORMAL = 0
BATTLE_STATE_PARACHUTE = 4
GLIDE_FREE = 7

# Evidenced drop / land points (LOBBY_FINDINGS updates 15–16), not original balance.
DEFAULT_DROP_POS = tuple(bf.FLIGHT_START)  # (698, 19300, -373)
DEFAULT_LAND_POS = (698.0, -677.0, -373.0)
DEFAULT_LAND_DELAY = 8.0

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
    """Owns get-off-plane / parachute / glider / land for one MatchSession."""

    def __init__(self, session, *, timeline=None, own_timeline=None):
        self.session = session
        self.avatar_id = bf.AVATAR_ID
        self.drop_pos = _env_vec3("JUMP_DROP_POS", DEFAULT_DROP_POS)
        self.land_pos = _env_vec3("JUMP_LAND_POS", DEFAULT_LAND_POS)
        self.land_delay = _env_float("JUMP_LAND_DELAY", DEFAULT_LAND_DELAY)
        self.jump_end_frac = _env_float("PLANE_JUMP_END_FRAC", _JUMP_END_FRAC)
        self.off_plane = False
        self.landed = False
        self.choice = None  # None | "parachute" | "glider"
        self.force_dropped = False
        self._land_job = None
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            space = getattr(session, "space_module", None)
            plane = getattr(session, "plane_module", None)
            shared = None
            if space is not None:
                shared = getattr(space, "timeline", None)
            if shared is None and plane is not None:
                shared = getattr(plane, "timeline", None)
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

    # ---- actions --------------------------------------------------------------------

    def _leave_plane(self, *, reason):
        if self.off_plane or self.session.closed:
            return
        self.off_plane = True
        x, y, z = self.drop_pos
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
        plane = getattr(self.session, "plane_module", None)
        if plane is not None:
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

    def _schedule_land(self):
        if self.landed or self.session.closed:
            return
        delay = max(0.0, float(self.land_delay))
        self._land_job = self.session.schedule(delay, self._land)

    def _land(self):
        if self.landed or self.session.closed:
            return
        self.landed = True
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
        self.session._log(
            "      [BATTLE] jump landed at (%.0f, %.0f, %.0f) -> fallPhase 0 flightStage 2"
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
