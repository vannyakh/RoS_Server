"""RO-079: discard validation, spawn, re-pickup."""

from __future__ import annotations

import struct

from battle.timeline import MatchTimeline

DISCARD_MSGID = 0xBE
MSG_TRY_PICKUP = 0x81


def _player_at_land(session, x=698.0, z=-373.0):
    class _Zone:
        _position_set = True
        pos_x = float(x)
        pos_z = float(z)

    session.zone_module = _Zone()


def _pickup_payload(eid, qty=1, flag=True):
    return struct.pack("<I", int(eid)) + struct.pack("<i", int(qty)) + bytes([1 if flag else 0])


def _discard_payload(prop_id, count, bf):
    return struct.pack("<I", int(bf.AVATAR_ID)) + struct.pack("<ii", int(prop_id), int(count))


def _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 60.0})
    jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    im = items_mod.ItemsModule(session, amounts_path=tiny_amounts)
    pm = props_mod.PropsModule(session, loot_data_path=tiny_loot, timeline=tl, own_timeline=False)
    dm = discard_mod.DiscardModule(session)
    im.start()
    pm.start()
    dm.start()
    tl.start(session)
    clock.advance(0.0)
    _player_at_land(session)


def test_reject_discard_not_owned(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts, bf):
    _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts)
    before = len(session.props_module.props)
    session.dispatch_inbound(DISCARD_MSGID, _discard_payload(1101, 5, bf))
    assert len(session.props_module.props) == before
    assert session.match_package.folded.get(1101, 0) == 0


def test_reject_discard_over_stack(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts, bf):
    _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts)
    session.match_package.folded[1101] = 10
    session.dispatch_inbound(DISCARD_MSGID, _discard_payload(1101, 15, bf))
    assert session.match_package.folded[1101] == 10


def test_reject_discard_zero_count(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts, bf):
    _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts)
    session.match_package.folded[1101] = 10
    session.dispatch_inbound(DISCARD_MSGID, _discard_payload(1101, 0, bf))
    assert session.match_package.folded[1101] == 10


def test_partial_discard_spawns_prop(
    session, sent, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts, bf
):
    _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts)
    session.match_package.folded[1101] = 30
    sent.clear()
    session.dispatch_inbound(DISCARD_MSGID, _discard_payload(1101, 10, bf))
    assert session.match_package.folded[1101] == 20
    drop = next(
        r for r in session.props_module.props.values() if r["prop_id"] == 1101 and r["amount"] == 10
    )
    del_folded = bf.entity_method(
        bf.AVATAR_ID, "BattleGroundAvatar", "onDelDtsFoldedItem", struct.pack("<ii", 1101, 10)
    )
    assert any(s == del_folded for s in sent)
    eid = next(e for e, r in session.props_module.props.items() if r is drop)
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert session.match_package.folded[1101] == 30


def test_discard_equipped_gun_clears_slot(
    session, sent, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts, bf
):
    _boot(session, clock, items_mod, props_mod, discard_mod, jump_mod, tiny_loot, tiny_amounts)
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1001)
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert session.match_package.gun_slots[1] == 1001
    sent.clear()
    session.dispatch_inbound(DISCARD_MSGID, _discard_payload(1001, 1, bf))
    assert session.match_package.gun_slots[1] == 0
    assert any(s == bf.update_property("BattleGroundAvatar", "dtsWeapon1", bf.weapon_item(0)) for s in sent)
    assert any(r["prop_id"] == 1001 and r["amount"] == 1 for r in session.props_module.props.values())