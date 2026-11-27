"""Shrinking safe zone, circle UI and poison damage (RO-064).

Updates BattleGroundSpace circle fields via RO-059 property updates, drives
``updateCircleRestTime`` / ``showCircleNotify`` / ``onRequestCircleRestTime``, toggles
``isInPoisonArea`` on the avatar, and applies poison DPS until ``hp`` hits zero
(``session.results_module.apply_zone_fatal``).

Stages (ZONE_SOURCE=client, the default) are the client's own CIRCLE_PARAM values in
battle_flow (ZONE_INIT, ZONE_STAGES wait/shrink/radius, ZONE_DAMAGE amount/interval), the ones the
legacy battle_flow zone used and that passed on LDPlayer (checklist 14.x). The zone starts when the
player lands (flow stage "ground"); each stage announces a white circle toward the player, waits,
then shrinks the blue circle onto it in 1 s steps. Surviving the last circle wins the match.
ZONE_SOURCE=data keeps the older gateway-invented battle/data/zone.json stages (tests).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import battle_flow as bf
from battle.timeline import MatchTimeline, load_phase_durations, shared_timeline

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_ZONE_PATH = DATA_DIR / "zone.json"

AVATAR_ID = bf.AVATAR_ID


def _env_float(key, default):
    if key in os.environ:
        return float(os.environ[key])
    return float(default)


def _env_int(key, default):
    if key in os.environ:
        return int(os.environ[key])
    return int(default)


def _load_zone_config(path=None):
    root = Path(path) if path is not None else DEFAULT_ZONE_PATH
    cfg = {
        "player_hp": 100,
        "poison_tick_seconds": 1.0,
        "stages": [],
    }
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in ("player_hp", "poison_tick_seconds", "stages"):
            if key in raw:
                cfg[key] = raw[key]
    cfg["player_hp"] = _env_int("ZONE_PLAYER_HP", cfg["player_hp"])
    cfg["poison_tick_seconds"] = _env_float("ZONE_POISON_TICK", cfg["poison_tick_seconds"])
    return cfg


def zone_source():
    return os.environ.get("ZONE_SOURCE", "client")


def client_stages(scale=None):
    """Stage dicts from the client's circle parameters (battle_flow.ZONE_STAGES / ZONE_DAMAGE)."""
    scale = bf.ZONE_TIME_SCALE if scale is None else float(scale)
    stages, at = [], 0.0
    for i, (wait, shrink, radius) in enumerate(bf.ZONE_STAGES):
        amount, every = bf.ZONE_DAMAGE[min(i, len(bf.ZONE_DAMAGE) - 1)]
        stages.append({
            "delay": at, "rest_seconds": int(wait * scale), "shrink_seconds": float(shrink * scale),
            "circle_stage": i + 1, "white_radius": int(radius), "toward_player": True,
            "poison_amount": int(amount), "poison_every": float(every),
        })
        at += (wait + shrink) * scale
    return stages


def in_blue_circle(x, z, center, radius):
    """True when (x, z) is inside the blue safe circle (XZ plane)."""
    cx, cz = float(center[0]), float(center[1])
    r = float(radius)
    if r <= 0.0:
        return False
    dx = float(x) - cx
    dz = float(z) - cz
    return (dx * dx + dz * dz) <= (r * r)


class ZoneModule:
    """Stage-driven circle shrink and poison for one MatchSession."""

    def __init__(self, session, *, zone_data_path=None, timeline=None, own_timeline=None):
        self.session = session
        self.cfg = _load_zone_config(zone_data_path)
        self.client_mode = zone_data_path is None and zone_source() == "client"
        self.stages = client_stages() if self.client_mode else list(self.cfg.get("stages") or [])
        self.avatar_id = AVATAR_ID
        self.space_id = getattr(session, "space_id", bf.SPACE_ID)
        self._player_hp = int(self.cfg["player_hp"])
        self.poison_tick = float(self.cfg["poison_tick_seconds"])
        self.pos_x = 0.0
        self.pos_z = 0.0
        self._position_set = False
        self._stage_idx = -1
        self._blue_center = (0.0, 0.0)
        self._blue_radius = 0.0
        self._poison_dps = 0
        self._rest_seconds = 0
        self._in_poison = False
        self._play_started = False
        self._poison_job = None
        self._poison_amount = 0
        self._poison_every = 1.0
        self._last_damage = None
        self.closed_zone = False
        if self.client_mode:
            (cx, cz), r = bf.ZONE_INIT
            self._blue_center, self._blue_radius = (float(cx), float(cz)), float(r)
        self._sync_player_hp_from_session()
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            shared = shared_timeline(session, "space_module", "plane_module", "jump_module")
            if shared is not None:
                self.timeline = shared
                self._owns_timeline = False if own_timeline is None else bool(own_timeline)
            else:
                self.timeline = MatchTimeline(load_phase_durations())
                self._owns_timeline = True if own_timeline is None else bool(own_timeline)

    @property
    def player_hp(self):
        player = getattr(self.session, "player", None)
        if player is not None:
            return int(player.health)
        return self._player_hp

    @player_hp.setter
    def player_hp(self, value):
        v = int(value)
        player = getattr(self.session, "player", None)
        if player is not None:
            player.health = float(v)
            if v <= 0:
                player.set_eliminated()
        self._player_hp = v

    def _sync_player_hp_from_session(self):
        player = getattr(self.session, "player", None)
        if player is not None:
            cap = float(self._player_hp)
            player.max_health = cap
            if player.health <= 0 or player.health > cap:
                player.health = cap

    def start(self):
        if self.session.closed:
            return
        flow = getattr(self.session, "flow", None)
        if self.client_mode and flow is not None:
            flow.on_enter("ground", self._on_ground)
        else:
            self.timeline.on_phase("play", self._on_play)
        if self._owns_timeline:
            self.timeline.start(self.session)
        self.session.zone_module = self
        self.session._log("      [BATTLE] zone module started (%d stages)" % len(self.stages))

    def track_position(self, x, z, from_client=True):
        """Update the avatar XZ used for poison checks. Client reports (position_sync) win: once one
        arrives, the jump module's landing point is no longer used (QA 2026-11-27)."""
        if from_client:
            self._client_position = True
        self.pos_x = float(x)
        self.pos_z = float(z)
        self._position_set = True
        self._refresh_poison_flag()

    def current_stage(self):
        if self._stage_idx < 0 or self._stage_idx >= len(self.stages):
            return None
        return dict(self.stages[self._stage_idx])

    def is_in_poison_area(self):
        if not self._play_started:
            return False
        if not self._position_set:
            return False
        return not in_blue_circle(
            self.pos_x, self.pos_z, self._blue_center, self._blue_radius
        )

    # ---- timeline -------------------------------------------------------------------

    def _on_play(self, _phase):
        if self.session.closed:
            return
        self._play_started = True
        self._sync_position_from_jump()
        if self.player_hp > 0:
            self.session.enqueue(
                bf.update_property("BattleGroundAvatar", "hp", bf.i32(self.player_hp))
            )
            self.session.enqueue(
                bf.update_property("BattleGroundAvatar", "maxHp", bf.i32(self.player_hp))
            )
        for stage in self.stages:
            delay = float(stage.get("delay", 0.0))
            self.session.schedule(delay, self._apply_stage, stage)
        if self.poison_tick > 0.0:
            self.session.schedule(self.poison_tick, self._poison_tick_recurring)

    def _on_ground(self, _stage):
        """Client-data zone: the fight starts when the player lands (legacy ZONE_AUTO behaviour)."""
        if self.session.closed or self._play_started:
            return
        sid = self.space_id
        self.session.enqueue(bf.update_property("BattleGroundSpace", "gameStatus", bf.i32(bf.GS_FIGHT), eid=sid))
        bx, bz = self._blue_center
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleCenter", bf.vec2(bx, bz), eid=sid))
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleRadius",
                                                bf.i32(int(self._blue_radius)), eid=sid))
        space = getattr(self.session, "space_module", None)
        if space is not None and getattr(space, "defaults", None) is not None:
            space.defaults["gameStatus"] = bf.GS_FIGHT
        self.session._log("      [BATTLE] zone start (client stages, %d, time scale %.2f)"
                          % (len(self.stages), bf.ZONE_TIME_SCALE))
        self._on_play("ground")

    def _sync_position_from_jump(self):
        if getattr(self, "_client_position", False):
            return
        jump = getattr(self.session, "jump_module", None)
        if jump is None:
            return
        land = getattr(jump, "land_pos", None)
        if land and len(land) >= 3:
            self.track_position(land[0], land[2], from_client=False)
        elif getattr(jump, "drop_pos", None):
            d = jump.drop_pos
            self.track_position(d[0], d[2], from_client=False)

    def _apply_stage(self, stage):
        if self.session.closed:
            return
        self._stage_idx += 1
        self._rest_seconds = int(stage.get("rest_seconds", 0))
        if not stage.get("toward_player"):
            self._blue_center = tuple(stage.get("blue_center", [0.0, 0.0]))
            self._blue_radius = float(stage.get("blue_radius", 0.0))
        self._poison_dps = int(stage.get("poison_dps", 0))
        self._poison_amount = int(stage.get("poison_amount", 0))
        self._poison_every = float(stage.get("poison_every", 1.0))
        circle_stage = int(stage.get("circle_stage", self._stage_idx + 1))
        wr = int(stage.get("white_radius", 0))
        if stage.get("toward_player"):
            target = (self.pos_x, self.pos_z) if self._position_set else self._blue_center
            wc = list(bf._toward(self._blue_center, target, max(self._blue_radius - wr, 0)))
        else:
            wc = stage.get("white_center", list(self._blue_center))
        bx, bz = self._blue_center
        wx, wz = float(wc[0]), float(wc[1])
        sid = self.space_id
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace", "circleStage", bf.i32(circle_stage), eid=sid
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "whiteCircleCenter",
                bf.vec2(wx, wz),
                eid=sid,
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "whiteCircleRadius",
                bf.i32(wr),
                eid=sid,
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "blueCircleCenter",
                bf.vec2(float(bx), float(bz)),
                eid=sid,
            )
        )
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "blueCircleRadius",
                bf.i32(int(self._blue_radius)),
                eid=sid,
            )
        )
        self.session.enqueue(
            bf.entity_method(
                sid,
                "BattleGroundSpace",
                "updateCircleRestTime",
                bf.i32(self._rest_seconds),
            )
        )
        self.session.enqueue(
            bf.entity_method(
                sid,
                "BattleGroundSpace",
                "showCircleNotify",
                bf.i32(circle_stage),
            )
        )
        self.session.enqueue(
            bf.entity_method(
                self.avatar_id,
                "BattleGroundAvatar",
                "onRequestCircleRestTime",
                bf.i32(self._rest_seconds),
            )
        )
        space = getattr(self.session, "space_module", None)
        if space is not None and getattr(space, "defaults", None) is not None:
            d = space.defaults
            d["circleStage"] = circle_stage
            d["whiteCircleCenter"] = [wx, wz]
            d["whiteCircleRadius"] = wr
            d["blueCircleCenter"] = [float(bx), float(bz)]
            d["blueCircleRadius"] = int(self._blue_radius)
        self._refresh_poison_flag()
        if stage.get("shrink_seconds"):
            last = self._stage_idx >= len(self.stages) - 1
            self.session.schedule(self._rest_seconds, self._shrink_start, (wx, wz), wr,
                                  float(stage["shrink_seconds"]), last)
        self.session._log(
            "      [BATTLE] zone stage %s circle=%s blue_r=%.0f rest=%ss dps=%s"
            % (
                circle_stage,
                self._blue_center,
                self._blue_radius,
                self._rest_seconds,
                self._poison_dps,
            )
        )

    # ---- shrink (client stages) ------------------------------------------------------

    def _shrink_start(self, white_center, white_radius, seconds, last):
        if self.session.closed:
            return
        sid = self.space_id
        start_c, start_r = self._blue_center, self._blue_radius
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleStartCenter", bf.vec2(*start_c), eid=sid))
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleStartRadius", bf.i32(int(start_r)), eid=sid))
        self.session.enqueue(bf.entity_method(sid, "BattleGroundSpace", "updateCircleRestTime", bf.i32(int(seconds))))
        steps = max(1, int(math.ceil(seconds)))
        for n in range(1, steps + 1):
            self.session.schedule(seconds * n / steps, self._shrink_step, start_c, start_r,
                                  white_center, white_radius, n / steps, last and n == steps)

    def _shrink_step(self, start_c, start_r, white_c, white_r, k, final):
        if self.session.closed:
            return
        sid = self.space_id
        self._blue_center = (start_c[0] + (white_c[0] - start_c[0]) * k, start_c[1] + (white_c[1] - start_c[1]) * k)
        self._blue_radius = start_r + (white_r - start_r) * k
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleCenter", bf.vec2(*self._blue_center), eid=sid))
        self.session.enqueue(bf.update_property("BattleGroundSpace", "blueCircleRadius",
                                                bf.i32(int(self._blue_radius)), eid=sid))
        space = getattr(self.session, "space_module", None)
        if space is not None and getattr(space, "defaults", None) is not None:
            space.defaults["blueCircleCenter"] = list(self._blue_center)
            space.defaults["blueCircleRadius"] = int(self._blue_radius)
        self._refresh_poison_flag()
        if final:
            self.closed_zone = True
            self.session._log("      [BATTLE] zone closed")
            results = getattr(self.session, "results_module", None)
            if self.player_hp > 0 and results is not None and hasattr(results, "declare_victory"):
                results.declare_victory(placement=1)      # survived the last circle

    # ---- poison ---------------------------------------------------------------------

    def _poison_tick_recurring(self):
        if self.session.closed or not self._play_started:
            return
        self._sync_position_from_jump()
        self._poison_tick_once()
        if not self.session.closed and self.player_hp > 0:
            self.session.schedule(self.poison_tick, self._poison_tick_recurring)

    def _poison_tick_once(self):
        if self.client_mode:
            return self._client_poison_tick()
        if self._poison_dps <= 0:
            self._refresh_poison_flag()
            return
        if not self.is_in_poison_area():
            self._refresh_poison_flag()
            return
        self.player_hp = max(0, self.player_hp - self._poison_dps)
        self.session.enqueue(
            bf.update_property("BattleGroundAvatar", "hp", bf.i32(self.player_hp))
        )
        self._refresh_poison_flag(force_poison=True)
        if self.player_hp <= 0:
            results = getattr(self.session, "results_module", None)
            if results is not None and hasattr(results, "apply_zone_fatal"):
                results.apply_zone_fatal()
            self.session._log("      [BATTLE] zone poison fatal")

    def _client_poison_tick(self):
        """ZONE_DAMAGE: `amount` hp every `every` seconds outside the blue circle, with the hit effect."""
        if self._poison_amount <= 0 or not self.is_in_poison_area():
            self._refresh_poison_flag()
            self._last_damage = None
            return
        now = self.session._now()
        if self._last_damage is not None and now - self._last_damage < self._poison_every - 1e-6:
            self._refresh_poison_flag()
            return
        self._last_damage = now
        self.player_hp = max(0, self.player_hp - self._poison_amount)
        flow = getattr(self.session, "flow", None)
        if flow is not None:
            flow.add_damage(taken=self._poison_amount)
        self.session.enqueue(bf.hp_messages(self.player_hp))
        self.session.enqueue(bf.client_call("BattleGroundAvatar", "showPoisonEffect", self.avatar_id))
        self._refresh_poison_flag(force_poison=True)
        if self.player_hp <= 0:
            self.session.enqueue(bf.update_property("BattleGroundAvatar", "battleState", bf.i8(bf.STATE_DIED)))
            results = getattr(self.session, "results_module", None)
            if results is not None and hasattr(results, "apply_zone_fatal"):
                results.apply_zone_fatal()
            self.session._log("      [BATTLE] zone poison fatal")

    def _refresh_poison_flag(self, force_poison=False):
        poison = force_poison or self.is_in_poison_area()
        if poison == self._in_poison:
            return
        self._in_poison = poison
        self.session.enqueue(
            bf.update_property(
                "BattleGroundAvatar",
                "isInPoisonArea",
                bf.i8(1 if poison else 0),
            )
        )


def register(session):
    """MatchSession module entry point."""
    mod = ZoneModule(session)
    mod.start()
    return mod