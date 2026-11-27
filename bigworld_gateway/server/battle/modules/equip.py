"""Weapon slots and dtsCurWeapon via changeDtsWeapon (RO-084)."""

from __future__ import annotations

import struct

import battle_flow as bf
from battle import requests as reqs

CHANGE_WEAPON = "changeDtsWeapon"
AVATAR_ID = bf.AVATAR_ID


def parse_change_weapon(args: bytes) -> tuple[int, bool]:
    data = bytes(args or b"")
    if len(data) < 4:
        return 0, True
    slot = int(struct.unpack_from("<i", data, 0)[0])
    flag = True
    if len(data) >= 5:
        flag = data[4] != 0
    return slot, flag


class EquipModule:
    def __init__(self, session):
        self.session = session
        self.current_slot = 0

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_change_weapon, self._on_change_weapon)
        self.session.equip_module = self
        self.session._equip_cur_slot = 0
        self.session._log("      [BATTLE] equip module started")

    def _package(self):
        return getattr(self.session, "match_package", None)

    def _is_change_weapon(self, msgid, payload):
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return call is not None and call.entity == "BattleGroundAvatar" and call.method == CHANGE_WEAPON

    def _wear_slot(self, slot: int):
        package = self._package()
        if package is None:
            self.session._log("      [BATTLE] equip reject (no package)")
            return []
        wid = int(package.gun_slots.get(slot, 0))
        if wid <= 0:
            self.session._log("      [BATTLE] equip reject empty slot=%s" % slot)
            return []
        if bf.prop_type(wid) != "Gun":
            self.session._log("      [BATTLE] equip reject slot=%s not a gun prop=%s" % (slot, wid))
            return []
        self.current_slot = slot
        self.session._equip_cur_slot = slot
        return [
            bf.update_property("BattleGroundAvatar", "dtsWeapon%d" % slot, bf.weapon_item(wid)),
            bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(slot)),
            bf.entity_method(AVATAR_ID, "BattleGroundAvatar", "onWearDtsWeapon", bf.i32(slot)),
        ]

    def _on_change_weapon(self, msgid, payload):
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        if call is None or call.method != CHANGE_WEAPON:
            return b""
        slot, _flag = parse_change_weapon(call.args)
        if slot == 0:
            self.current_slot = 0
            self.session._equip_cur_slot = 0
            bodies = [bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(0))]
            for body in bodies:
                self.session.enqueue(body)
            self.session._log("      [BATTLE] equip unequip -> fist")
            return b""
        if slot not in (1, 2):
            self.session._log("      [BATTLE] equip reject slot=%s" % slot)
            return b""
        bodies = self._wear_slot(slot)
        if not bodies:
            return b""
        for body in bodies:
            self.session.enqueue(body)
        self.session._log("      [BATTLE] equip wear slot=%s" % slot)
        return b""


def register(session):
    mod = EquipModule(session)
    mod.start()
    return mod