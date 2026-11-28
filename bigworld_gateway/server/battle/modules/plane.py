"""Plane entity, flight route, boarding and jump window (RO-062).

Evidence (bigworld_gateway/docs/LOBBY_FINDINGS.md):

- Update 21 (boarding, verified): BattleGroundSpace BEFORE_FIGHT + ``Plane`` createEntity, then the
  avatar's ``fallPhase`` CAN_FALL, ``leftPlayerNumOnPlane`` and ``planeID``. planeID must be set after
  the plane has loaded and the loading screen is gone; set too early, ``getOnPlane`` does nothing.
  The legacy auto timeline re-sent planeID every 5 s while position reports still showed the ground.
- Update 22 (verified): ``FLIGHT_STEPS`` plane at +0 s, planeID 0 -> plane id, leftPlayerNumOnPlane,
  fallPhase 2 at +3 s (``battle_flow.BOARD_DELAY``). planeID in the plane's own bundle left the
  player on the ground.
- Update 25 (verified): the Plane has an AvatarFilter and only follows server positions;
  ``movePath`` / ``moveSpeed`` do not move it. ``detailedPosition`` 0x58 (30 bytes,
  ``battle_flow.detailed_position``) every ``FLIGHT_POS_EVERY`` s at ``FLIGHT_SPEED`` (500 units/s)
  along the route at y ``FLIGHT_START[1]`` (19300), ``mode`` 1 (PEOPLE, the transport jet).
- Map 700: MAP_RANGE (-20000, -20000, 20000, 20000) (update 21) and CIRCLE_BOUND_BOX
  (-22429.98, -20648.09, 8450.52, 10375.44) (map table, line ~192); initial blue circle centre
  ``battle_flow.ZONE_INIT`` (-7507, -4674).

Gateway parameters (not original RoS): the route's random entry edge / spread / angle, where on the
route the plane starts (so the timeline's jump window is over the play area), the jump-window
fractions, and when server-side bots leave the plane.
"""

from __future__ import annotations

import math
import os
import random

import battle_flow as bf
from battle.timeline import MatchTimeline, load_phase_durations, shared_timeline

# Client const.FlightStage (LOBBY_FINDINGS update 15). Gateway uses Launch/Fly only here.
FLIGHT_STAGE_LAUNCH = 0
FLIGHT_STAGE_FLY = 1
FALL_CAN_FALL = 2                       # const.FallPhase CAN_FALL (update 21)

# const.PlaneWorkMode PEOPLE 1 (update 21); mode 1 shows the transport jet (update 25, verified).
DEFAULT_MODE = 1
DEFAULT_MAP_ID = 700
DEFAULT_MOVE_SPEED = float(bf.FLIGHT_SPEED)          # 500 units/s, verified flight (update 25)
PLANE_Y = float(bf.FLIGHT_START[1])                  # 19300, verified drop height (updates 22, 25)
POS_EVERY = float(bf.FLIGHT_POS_EVERY)               # 0.2 s between detailedPosition updates
DEFAULT_LEFT_ON_PLANE = 1  # solo BR without a MatchFlow

# Map 700 bounds (LOBBY_FINDINGS update 21 MAP_RANGE; map table CIRCLE_BOUND_BOX).
MAP_RANGE = (-20000.0, -20000.0, 20000.0, 20000.0)  # min x, min z, max x, max z
CIRCLE_BOUND_BOX = (-22429.98, -20648.09, 8450.52, 10375.44)
PLAY_CENTER = (float(bf.ZONE_INIT[0][0]), float(bf.ZONE_INIT[0][1]))

# Route generation (gateway parameters).
ROUTE_SPREAD = 4000.0       # aim point within this distance of PLAY_CENTER
ROUTE_MAX_ANGLE = 30.0      # degrees off the edge normal

# Jump window as fractions of the flight phase (gateway params).
_JUMP_START_FRAC = 0.25
_JUMP_END_FRAC = 0.75

# Re-send planeID while position reports still show the ground (LOBBY_FINDINGS update 21).
BOARD_RETRY = 5.0
BOARD_GROUND_MARGIN = 100.0

EDGES = ("west", "east", "south", "north")


def _env_float(key, default):
    if key in os.environ:
        return float(os.environ[key])
    return float(default)


def _env_int(key, default):
    if key in os.environ:
        return int(os.environ[key])
    return int(default)


def _play_box():
    """CIRCLE_BOUND_BOX clipped to MAP_RANGE: the area the route must pass over."""
    return (
        max(CIRCLE_BOUND_BOX[0], MAP_RANGE[0]),
        max(CIRCLE_BOUND_BOX[1], MAP_RANGE[1]),
        min(CIRCLE_BOUND_BOX[2], MAP_RANGE[2]),
        min(CIRCLE_BOUND_BOX[3], MAP_RANGE[3]),
    )


def _route_through(aim, edge, angle):
    """Entry / exit (x, z) on opposite MAP_RANGE edges of the line through ``aim``, or None."""
    x0, z0, x1, z1 = MAP_RANGE
    ax, az = aim
    if edge in ("west", "east"):
        sign = 1.0 if edge == "west" else -1.0
        dx, dz = sign * math.cos(angle), math.sin(angle)
        t_in = ((x0 if sign > 0 else x1) - ax) / dx
        t_out = ((x1 if sign > 0 else x0) - ax) / dx
    else:
        sign = 1.0 if edge == "south" else -1.0
        dx, dz = math.sin(angle), sign * math.cos(angle)
        t_in = ((z0 if sign > 0 else z1) - az) / dz
        t_out = ((z1 if sign > 0 else z0) - az) / dz
    start = (ax + dx * t_in, az + dz * t_in)
    end = (ax + dx * t_out, az + dz * t_out)
    eps = 1e-6
    for x, z in (start, end):
        if not (x0 - eps <= x <= x1 + eps and z0 - eps <= z <= z1 + eps):
            return None
    return start, end


def generate_route(rng=None, *, height=PLANE_Y, spread=None, max_angle=None):
    """Random map-700 route: from a random MAP_RANGE edge to the opposite edge, through an aim point
    near the play-area centre. Returns {"path": [start, end], "aim": (x, z), "edge": name}."""
    rng = rng if rng is not None else random.Random()
    spread = _env_float("PLANE_ROUTE_SPREAD", ROUTE_SPREAD) if spread is None else float(spread)
    max_angle = (
        _env_float("PLANE_ROUTE_MAX_ANGLE", ROUTE_MAX_ANGLE) if max_angle is None else float(max_angle)
    )
    bx0, bz0, bx1, bz1 = _play_box()
    r = spread * math.sqrt(rng.random())
    a = rng.random() * 2.0 * math.pi
    aim = (
        min(max(PLAY_CENTER[0] + r * math.cos(a), bx0), bx1),
        min(max(PLAY_CENTER[1] + r * math.sin(a), bz0), bz1),
    )
    edge = EDGES[rng.randrange(len(EDGES))]
    angle = math.radians(rng.uniform(-max_angle, max_angle))
    ends = _route_through(aim, edge, angle)
    while ends is None:              # too steep to reach the opposite edge: halve (0 always fits)
        angle *= 0.5
        if abs(angle) < 1e-4:
            angle = 0.0
        ends = _route_through(aim, edge, angle)
    (sx, sz), (ex, ez) = ends
    y = float(height)
    return {"path": [(sx, y, sz), (ex, y, ez)], "aim": aim, "edge": edge}


def build_move_path(map_id=None, rng=None):
    """Plane.movePath for map 700: ``PLANE_MOVE_PATH`` override, else a generated edge-to-edge route."""
    _ = map_id  # reserved; bounds are map 700's until map-specific data exists
    raw = os.environ.get("PLANE_MOVE_PATH")
    if raw:
        pts = []
        for chunk in raw.split(";"):
            x, y, z = (float(v) for v in chunk.split(","))
            pts.append((x, y, z))
        if len(pts) >= 2:
            return pts
    return generate_route(rng)["path"]


def path_length(path):
    return sum(
        math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in zip(path[:-1], path[1:])
    )


def point_at(path, s):
    """((x, y, z), yaw) at arc length ``s`` along ``path`` (clamped). Yaw as battle_flow.plane_position."""
    s = max(0.0, float(s))
    for a, b in zip(path[:-1], path[1:]):
        seg = math.hypot(b[0] - a[0], b[2] - a[2])
        yaw = math.atan2(b[0] - a[0], b[2] - a[2])
        if s <= seg or b is path[-1]:
            k = 1.0 if seg <= 0.0 else min(s / seg, 1.0)
            return (
                (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k),
                yaw,
            )
        s -= seg
    last = path[-1]
    return (tuple(last), 0.0)


def arc_of_closest(path, xz):
    """Arc length of the route point closest to (x, z)."""
    best, best_d, acc = 0.0, None, 0.0
    for a, b in zip(path[:-1], path[1:]):
        vx, vz = b[0] - a[0], b[2] - a[2]
        seg2 = vx * vx + vz * vz
        k = 0.0 if seg2 <= 0 else max(0.0, min(1.0, ((xz[0] - a[0]) * vx + (xz[1] - a[2]) * vz) / seg2))
        px, pz = a[0] + vx * k, a[2] + vz * k
        d = math.hypot(xz[0] - px, xz[1] - pz)
        if best_d is None or d < best_d:
            best, best_d = acc + math.sqrt(seg2) * k, d
        acc += math.sqrt(seg2)
    return best


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
    """Owns the Plane entity, its flight, boarding and the plane's passenger count."""

    def __init__(
        self, session, *, timeline=None, move_path=None, left_on_plane=None, own_timeline=None,
        rng=None, seed=None,
    ):
        self.session = session
        self.plane_id = session.alloc_plane_id()
        self.space_id = session.alloc_space_id()
        self.avatar_id = bf.AVATAR_ID
        if rng is None:
            if seed is None and "PLANE_SEED" in os.environ:
                seed = int(os.environ["PLANE_SEED"])
            rng = random.Random(seed)
        self.rng = rng
        self.move_path = build_move_path(rng=self.rng) if move_path is None else list(move_path)
        self.route_length = path_length(self.move_path)
        self.speed = _env_float("PLANE_MOVE_SPEED", DEFAULT_MOVE_SPEED)
        self._left_override = None if left_on_plane is None else int(left_on_plane)
        if "PLANE_LEFT_PLAYER_NUM" in os.environ:
            self._left_override = int(os.environ["PLANE_LEFT_PLAYER_NUM"])
        self.left_on_plane = (
            DEFAULT_LEFT_ON_PLANE if self._left_override is None else self._left_override
        )
        self.jump_start_frac = _env_float("PLANE_JUMP_START_FRAC", _JUMP_START_FRAC)
        self.jump_end_frac = _env_float("PLANE_JUMP_END_FRAC", _JUMP_END_FRAC)
        self.board_delay = _env_float("PLANE_BOARD_DELAY", bf.BOARD_DELAY)
        self.created = False
        self.removed = False
        self.in_jump_area = False
        self.flight_stage = None
        self.plane_id_prop = None
        self.created_at = None
        self.start_arc = 0.0
        self.arrived = False
        self.boarded = False
        self.board_sends = 0
        self.human_aboard = True
        self.bots_aboard = 0
        self.bot_drops = []           # [(at, (x, y, z))] server-side bots leaving the plane
        self._board_at = None
        self._board_try_at = None
        self._board_try_report = None
        # own_timeline: start this MatchTimeline from PlaneModule.start().
        # False when attaching to a timeline SpaceModule already started.
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            shared = shared_timeline(session, "space_module")
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
        self.session.on_close(self.remove)

    # ---- route / position -------------------------------------------------------------

    def _now(self):
        return float(self.session._now())

    def _start_arc(self):
        """Where on the route the plane is created. The timeline's jump window is gateway time
        (timeline.json), shorter than an edge-to-edge flight at 500 units/s, so the plane starts as
        far along the route as needed to be over the play area in the middle of the window.
        With a flight phase long enough for the whole route this is the route's start edge."""
        if os.environ.get("PLANE_START_AT_EDGE", "off") == "on":
            return 0.0
        d = self.timeline.durations
        mid = float(d.get("boarding", 0.0)) + float(d.get("flight", 0.0)) * 0.5 * (
            max(0.0, min(1.0, self.jump_start_frac)) + max(0.0, min(1.0, self.jump_end_frac))
        )
        aim = arc_of_closest(self.move_path, PLAY_CENTER)
        return max(0.0, min(self.route_length, aim - self.speed * mid))

    def arc_at(self, now=None):
        if self.created_at is None:
            return 0.0
        now = self._now() if now is None else float(now)
        return min(self.route_length, self.start_arc + self.speed * max(0.0, now - self.created_at))

    def position_at(self, now=None):
        """((x, y, z), yaw) of the plane on its route."""
        return point_at(self.move_path, self.arc_at(now))

    def current_position(self):
        """Plane position now, or None before the plane exists."""
        if not self.created:
            return None
        return self.position_at()[0]

    # ---- boarding ---------------------------------------------------------------------

    def _slots(self):
        flow = getattr(self.session, "flow", None)
        if flow is None:
            return DEFAULT_LEFT_ON_PLANE
        return int(getattr(flow, "slots", DEFAULT_LEFT_ON_PLANE))

    def _on_boarding(self, _phase):
        if self.session.closed or self.created:
            return
        self.left_on_plane = self._slots() if self._left_override is None else self._left_override
        self.bots_aboard = max(0, self.left_on_plane - 1)
        self.created_at = self._now()
        self.start_arc = self._start_arc()
        pos, yaw = self.position_at(self.created_at)
        values = build_plane_values(move_path=self.move_path)
        body = bf.create_entity(self.plane_id, "Plane", pos=pos, direction=(0.0, 0.0, yaw), values=values)
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
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "flightStage", bf.i32(FLIGHT_STAGE_LAUNCH)
            )
        )
        self.flight_stage = FLIGHT_STAGE_LAUNCH
        self._board_at = self.created_at + max(0.0, self.board_delay)
        self.session.schedule(max(0.0, self.board_delay), self._board_due)
        self.session._log(
            "      [BATTLE] plane module create eid=%s mapID=%s route (%.0f,%.0f)->(%.0f,%.0f) len=%.0f "
            "start=%.0f speed=%s aboard=%s (%dB)"
            % (
                self.plane_id, DEFAULT_MAP_ID,
                self.move_path[0][0], self.move_path[0][2], self.move_path[-1][0], self.move_path[-1][2],
                self.route_length, self.start_arc, self.speed, self.left_on_plane, len(body),
            )
        )
        self._tick()

    def client_in_world(self):
        """True once the client reported a position away from the origin (loading screen gone).
        LOBBY_FINDINGS update 21: planeID set during the loading screen does not board the player."""
        player = getattr(self.session, "player", None)
        pos = getattr(player, "position", None)
        if not pos:
            return False
        return any(abs(float(v)) >= 1.0 for v in pos)

    def _jumped(self):
        jump = getattr(self.session, "jump_module", None)
        return not self.human_aboard or bool(getattr(jump, "off_plane", False))

    def _board_due(self):
        if not self.session.closed and not self.boarded:
            self._maybe_board(self._now())

    def _maybe_board(self, now):
        if self.removed or self._jumped() or self._board_at is None or now + 1e-6 < self._board_at:
            return
        if not self.client_in_world():
            return
        player = getattr(self.session, "player", None)
        report = getattr(player, "position", None)
        if self.boarded:
            # Re-send only for a new report that still shows the ground (update 21).
            if report is self._board_try_report or now - self._board_try_at + 1e-6 < BOARD_RETRY:
                return
            if float(report[1]) >= self.position_at(now)[0][1] - BOARD_GROUND_MARGIN:
                return
            self.session._log(
                "      [BATTLE] plane: not on the plane yet (y %.1f), re-sending planeID" % report[1]
            )
        self._board_try_at = now
        self._board_try_report = report
        self._send_board()

    def _send_board(self):
        """FLIGHT_STEPS boarding step (LOBBY_FINDINGS update 22): planeID 0 -> plane id,
        leftPlayerNumOnPlane, fallPhase CAN_FALL."""
        pid = int(self.plane_id)
        self.session.enqueue(bf.update_property("BattleGroundAvatar", "planeID", bf.i32(0)))
        self.session.enqueue(bf.update_property("BattleGroundAvatar", "planeID", bf.i32(pid)))
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(self.left_on_plane)
            )
        )
        self.session.enqueue(
            bf.update_property("BattleGroundAvatar", "fallPhase", bf.i8(FALL_CAN_FALL))
        )
        self.plane_id_prop = pid
        self.boarded = True
        self.board_sends += 1

    # ---- flight -----------------------------------------------------------------------

    def _tick(self):
        """detailedPosition along the route every POS_EVERY s (LOBBY_FINDINGS update 25)."""
        if self.session.closed or self.removed or not self.created:
            return
        now = self._now()
        pos, yaw = self.position_at(now)
        self.session.enqueue(bf.detailed_position(int(self.plane_id), pos, (0.0, 0.0, yaw)))
        self._maybe_board(now)
        if self.arc_at(now) >= self.route_length - 1e-6:
            self.arrived = True
            self.session._log(
                "      [BATTLE] plane reached the end of its route at (%.0f, %.0f, %.0f)" % pos
            )
            return
        self.session.schedule(POS_EVERY, self._tick)

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
            self._schedule_bots(0.0, 0.0)
            return
        start = max(0.0, min(1.0, self.jump_start_frac)) * flight_dur
        end = max(0.0, min(1.0, self.jump_end_frac)) * flight_dur
        if end < start:
            end = start
        self.session.schedule(start, self._set_in_jump_area, True)
        if end > start:
            self.session.schedule(end, self._set_in_jump_area, False)
        self._schedule_bots(start, end)

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
        if not flag:
            while self.bots_aboard > 0:          # window over: nobody server-side stays aboard
                self._bot_leaves()

    # ---- passengers -------------------------------------------------------------------

    def _schedule_bots(self, start, end):
        """Server-side bots leave at random times inside the jump window (no Robot entities are
        sent, BOT_CLIENT_ENTITIES=off). Times are gateway parameters."""
        n = self.bots_aboard
        times = sorted(
            start if end <= start else self.rng.uniform(start, end - 1e-3) for _ in range(n)
        )
        for t in times:
            self.session.schedule(t, self._bot_leaves)

    def _send_left(self):
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(self.left_on_plane)
            )
        )

    def _bot_leaves(self):
        if self.session.closed or self.removed or self.bots_aboard <= 0:
            return
        self.bots_aboard -= 1
        self.left_on_plane = max(0, self.left_on_plane - 1)
        pos = self.current_position()
        self.bot_drops.append((self._now(), pos))
        self._send_left()

    def human_left(self):
        """The client's player left the plane (jump.py). Returns the passengers left."""
        if self.human_aboard:
            self.human_aboard = False
            self.left_on_plane = max(0, self.left_on_plane - 1)
            self._send_left()
        return self.left_on_plane

    # ---- cleanup ----------------------------------------------------------------------

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
