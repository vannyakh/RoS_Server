"""Battle package: stacks, partial pickup, shared by props / discard / equip (RO-077).

``MatchPackage`` is the authoritative in-match bag. ``ItemsModule`` registers before
``props`` (filename order) and owns ``tryPickUp`` when both are loaded.
"""

from __future__ import annotations

import json
import os
import pickle
import struct
import uuid
from pathlib import Path

import battle_flow as bf
import bwdefs
from battle import requests as reqs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_AMOUNTS_PATH = DATA_DIR / "item_amounts.json"

PICKUP_METHODS = frozenset({"tryPickUp"})
AVATAR_ID = bf.AVATAR_ID


def _env_int(key, default):
    if key in os.environ:
        return int(os.environ[key])
    return int(default)


def load_item_amounts(path=None):
    root = Path(path) if path is not None else DEFAULT_AMOUNTS_PATH
    cfg = {
        "package_grid_limit": 300,
        "default_stack_cap": 1,
        "fold_by_default": True,
        "props": {},
    }
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in cfg:
            if key in raw:
                cfg[key] = raw[key]
    cfg["package_grid_limit"] = _env_int("PACKAGE_GRID_LIMIT", cfg["package_grid_limit"])
    cfg["default_stack_cap"] = _env_int("DEFAULT_STACK_CAP", cfg["default_stack_cap"])
    return cfg


def prop_meta(cfg, prop_id: int) -> dict:
    entry = dict((cfg.get("props") or {}).get(str(prop_id)) or {})
    entry.setdefault("stack_cap", int(cfg.get("default_stack_cap", 1)))
    entry.setdefault("folded", bool(cfg.get("fold_by_default", True)))
    cap = int(entry["stack_cap"])
    stacks = int(entry.get("max_stacks", cfg.get("default_max_stacks", 2)))
    entry.setdefault("max_total", cap * max(1, stacks))
    return entry


def parse_try_pickup_args(args: bytes) -> tuple[int, bool]:
    """Decode tryPickUp(INT32, BOOL). qty <= 1 means take max allowed (captured mode)."""
    data = bytes(args or b"")
    if len(data) < 4:
        return 0, True
    qty = struct.unpack_from("<i", data, 0)[0]
    flag = True
    if len(data) >= 5:
        flag = data[4] != 0
    if qty <= 1:
        return 0, flag
    return int(qty), flag


class MatchPackage:
    """In-match dtsItemPackage mirror (gateway-local)."""

    def __init__(self, cfg, *, gun_slots=None):
        self.cfg = cfg
        self.folded: dict[int, int] = {}
        self.gun_slots = gun_slots if gun_slots is not None else {1: 0, 2: 0}

    def stack_cap(self, prop_id: int) -> int:
        return int(prop_meta(self.cfg, prop_id)["stack_cap"])

    def is_folded(self, prop_id: int) -> bool:
        return bool(prop_meta(self.cfg, prop_id)["folded"]) and bf.prop_type(prop_id) != "Gun"

    def _stack_count(self, prop_id: int, total: int) -> int:
        if total <= 0:
            return 0
        cap = max(1, self.stack_cap(prop_id))
        return (int(total) + cap - 1) // cap

    def grid_used(self) -> int:
        guns = sum(1 for s in (1, 2) if self.gun_slots.get(s))
        stacks = sum(self._stack_count(pid, cnt) for pid, cnt in self.folded.items())
        return stacks + guns

    def room_in_stack(self, prop_id: int) -> int:
        pid = int(prop_id)
        meta = prop_meta(self.cfg, pid)
        cap = max(1, int(meta["stack_cap"]))
        max_total = int(meta["max_total"])
        have = int(self.folded.get(pid, 0))
        if have >= max_total:
            return 0
        if self.grid_used() >= int(self.cfg.get("package_grid_limit", 300)) and pid not in self.folded:
            return 0
        partial = have % cap
        slot_room = (cap - partial) if partial else cap
        return min(slot_room, max_total - have)

    def can_reserve_grid(self, prop_id: int) -> bool:
        return self.room_in_stack(prop_id) > 0 or bf.prop_type(int(prop_id)) == "Gun"

    def compute_take(self, prop_id: int, ground_amount: int, request_qty: int) -> int:
        ground_amount = max(0, int(ground_amount))
        if ground_amount <= 0:
            return 0
        if bf.prop_type(prop_id) == "Gun":
            return 1 if ground_amount >= 1 and self.can_reserve_grid(prop_id) else 0
        if not self.can_reserve_grid(prop_id) and int(prop_id) not in self.folded:
            return 0
        room = self.room_in_stack(prop_id)
        if room <= 0:
            return 0
        want = ground_amount if request_qty <= 0 else min(request_qty, ground_amount)
        return min(want, room)

    def add_folded(self, prop_id: int, count: int) -> int:
        count = max(0, int(count))
        if count <= 0:
            return 0
        pid = int(prop_id)
        self.folded[pid] = int(self.folded.get(pid, 0)) + count
        return count


def encode_item_data_convert(amount: int) -> bytes:
    info = bwdefs.blob(pickle.dumps({"ex_tm": 0}, protocol=2))
    return bwdefs.blob(uuid.uuid4().bytes) + bf.i32(int(amount)) + info + bf.i32(0)


def encode_on_add_dts_item(prop_id: int, amount: int) -> bytes:
    item = encode_item_data_convert(amount)
    add = bf.i32(int(prop_id)) + struct.pack("<I", 1) + item + bf.i8(0) + bf.i32(0)
    return bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onAddDtsItem", add)


def encode_sync_amount(prop_eid: int, remainder: int) -> bytes:
    return bf.entity_method(int(prop_eid), "DtsProp", "syncAmount", bf.i32(int(remainder)))


def encode_amount_property(prop_eid: int, remainder: int) -> bytes:
    return bf.update_property("DtsProp", "amount", bf.i32(int(remainder)), eid=int(prop_eid))


class ItemsModule:
    """Owns MatchPackage and tryPickUp replies."""

    def __init__(self, session, *, amounts_path=None):
        self.session = session
        self.cfg = load_item_amounts(amounts_path)
        player = getattr(session, "player", None)
        slots = player.gun_slots if player is not None else {1: 0, 2: 0}
        self.package = MatchPackage(self.cfg, gun_slots=slots)
        session.match_package = self.package
        session.items_module = self

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_pickup, self._on_pickup)
        self.session.items_module = self
        self.session._log("      [BATTLE] items module started (grid_limit=%s)" % self.cfg["package_grid_limit"])

    def _props_mod(self):
        return getattr(self.session, "props_module", None)

    def _is_pickup(self, msgid, payload):
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return (
            call is not None
            and call.entity == "DtsProp"
            and call.method in PICKUP_METHODS
        )

    def _on_pickup(self, msgid, payload):
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        if call is None or call.method not in PICKUP_METHODS:
            return b""
        props = self._props_mod()
        if props is None:
            self.session._log("      [BATTLE] items reject pickup (no props_module)")
            return b""
        eid = int(call.entity_id)
        row = props.props.get(eid)
        if row is None:
            self.session._log("      [BATTLE] items reject pickup missing eid=%s" % eid)
            return b""
        if not props.in_pickup_range(row["x"], row["z"]):
            self.session._log("      [BATTLE] items reject pickup out of range eid=%s" % eid)
            return b""
        req_qty, _flag = parse_try_pickup_args(call.args)
        prop_id = int(row["prop_id"])
        ground = int(row["amount"])
        take = self.package.compute_take(prop_id, ground, req_qty)
        if take <= 0:
            self.session._log(
                "      [BATTLE] items reject pickup prop=%s ground=%s req=%s"
                % (prop_id, ground, req_qty)
            )
            return b""
        if take > ground:
            self.session._log("      [BATTLE] items reject pickup take > ground")
            return b""
        bodies = self._apply_take(props, eid, row, prop_id, ground, take)
        for body in bodies:
            self.session.enqueue(body)
        self.session._log(
            "      [BATTLE] items pickup eid=%s propID=%s take=%s/%s (%s)"
            % (eid, prop_id, take, ground, bf.prop_type(prop_id))
        )
        return b""

    def _apply_take(self, props, eid, row, prop_id, ground, take):
        remainder = ground - take
        bodies = []
        if bf.prop_type(prop_id) == "Gun":
            slot = next((s for s in (1, 2) if not self.package.gun_slots[s]), 1)
            self.package.gun_slots[slot] = prop_id
            props.gun_slots[slot] = prop_id
            player = getattr(self.session, "player", None)
            if player is not None:
                player.gun_slots[slot] = prop_id
            bodies.append(bf.leave_aoi(eid))
            del props.props[eid]
            bodies.extend(
                [
                    bf.update_property(
                        "BattleGroundAvatar", "dtsWeapon%d" % slot, bf.weapon_item(prop_id)
                    ),
                    bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(slot)),
                    bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onWearDtsWeapon", bf.i32(slot)),
                    bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onPickUpPropEntity"),
                ]
            )
            return bodies
        self.package.add_folded(prop_id, take)
        player = getattr(self.session, "player", None)
        if player is not None:
            key = str(prop_id)
            player.battle_inventory[key] = player.battle_inventory.get(key, 0) + take
        bodies.append(encode_on_add_dts_item(prop_id, take))
        bodies.append(
            bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onPickUpPropEntity")
        )
        if remainder <= 0:
            bodies.insert(0, bf.leave_aoi(eid))
            del props.props[eid]
        else:
            row["amount"] = remainder
            bodies.insert(0, encode_sync_amount(eid, remainder))
            bodies.insert(1, encode_amount_property(eid, remainder))
        return bodies


def register(session):
    mod = ItemsModule(session)
    mod.start()
    return mod