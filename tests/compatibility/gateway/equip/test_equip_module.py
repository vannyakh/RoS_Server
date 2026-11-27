"""RO-084: slot wear and swap."""

from __future__ import annotations

import struct

import battle_flow as bf


def _boot(session, items_mod, equip_mod, tiny_amounts):
    im = items_mod.ItemsModule(session, amounts_path=tiny_amounts)
    em = equip_mod.EquipModule(session)
    im.start()
    em.start()
    pkg = session.match_package
    pkg.gun_slots[1] = 1001
    pkg.gun_slots[2] = 1002


def test_reject_equip_empty_slot(session, items_mod, equip_mod, tiny_amounts, reqs):
    _boot(session, items_mod, equip_mod, tiny_amounts)
    session.match_package.gun_slots[2] = 0
    frame = reqs.encode_call("BattleGroundAvatar", "changeDtsWeapon", bf.AVATAR_ID, struct.pack("<iB", 2, 1))
    msgid, payload, _ = reqs.split_frame(frame)
    session.dispatch_inbound(msgid, payload)
    assert session.equip_module.current_slot == 0


def test_wear_slot_uses_ro059_encoder(session, sent, items_mod, equip_mod, tiny_amounts, reqs):
    _boot(session, items_mod, equip_mod, tiny_amounts)
    sent.clear()
    frame = reqs.encode_call("BattleGroundAvatar", "changeDtsWeapon", bf.AVATAR_ID, struct.pack("<iB", 2, 1))
    msgid, payload, _ = reqs.split_frame(frame)
    session.dispatch_inbound(msgid, payload)
    assert session.equip_module.current_slot == 2
    assert any(s == bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(2)) for s in sent)
    assert any(
        s == bf.entity_method(bf.AVATAR_ID, "BattleGroundAvatar", "onWearDtsWeapon", bf.i32(2)) for s in sent
    )
    assert any(
        s == bf.update_property("BattleGroundAvatar", "dtsWeapon2", bf.weapon_item(1002)) for s in sent
    )


def test_reject_non_gun_slot_state(session, items_mod, equip_mod, tiny_amounts, reqs):
    _boot(session, items_mod, equip_mod, tiny_amounts)
    session.match_package.gun_slots[1] = 1101
    frame = reqs.encode_call("BattleGroundAvatar", "changeDtsWeapon", bf.AVATAR_ID, struct.pack("<iB", 1, 1))
    msgid, payload, _ = reqs.split_frame(frame)
    session.dispatch_inbound(msgid, payload)
    assert session.equip_module.current_slot == 0