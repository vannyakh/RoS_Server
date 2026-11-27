"""RO-066: DtsProp spawn, tryPickUp validation, double-pickup reject."""

from __future__ import annotations

import struct

from battle.timeline import MatchTimeline

MSG_TRY_PICKUP = 0x81


def _player_at_land(session, x=698.0, z=-373.0):
    """Stub zone position so pickup range checks see the evidenced land point."""

    class _Zone:
        _position_set = True
        pos_x = float(x)
        pos_z = float(z)

    session.zone_module = _Zone()


def _pickup_payload(eid, args=b"\x01\x00\x00\x00\x01"):
    return struct.pack("<I", int(eid)) + args


def test_play_phase_spawns_props(session, sent, clock, props_mod, jump_mod, tiny_loot):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 60.0})
    jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    mod = props_mod.PropsModule(session, loot_data_path=tiny_loot, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)
    clock.advance(0.0)
    assert len(mod.props) == 2
    assert len(sent) == 2
    assert all(s[:1] == b"\x0b" for s in sent)


def test_pickup_gun_at_range(session, sent, clock, props_mod, jump_mod, tiny_loot, bf):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 10.0})
    jm = jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    jm.land_pos = (698.0, -677.0, -373.0)
    mod = props_mod.PropsModule(session, loot_data_path=tiny_loot, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)
    clock.advance(0.0)
    _player_at_land(session)
    eid = next(iter(mod.props))
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid not in mod.props
    assert any(s == bf.leave_aoi(eid) for s in sent)
    assert any(
        bf.entity_method(bf.AVATAR_ID, "BattleGroundAvatar", "onPickUpPropEntity") == s
        for s in sent
    )


def test_double_pickup_rejected(session, clock, props_mod, jump_mod, tiny_loot):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 10.0})
    jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    mod = props_mod.PropsModule(
        session, loot_data_path=tiny_loot, timeline=tl, own_timeline=False
    )
    mod.start()
    tl.start(session)
    clock.advance(0.0)
    _player_at_land(session)
    eid = next(iter(mod.props))
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid not in mod.props


def test_pickup_out_of_range_rejected(session, sent, clock, props_mod, tiny_loot):
    import json

    data = {
        "map_id": 700,
        "pickup_range_xz": 0.5,
        "entries": [
            {"prop_id": 1001, "amount": 1, "x": 1000.0, "y": -677.0, "z": 1000.0},
        ],
    }
    path = tiny_loot.parent / "far.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 10.0})
    mod = props_mod.PropsModule(session, loot_data_path=path, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)
    clock.advance(0.0)
    eid = next(iter(mod.props))
    sent.clear()
    session.dispatch_inbound(MSG_TRY_PICKUP, _pickup_payload(eid))
    assert eid in mod.props
    assert sent == []