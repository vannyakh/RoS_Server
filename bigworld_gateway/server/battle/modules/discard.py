"""Bag discard: remove from MatchPackage, spawn DtsProp, onDiscardProp (RO-079).

Inbound ``discardDtsProp`` is not in ``battle_cell_exposed.json`` yet; tests and
staged rollout use ``BATTLE_DISCARD_MSGID`` with args ``prop_id INT32, count INT32``
after the entity id. When RO-078 adds a verified index, decode-by-name takes over.
"""

from __future__ import annotations

import os
import struct

import battle_flow as bf
from battle import requests as reqs

DISCARD_METHODS = frozenset({"discardDtsProp", "discardProp"})
AVATAR_ID = bf.AVATAR_ID


def _env_int(key, default):
    if key in os.environ:
        return int(os.environ[key])
    return int(default)


def parse_discard_args(args: bytes) -> tuple[int, int]:
    data = bytes(args or b"")
    if len(data) < 8:
        return 0, 0
    prop_id, count = struct.unpack_from("<ii", data, 0)
    return int(prop_id), int(count)


def _owned_count(package, prop_id: int) -> int:
    pid = int(prop_id)
    total = int(package.folded.get(pid, 0))
    if bf.prop_type(pid) == "Gun":
        for slot in (1, 2):
            if int(package.gun_slots.get(slot, 0)) == pid:
                total += 1
    return total


def _slot_for_prop(package, prop_id: int) -> int:
    pid = int(prop_id)
    for slot in (1, 2):
        if int(package.gun_slots.get(slot, 0)) == pid:
            return slot
    return 0


def encode_on_del_folded(prop_id: int, count: int) -> bytes:
    return bf.entity_method(
        AVATAR_ID,
        "BattleGroundAvatar",
        "onDelDtsFoldedItem",
        struct.pack("<ii", int(prop_id), int(count)),
    )


def encode_on_del_item(prop_id: int) -> bytes:
    return bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onDelDtsItem", bf.i32(int(prop_id)))


def encode_on_discard_prop(_prop_eid: int, prop_id: int) -> bytes:
    """Client callback is on BattleGroundAvatar (iDtsProp sync), not the ground entity."""
    return bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onDiscardProp", bf.i32(int(prop_id)))


class DiscardModule:
    def __init__(self, session):
        self.session = session

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_discard, self._on_discard)
        self.session.discard_module = self
        self.session._log("      [BATTLE] discard module started")

    def _override_msgid(self) -> int:
        return _env_int("BATTLE_DISCARD_MSGID", 0)

    def _is_discard(self, msgid, payload):
        override = self._override_msgid()
        if override > 0 and int(msgid) == override:
            return True
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return (
            call is not None
            and call.entity == "BattleGroundAvatar"
            and call.method in DISCARD_METHODS
        )

    def _parse_call(self, msgid, payload):
        override = self._override_msgid()
        if override > 0 and int(msgid) == override:
            raw = bytes(payload or b"")
            if len(raw) < 8:
                return None
            args = raw[4:]
            return reqs.CellCall(int(struct.unpack_from("<I", raw, 0)[0]), "BattleGroundAvatar", "discardDtsProp", args, False)
        return reqs.decode(int(msgid), payload or b"", log=self.session._log)

    def _package(self):
        return getattr(self.session, "match_package", None)

    def _props_mod(self):
        return getattr(self.session, "props_module", None)

    def _player_pos(self):
        props = self._props_mod()
        y = -677.0
        jump = getattr(self.session, "jump_module", None)
        if jump is not None:
            land = getattr(jump, "land_pos", None)
            if land and len(land) >= 3:
                y = float(land[1])
        if props is not None:
            x, z = props.player_xz()
            return float(x), float(y), float(z)
        return 0.0, float(y), 0.0

    def _spawn_drop(self, props, prop_id: int, amount: int):
        x, y, z = self._player_pos()
        eid = self.session.alloc_prop_id()
        props.props[eid] = {
            "prop_id": int(prop_id),
            "amount": int(amount),
            "x": x,
            "y": y,
            "z": z,
        }
        body = bf.create_entity(
            eid,
            "DtsProp",
            pos=(x, y, z),
            values={
                "mapID": bf.i32(props.map_id),
                "propID": bf.i32(int(prop_id)),
                "amount": bf.i32(int(amount)),
            },
        )
        return eid, body

    def _clear_gun_slot(self, package, props, slot: int):
        package.gun_slots[slot] = 0
        if props is not None:
            props.gun_slots[slot] = 0
        player = getattr(self.session, "player", None)
        if player is not None:
            player.gun_slots[slot] = 0

    def _on_discard(self, msgid, payload):
        package = self._package()
        props = self._props_mod()
        if package is None or props is None:
            self.session._log("      [BATTLE] discard reject (no package or props)")
            return b""
        call = self._parse_call(msgid, payload)
        if call is None or call.method not in DISCARD_METHODS:
            return b""
        prop_id, count = parse_discard_args(call.args)
        if count <= 0:
            self.session._log(
                "      [BATTLE] discard reject prop=%s count=%s (non-positive)" % (prop_id, count)
            )
            return b""
        owned = _owned_count(package, prop_id)
        if owned <= 0 or count > owned:
            self.session._log(
                "      [BATTLE] discard reject prop=%s count=%s owned=%s"
                % (prop_id, count, owned)
            )
            return b""
        bodies = []
        remaining = count
        slot = _slot_for_prop(package, prop_id)
        if slot and bf.prop_type(prop_id) == "Gun" and remaining > 0:
            self._clear_gun_slot(package, props, slot)
            bodies.append(
                bf.update_property("BattleGroundAvatar", "dtsWeapon%d" % slot, bf.weapon_item(0))
            )
            cur = getattr(self.session, "_equip_cur_slot", None)
            if cur == slot:
                bodies.append(bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(0)))
            remaining -= 1
        folded_have = int(package.folded.get(int(prop_id), 0))
        take_folded = min(remaining, folded_have)
        if take_folded > 0:
            package.folded[int(prop_id)] = folded_have - take_folded
            if package.folded[int(prop_id)] <= 0:
                package.folded.pop(int(prop_id), None)
            player = getattr(self.session, "player", None)
            if player is not None:
                key = str(prop_id)
                player.battle_inventory[key] = max(0, player.battle_inventory.get(key, 0) - take_folded)
            if package.is_folded(prop_id):
                bodies.append(encode_on_del_folded(prop_id, take_folded))
            else:
                bodies.append(encode_on_del_item(prop_id))
            remaining -= take_folded
        if remaining > 0:
            self.session._log("      [BATTLE] discard internal underflow prop=%s" % prop_id)
            return b""
        drop_eid, create_body = self._spawn_drop(props, prop_id, count)
        bodies.insert(0, create_body)
        bodies.append(encode_on_discard_prop(drop_eid, prop_id))
        for body in bodies:
            self.session.enqueue(body)
        self.session._log(
            "      [BATTLE] discard prop=%s count=%s -> eid=%s" % (prop_id, count, drop_eid)
        )
        return b""


def register(session):
    mod = DiscardModule(session)
    mod.start()
    return mod