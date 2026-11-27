"""Plane entity, boarding and flight path (RO-062).

Creates the Plane entity (client type 147) on the MatchTimeline boarding phase,
points the avatar's planeID / flightStage / leftPlayerNumOnPlane at it, and flips
inJumpArea during the flight jump window. Also updates BattleGroundSpace
getOnPlaneTime and planeEntityIDs via RO-059 encoders.

movePath / moveSpeed / phase lengths are gateway parameters, not original RoS.
When the space module is loaded, set BATTLE_SPACE=off so the legacy ros_server
delayed spacet path does not create a second space entity.
"""

from __future__ import annotations

import os

import battle_flow as bf
from battle.timeline import MatchTimeline, load_phase_durations

# Client const.FlightStage (LOBBY_FINDINGS update 15). Gateway uses Launch/Fly only here.
FLIGHT_STAGE_LAUNCH = 0
FLIGHT_STAGE_FLY = 1

# Map 700 two-point path at height 300 (same shape as battle_flow debug "plane").
DEFAULT_MOVE_PATH = ((0.0, 300.0, 0.0), (2000.0, 300.0, 2000.0))
DEFAULT_MOVE_SPEED = 60.0
DEFAULT_MODE = 0
DEFAULT_MAP_ID = 700
DEFAULT_LEFT_ON_PLANE = 1  # solo BR

# Jump window as fractions of the flight phase (gateway params).
_JUMP_START_FRAC = 0.25
_JUMP_END_FRAC = 0.75


def _env_float(key, default):
    if key in os.environ:
        return float(os.environ[key])
    return float(default)


def _env_int(key, default):
    if key in os.environ:
        return int(os.environ[key])
    return int(default)


def build_move_path(map_id=None):
    """Return VECTOR3 waypoints for Plane.movePath over map 700 (gateway path)."""
    _ = map_id  # reserved; path is map-700 shaped until map-specific data exists
    raw = os.environ.get("PLANE_MOVE_PATH")
    if raw:
        pts = []
        for chunk in raw.split(";"):
            x, y, z = (float(v) for v in chunk.split(","))
            pts.append((x, y, z))
        if len(pts) >= 2:
            return pts
    return [tuple(p) for p in DEFAULT_MOVE_PATH]


def build_plane_values(*, map_id=None, move_speed=None, mode=None, in_jump_area=0, move_path=None):
    """Encode Plane createEntity property map via RO-059 helpers."""
    mid = DEFAULT_MAP_ID if map_id is None else int(map_id)
    if "BATTLE_MAP" in os.environ:
        mid = int(os.environ["BATTLE_MAP"])
    speed = DEFAULT_MOVE_SPEED if move_speed is None else float(move_speed)
    if "PLANE_MOVE_SPEED" in os.environ:
        speed = float(os.environ["PLANE_MOVE_SPEED"])
    md = DEFAULT_MODE if mode is None else int(mode)
    path = build_move_path(mid) if move_path is None else list(move_path)
    return {
        "mapID": bf.i32(mid),
        "moveSpeed": bf.f32(speed),
        "inJumpArea": bf.i8(1 if in_jump_area else 0),
        "mode": bf.i32(md),
        "movePath": bf.arr_vec3(path),
    }


class PlaneModule:
    """Owns the Plane entity and boarding / jump-window property updates."""

    def __init__(
        self, session, *, timeline=None, move_path=None, left_on_plane=None, own_timeline=None
    ):
        self.session = session
        self.plane_id = session.alloc_plane_id()
        self.space_id = session.alloc_space_id()
        self.avatar_id = bf.AVATAR_ID
        self.move_path = build_move_path() if move_path is None else list(move_path)
        self.left_on_plane = (
            DEFAULT_LEFT_ON_PLANE if left_on_plane is None else int(left_on_plane)
        )
        if "PLANE_LEFT_PLAYER_NUM" in os.environ:
            self.left_on_plane = int(os.environ["PLANE_LEFT_PLAYER_NUM"])
        self.jump_start_frac = _env_float("PLANE_JUMP_START_FRAC", _JUMP_START_FRAC)
        self.jump_end_frac = _env_float("PLANE_JUMP_END_FRAC", _JUMP_END_FRAC)
        self.created = False
        self.removed = False
        self.in_jump_area = False
        self.flight_stage = None
        self.plane_id_prop = None
        # own_timeline: start this MatchTimeline from PlaneModule.start().
        # False when attaching to a timeline SpaceModule already started.
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            space = getattr(session, "space_module", None)
            shared = getattr(space, "timeline", None) if space is not None else None
            if shared is not None:
                self.timeline = shared
                self._owns_timeline = False if own_timeline is None else bool(own_timeline)
            else:
                self.timeline = MatchTimeline(load_phase_durations())
                self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        self._orig_close = session.close

    def start(self):
        if self.session.closed:
            return
        self.timeline.on_phase("boarding", self._on_boarding)
        self.timeline.on_phase("flight", self._on_flight)
        if self._owns_timeline:
            self.timeline.start(self.session)
        self.session.plane_module = self
        self.session.close = self._close_with_cleanup

    def _on_boarding(self, _phase):
        if self.session.closed or self.created:
            return
        values = build_plane_values(move_path=self.move_path)
        body = bf.create_entity(self.plane_id, "Plane", values=values)
        self.session.enqueue(body)
        self.created = True
        self.in_jump_area = False

        get_on = _env_int("PLANE_GET_ON_TIME", int(self.session._now()))
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "getOnPlaneTime",
                bf.i32(get_on),
                eid=self.space_id,
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "planeEntityIDs",
                bf.arr_i32([int(self.plane_id)]),
                eid=self.space_id,
            )
        )

        self._set_avatar_boarding_props()
        self.session._log(
            "      [BATTLE] plane module create eid=%s mapID=%s path=%d pts speed=%s (%dB)"
            % (
                self.plane_id,
                DEFAULT_MAP_ID,
                len(self.move_path),
                DEFAULT_MOVE_SPEED,
                len(body),
            )
        )

    def _set_avatar_boarding_props(self):
        """Point the player at this plane (LOBBY_FINDINGS: planeID -> on-plane pose)."""
        pid = int(self.plane_id)
        self.session.enqueue(
            bf.update_property("BattleGroundAvatar", "planeID", bf.i32(pid))
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "flightStage", bf.i32(FLIGHT_STAGE_LAUNCH)
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "leftPlayerNumOnPlane",
                bf.i32(self.left_on_plane),
            )
        )
        self.plane_id_prop = pid
        self.flight_stage = FLIGHT_STAGE_LAUNCH

    def _on_flight(self, _phase):
        if self.session.closed or not self.created:
            return
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "flightStage", bf.i32(FLIGHT_STAGE_FLY)
            )
        )
        self.flight_stage = FLIGHT_STAGE_FLY
        flight_dur = float(self.timeline.durations.get("flight", 0.0))
        if flight_dur <= 0.0:
            self._set_in_jump_area(True)
            return
        start = max(0.0, min(1.0, self.jump_start_frac)) * flight_dur
        end = max(0.0, min(1.0, self.jump_end_frac)) * flight_dur
        if end < start:
            end = start
        self.session.schedule(start, self._set_in_jump_area, True)
        if end > start:
            self.session.schedule(end, self._set_in_jump_area, False)

    def _set_in_jump_area(self, flag):
        if self.session.closed or not self.created or self.removed:
            return
        flag = bool(flag)
        body = bf.update_property(
            "Plane",
            "inJumpArea",
            bf.i8(1 if flag else 0),
            eid=self.plane_id,
        )
        self.session.enqueue(body)
        self.in_jump_area = flag
        self.session._log(
            "      [BATTLE] plane inJumpArea=%s eid=%s" % (int(flag), self.plane_id)
        )

    def remove(self):
        if self.removed or not self.created:
            self.removed = True
            return
        if not self.session.closed:
            self.session.enqueue(bf.leave_aoi(self.plane_id))
        self.removed = True

    def _close_with_cleanup(self):
        try:
            self.remove()
        finally:
            self._orig_close()


def register(session):
    """MatchSession module entry point (GATEWAY_BATTLE_SESSION.md).

    Deferred start so alphabetically later space.py can own the shared
    MatchTimeline when both modules load; otherwise this module starts its own.
    """
    mod = PlaneModule(session)
    session.schedule(0.0, _deferred_start, mod)
    return mod


def _deferred_start(mod):
    if mod.session.closed:
        return
    space = getattr(mod.session, "space_module", None)
    shared = getattr(space, "timeline", None) if space is not None else None
    if shared is not None and mod._owns_timeline:
        mod.timeline = shared
        mod._owns_timeline = False
    mod.start()
