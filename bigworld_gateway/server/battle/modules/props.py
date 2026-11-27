"""DtsProp loot spawn and tryPickUp handling (RO-066).

Creates ground props from ``battle/data/loot.json`` on the match timeline
``play`` phase, validates pickup range, removes the entity, and applies the
same reply chain as ``battle_flow.Match`` (guns → wear slot; other → onAddDtsItem).

Positions and propIDs are gateway data (RO-065), not original RoS balance.
"""

from __future__ import annotations

import json
import math
import os
import pickle
import struct
from pathlib import Path

import battle_flow as bf
import bwdefs
from battle import requests as reqs
from battle.timeline import MatchTimeline, load_phase_durations

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_LOOT_PATH = DATA_DIR / "loot.json"

PICKUP_METHODS = frozenset({"tryPickUp"})
AVATAR_ID = bf.AVATAR_ID


def _env_float(key, default):
    if key in os.environ:
        return float(os.environ[key])
    return float(default)


def load_loot_config(path=None):
    root = Path(path) if path is not None else DEFAULT_LOOT_PATH
    cfg = {"map_id": 700, "pickup_range_xz": 5.0, "entries": []}
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in cfg:
            if key in raw:
                cfg[key] = raw[key]
    cfg["pickup_range_xz"] = _env_float("LOOT_PICKUP_RANGE", cfg["pickup_range_xz"])
    if "BATTLE_MAP" in os.environ:
        cfg["map_id"] = int(os.environ["BATTLE_MAP"])
    return cfg


def xz_distance(ax, az, bx, bz):
    dx = float(ax) - float(bx)
    dz = float(az) - float(bz)
    return math.sqrt(dx * dx + dz * dz)


class PropsModule:
    """Owns DtsProp entities and pickup for one MatchSession."""

    def __init__(self, session, *, loot_data_path=None, timeline=None, own_timeline=None):
        self.session = session
        self.cfg = load_loot_config(loot_data_path)
        self.pickup_range = float(self.cfg["pickup_range_xz"])
        self.map_id = int(self.cfg["map_id"])
        self.props = {}  # eid -> {prop_id, amount, x, y, z}
        self._local_gun_slots = {1: 0, 2: 0}
        if timeline is not None:
            self.timeline = timeline
            self._owns_timeline = True if own_timeline is None else bool(own_timeline)
        else:
            shared = None
            for attr in ("space_module", "plane_module", "jump_module", "zone_module"):
                mod = getattr(session, attr, None)
                if mod is not None:
                    shared = getattr(mod, "timeline", None)
                if shared is not None:
                    break
            if shared is not None:
                self.timeline = shared
                self._owns_timeline = False if own_timeline is None else bool(own_timeline)
            else:
                self.timeline = MatchTimeline(load_phase_durations())
                self._owns_timeline = True if own_timeline is None else bool(own_timeline)

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_pickup_request, self._on_pickup_request)
        self.timeline.on_phase("play", self._on_play)
        if self._owns_timeline:
            self.timeline.start(self.session)
        self.session.props_module = self
        self.session._log(
            "      [BATTLE] props module started (%d entries)" % len(self.cfg.get("entries") or [])
        )

    @property
    def gun_slots(self):
        player = getattr(self.session, "player", None)
        if player is not None:
            return player.gun_slots
        return self._local_gun_slots

    def player_xz(self):
        zone = getattr(self.session, "zone_module", None)
        if zone is not None and getattr(zone, "_position_set", False):
            return float(zone.pos_x), float(zone.pos_z)
        jump = getattr(self.session, "jump_module", None)
        if jump is not None:
            land = getattr(jump, "land_pos", None)
            if land and len(land) >= 3:
                return float(land[0]), float(land[2])
        return 0.0, 0.0

    def in_pickup_range(self, x, z):
        px, pz = self.player_xz()
        return xz_distance(px, pz, x, z) <= self.pickup_range

    def _on_play(self, _phase):
        if self.session.closed:
            return
        for row in self.cfg.get("entries") or []:
            self._spawn_row(row)

    def _spawn_row(self, row):
        prop_id = int(row["prop_id"])
        amount = int(row.get("amount", 1))
        x = float(row["x"])
        y = float(row["y"])
        z = float(row["z"])
        eid = self.session.alloc_prop_id()
        self.props[eid] = {"prop_id": prop_id, "amount": amount, "x": x, "y": y, "z": z}
        body = bf.create_entity(
            eid,
            "DtsProp",
            pos=(x, y, z),
            values={
                "mapID": bf.i32(self.map_id),
                "propID": bf.i32(prop_id),
                "amount": bf.i32(amount),
            },
        )
        self.session.enqueue(body)
        self.session._log(
            "      [BATTLE] props spawn eid=%s propID=%s at (%.1f,%.1f,%.1f)"
            % (eid, prop_id, x, y, z)
        )

    def _is_pickup_request(self, msgid, payload):
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return (
            call is not None
            and call.entity == "DtsProp"
            and call.method in PICKUP_METHODS
        )

    def _on_pickup_request(self, msgid, payload):
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        if call is None or call.method not in PICKUP_METHODS:
            return b""
        eid = int(call.entity_id)
        row = self.props.get(eid)
        if row is None:
            self.session._log("      [BATTLE] props reject pickup missing eid=%s" % eid)
            return b""
        if not self.in_pickup_range(row["x"], row["z"]):
            self.session._log("      [BATTLE] props reject pickup out of range eid=%s" % eid)
            return b""
        return self._apply_pickup(eid, row)

    def _apply_pickup(self, eid, row):
        prop_id = int(row["prop_id"])
        amount = int(row["amount"])
        del self.props[eid]
        bodies = [bf.leave_aoi(eid)]
        if bf.prop_type(prop_id) == "Gun":
            slot = next((s for s in (1, 2) if not self.gun_slots[s]), 1)
            self.gun_slots[slot] = prop_id
            bodies.extend(
                [
                    bf.update_property(
                        "BattleGroundAvatar", "dtsWeapon%d" % slot, bf.weapon_item(prop_id)
                    ),
                    bf.update_property(
                        "BattleGroundAvatar", "dtsCurWeapon", bf.i32(slot)
                    ),
                    bf.entity_method(
                        AVATAR_ID, "BattleGroundAvatar", "onWearDtsWeapon", bf.i32(slot)
                    ),
                    bf.entity_method(
                        AVATAR_ID, "BattleGroundAvatar", "onPickUpPropEntity"
                    ),
                ]
            )
        else:
            info = bwdefs.blob(pickle.dumps({"ex_tm": 0}, protocol=2))
            item = bwdefs.blob(os.urandom(16)) + bf.i32(amount) + info + bf.i32(0)
            add = bf.i32(prop_id) + struct.pack("<I", 1) + item + bf.i8(0) + bf.i32(0)
            player = getattr(self.session, "player", None)
            if player is not None:
                key = str(prop_id)
                player.battle_inventory[key] = player.battle_inventory.get(key, 0) + amount
            bodies.extend(
                [
                    bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onAddDtsItem", add),
                    bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onPickUpPropEntity"),
                ]
            )
        for body in bodies:
            self.session.enqueue(body)
        self.session._log(
            "      [BATTLE] props pickup eid=%s propID=%s (%s)"
            % (eid, prop_id, bf.prop_type(prop_id))
        )
        return b""


def register(session):
    mod = PropsModule(session)
    mod.start()
    return mod