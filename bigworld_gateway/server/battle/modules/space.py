"""BattleGroundSpace entity + pre-start countdown (RO-061).

Creates Globals.spaceEntity when MatchSession starts and removes it on session end.
Uses RO-059 encoders in battle_flow (create_entity / leave_aoi / update_property).
Timeline lengths and aliveNum are gateway parameters, not original RoS values.

When this module is loaded, set BATTLE_SPACE=off so the legacy ros_server delayed
spacet path does not create a second entity with the same id.
"""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path

import battle_flow as bf
import bwdefs
from battle.timeline import MatchTimeline, load_phase_durations

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SPACE_PATH = DATA_DIR / "space.json"

# BattleGroundGameStatusEnum (Frida / AutoRoyaleSpace): PREPARE shows the HUD countdown.
GAME_STATUS_PREPARE = 1
GAME_STATUS_BEFORE_FIGHT = 2


def _load_space_defaults(path=None):
    root = Path(path) if path is not None else DEFAULT_SPACE_PATH
    defaults = {
        "mapID": 700,
        "gameStartTime": 0,
        "gameStatus": GAME_STATUS_PREPARE,
        "clientStatus": None,
        "weatherID": 0,
        "aliveNum": 100,
        "circleStage": 1,
        "whiteCircleCenter": [845.0, -2467.0],
        "whiteCircleRadius": 300,
        "blueCircleCenter": [845.0, -2467.0],
        "blueCircleRadius": 1200,
        "blueCircleStartCenter": [845.0, -2467.0],
        "blueCircleStartRadius": 1200,
    }
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in defaults:
            if key in raw:
                defaults[key] = raw[key]
    if "BATTLE_MAP" in os.environ:
        defaults["mapID"] = int(os.environ["BATTLE_MAP"])
    if "SPACE_ALIVE_NUM" in os.environ:
        defaults["aliveNum"] = int(os.environ["SPACE_ALIVE_NUM"])
    if "SPACE_WEATHER_ID" in os.environ:
        defaults["weatherID"] = int(os.environ["SPACE_WEATHER_ID"])
    return defaults


def _py(value):
    """PYTHON property bytes (pickle protocol 2 + blob length). None -> 80024e2e."""
    return bwdefs.blob(pickle.dumps(value, protocol=2))


def build_space_values(defaults, *, stage_start, plane_id):
    """Encode BattleGroundSpace createEntity property map via RO-059 helpers."""
    wx, wz = defaults["whiteCircleCenter"]
    bx, bz = defaults["blueCircleCenter"]
    sx, sz = defaults["blueCircleStartCenter"]
    return {
        "mapID": bf.i32(int(defaults["mapID"])),
        "gameStartTime": bf.i32(int(defaults["gameStartTime"])),
        "gameStatus": bf.i32(int(defaults["gameStatus"])),
        "clientStatus": _py(defaults["clientStatus"]),
        "weatherID": bf.i32(int(defaults["weatherID"])),
        "aliveNum": bf.i32(int(defaults["aliveNum"])),
        "gameStageStartTime": bf.f32(float(stage_start)),
        "circleStage": bf.i32(int(defaults["circleStage"])),
        "whiteCircleCenter": bf.vec2(float(wx), float(wz)),
        "whiteCircleRadius": bf.i32(int(defaults["whiteCircleRadius"])),
        "blueCircleCenter": bf.vec2(float(bx), float(bz)),
        "blueCircleRadius": bf.i32(int(defaults["blueCircleRadius"])),
        "blueCircleStartCenter": bf.vec2(float(sx), float(sz)),
        "blueCircleStartRadius": bf.i32(int(defaults["blueCircleStartRadius"])),
        "planeEntityIDs": bf.arr_i32([int(plane_id)]),
    }


class SpaceModule:
    """Owns the BattleGroundSpace entity for one MatchSession."""

    def __init__(self, session, *, space_data_path=None, timeline=None, stage_start=None):
        self.session = session
        self.space_id = session.alloc_space_id()
        self.plane_id = session.alloc_plane_id()
        self.defaults = _load_space_defaults(space_data_path)
        self.timeline = timeline if timeline is not None else MatchTimeline(load_phase_durations())
        self.created = False
        self.removed = False
        # serverTime at create ~= 1.0 when setGameTime ticks start at match enter.
        self.stage_start = 1.0 if stage_start is None else float(stage_start)
        self._orig_close = session.close

    def start(self):
        if self.created or self.session.closed:
            return
        values = build_space_values(
            self.defaults, stage_start=self.stage_start, plane_id=self.plane_id
        )
        body = bf.create_entity(self.space_id, "BattleGroundSpace", values=values)
        self.session.enqueue(body)
        self.created = True
        self.session.space_module = self
        self.session._log(
            "      [BATTLE] space module create eid=%s mapID=%s gameStatus=%s aliveNum=%s weatherID=%s (%dB)"
            % (
                self.space_id,
                self.defaults["mapID"],
                self.defaults["gameStatus"],
                self.defaults["aliveNum"],
                self.defaults["weatherID"],
                len(body),
            )
        )
        self.timeline.on_phase("boarding", self._on_boarding)
        self.timeline.start(self.session)
        self.session.close = self._close_with_cleanup

    def _on_boarding(self, _phase):
        """End of warmup / pre-start: drop the countdown banner (BEFORE_FIGHT)."""
        if self.session.closed or self.removed:
            return
        body = bf.update_property(
            "BattleGroundSpace",
            "gameStatus",
            bf.i32(GAME_STATUS_BEFORE_FIGHT),
            eid=self.space_id,
        )
        self.session.enqueue(body)
        self.defaults["gameStatus"] = GAME_STATUS_BEFORE_FIGHT

    def remove(self):
        if self.removed or not self.created:
            self.removed = True
            return
        if not self.session.closed:
            self.session.enqueue(bf.leave_aoi(self.space_id))
        self.removed = True

    def _close_with_cleanup(self):
        try:
            self.remove()
        finally:
            self._orig_close()


def register(session):
    """MatchSession module entry point (GATEWAY_BATTLE_SESSION.md)."""
    mod = SpaceModule(session)
    mod.start()
    return mod
