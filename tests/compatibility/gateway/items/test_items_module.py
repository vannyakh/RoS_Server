"""RO-077: stacks, partial pickup, package limits."""

from __future__ import annotations

import struct

from battle.timeline import MatchTimeline

MSG_TRY_PICKUP = 0x81


def _player_at_land(session, x=698.0, z=-373.0):
    class _Zone:
        _position_set = True
        pos_x = float(x)
        pos_z = float(z)

    session.zone_module = _Zone()


def _pickup_payload(eid, qty=1, flag=True):
    return struct.pack("<I", int(eid)) + struct.pack("<i", int(qty)) + bytes([1 if flag else 0])


def _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 60.0})
    jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    im = items_mod.ItemsModule(session, amounts_path=tiny_amounts)
    pm = props_mod.PropsModule(session, loot_data_path=tiny_loot, timeline=tl, own_timeline=False)
    im.start()
    pm.start()
    tl.start(session)
    clock.advance(0.0)
    _player_at_land(session)


def test_partial_ammo_pickup_leaves_remainder(
    session, sent, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts, bf
):
    _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts)
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1101)
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid in session.props_module.props
    assert session.props_module.props[eid]["amount"] == 15
    assert session.match_package.folded[1101] == 15
    assert any(
        bf.entity_method(eid, "DtsProp", "syncAmount", bf.i32(15)) == s for s in sent
    )
    assert not any(s == bf.leave_aoi(eid) for s in sent)


def test_full_pickup_after_partial(
    session, sent, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts, bf
):
    _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts)
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1101)
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid not in session.props_module.props
    assert session.match_package.folded[1101] == 30
    assert any(s == bf.leave_aoi(eid) for s in sent)


def test_reject_pickup_over_stack_room(
    session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts
):
    _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts)
    session.match_package.folded[1101] = 30
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1101)
    before = session.props_module.props[eid]["amount"]
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert session.props_module.props[eid]["amount"] == before
    assert session.match_package.folded[1101] == 30


def test_reject_requested_more_than_ground(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts):
    _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts)
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1101)
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid, qty=50))
    assert session.match_package.folded.get(1101, 0) == 15
    assert session.props_module.props[eid]["amount"] == 15


def test_gun_pickup_uses_weapon_path(
    session, sent, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts, bf
):
    _start_items_props(session, clock, items_mod, props_mod, jump_mod, tiny_loot, tiny_amounts)
    eid = next(e for e, r in session.props_module.props.items() if r["prop_id"] == 1001)
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid not in session.props_module.props
    assert session.match_package.gun_slots[1] == 1001
    assert any(
        bf.entity_method(bf.AVATAR_ID, "BattleGroundAvatar", "onWearDtsWeapon", bf.i32(1)) == s
        for s in sent
    )


def test_compute_take_unit(items_mod, tiny_amounts):
    cfg = items_mod.load_item_amounts(tiny_amounts)
    pkg = items_mod.MatchPackage(cfg)
    assert pkg.compute_take(1101, 30, 0) == 15
    pkg.add_folded(1101, 15)
    assert pkg.compute_take(1101, 30, 0) == 15
    pkg.add_folded(1101, 15)
    assert pkg.compute_take(1101, 30, 0) == 0
    assert pkg.compute_take(1101, 30, 3) == 0