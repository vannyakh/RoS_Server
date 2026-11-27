"""RO-064: circle stages, poison detection, and zone fatal handoff."""

from __future__ import annotations

from battle.timeline import MatchTimeline

from conftest import ADDR


def test_in_blue_circle_unit(zone_mod):
    assert zone_mod.in_blue_circle(0, 0, (0, 0), 500)
    assert not zone_mod.in_blue_circle(600, 0, (0, 0), 500)
    stub = type(
        "S",
        (),
        {
            "closed": False,
            "space_id": 20001,
            "_log": lambda *_a, **_k: None,
            "enqueue": lambda *_a, **_k: None,
            "schedule": lambda *_a, **_k: None,
        },
    )()
    mod = zone_mod.ZoneModule(
        stub,
        timeline=MatchTimeline({"warmup": 0, "boarding": 0, "flight": 0, "play": 60}),
        own_timeline=True,
    )
    mod._play_started = True
    mod._blue_center = (0.0, 0.0)
    mod._blue_radius = 100.0
    mod.track_position(0, 0)
    assert not mod.is_in_poison_area()
    mod.track_position(500, 500)
    assert mod.is_in_poison_area()


def test_play_phase_emits_circle_updates(session, sent, clock, bf, zone_mod, tiny_zone_data):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 120.0})
    mod = zone_mod.ZoneModule(session, zone_data_path=tiny_zone_data, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)

    clock.advance(0.0)  # enter play + first stage
    assert mod._play_started
    assert mod.current_stage() is not None
    assert mod.current_stage()["circle_stage"] == 1
    assert any(
        s == bf.update_property("BattleGroundSpace", "blueCircleRadius", bf.i32(500), eid=20001)
        for s in sent
    )
    assert any(
        bf.entity_method(20001, "BattleGroundSpace", "updateCircleRestTime", bf.i32(30)) == s
        for s in sent
    )

    sent.clear()
    clock.advance(5.0)
    assert mod.current_stage()["circle_stage"] == 2
    assert any(
        s == bf.update_property("BattleGroundSpace", "circleStage", bf.i32(2), eid=20001)
        for s in sent
    )


def test_is_in_poison_area_property_toggle(session, sent, clock, bf, zone_mod, tiny_zone_data):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 60.0})
    mod = zone_mod.ZoneModule(session, zone_data_path=tiny_zone_data, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)
    clock.advance(0.0)  # play + stage 0
    mod.track_position(0, 0)
    assert not any(
        s == bf.update_property("BattleGroundAvatar", "isInPoisonArea", bf.i8(1)) for s in sent
    )
    mod.track_position(1000, 1000)
    mod._refresh_poison_flag()
    assert any(
        s == bf.update_property("BattleGroundAvatar", "isInPoisonArea", bf.i8(1)) for s in sent
    )


def test_poison_fatal_calls_results(session, sent, clock, zone_mod, results_mod, tiny_zone_data, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 0.0, "play": 60.0})
    results_mod.register(session)
    mod = zone_mod.ZoneModule(session, zone_data_path=tiny_zone_data, timeline=tl, own_timeline=False)
    mod.start()
    tl.start(session)
    clock.advance(0.0)
    mod.track_position(900, 900)
    clock.advance(1.0)
    clock.advance(1.0)
    assert session.results_module.ended
    assert session.results_module.counters.deaths >= 1