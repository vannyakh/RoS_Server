"""Safe zone from the client's circle parameters (battle_flow ZONE_*), ported from the legacy
battle_flow zone that passed on LDPlayer. Starts on landing, white circle toward the player, waits,
shrinks in 1 s steps, ZONE_DAMAGE cadence, death -> results, surviving the last circle -> victory."""

import pytest


@pytest.fixture
def zone(session, zone_mod, monkeypatch):
    monkeypatch.setenv("ZONE_SOURCE", "client")
    mod = zone_mod.ZoneModule(session)
    mod.start()
    return mod


def test_stages_are_the_client_values(zone_mod, bf):
    stages = zone_mod.client_stages(scale=1.0)
    assert len(stages) == len(bf.ZONE_STAGES) == 8
    first, second = stages[0], stages[1]
    wait, shrink, radius = bf.ZONE_STAGES[0]
    assert (first["delay"], first["rest_seconds"], first["shrink_seconds"], first["white_radius"]) == (0.0, wait, shrink, radius)
    assert second["delay"] == wait + shrink                     # the next stage follows the shrink
    assert (first["poison_amount"], first["poison_every"]) == bf.ZONE_DAMAGE[0]
    assert zone_mod.client_stages(scale=0.1)[1]["delay"] == pytest.approx((wait + shrink) * 0.1)


def test_zone_starts_on_landing_with_fight_status(session, zone, bf, sent, clock):
    clock.advance(30.0)
    assert sent == []                                            # nothing before the player lands
    session.flow.enter("ground", "landed")
    fight = bf.update_property("BattleGroundSpace", "gameStatus", bf.i32(bf.GS_FIGHT), eid=session.space_id)
    assert sent[0] == fight
    (cx, cz), r = bf.ZONE_INIT
    assert bf.update_property("BattleGroundSpace", "blueCircleRadius", bf.i32(int(r)), eid=session.space_id) in sent
    clock.advance(0.0)
    assert zone.current_stage()["circle_stage"] == 1


def test_white_circle_is_aimed_at_the_player_and_inside_the_blue(session, zone, bf, sent, clock):
    zone.track_position(0.0, 0.0)
    session.flow.enter("ground")
    clock.advance(0.0)
    (bx, bz), br = bf.ZONE_INIT
    radius = bf.ZONE_STAGES[0][2]
    wx, wz = bf._toward((bx, bz), (0.0, 0.0), br - radius)   # legacy rule: toward the player, inside the blue
    white = bf.update_property("BattleGroundSpace", "whiteCircleCenter", bf.vec2(float(wx), float(wz)),
                               eid=session.space_id)
    assert white in sent
    assert bf.update_property("BattleGroundSpace", "whiteCircleRadius", bf.i32(radius), eid=session.space_id) in sent


def test_shrink_moves_the_blue_circle_onto_the_white_one(session, zone_mod, bf, clock, monkeypatch):
    monkeypatch.setenv("ZONE_SOURCE", "client")
    monkeypatch.setattr(bf, "ZONE_TIME_SCALE", 0.01)            # 270 s wait + 180 s shrink -> 4.5 s
    zone = zone_mod.ZoneModule(session)
    zone.start()
    start_r = zone._blue_radius
    session.flow.enter("ground")
    wait, shrink, radius = bf.ZONE_STAGES[0]
    clock.advance(wait * 0.01 + shrink * 0.01 / 2)
    assert radius < zone._blue_radius < start_r                  # half way through the shrink
    clock.advance(shrink * 0.01 / 2 + 0.001)
    assert zone._blue_radius == pytest.approx(radius)
    assert zone.current_stage()["circle_stage"] == 2             # the next stage started after the shrink


def test_zone_damage_follows_the_stage_cadence_and_kills(session, zone, results_mod, bf, clock):
    results = results_mod.register(session)
    session.flow.enter("ground")
    clock.advance(0.0)
    zone.track_position(1.0e6, 1.0e6)                           # far outside the blue circle
    amount, every = bf.ZONE_DAMAGE[0]
    hp0 = zone.player_hp
    zone._poison_tick_once()
    assert zone.player_hp == hp0 - amount and zone._in_poison is True
    zone._poison_tick_once()
    assert zone.player_hp == hp0 - amount                       # not again before `every` seconds
    clock.advance(every)
    zone._poison_tick_once()
    assert zone.player_hp == hp0 - 2 * amount
    zone.player_hp = amount
    clock.advance(every)
    zone._poison_tick_once()
    assert zone.player_hp == 0 and results.ended is True
    assert session.flow.stage == "results" and session.flow.victory is False


def test_surviving_the_last_circle_is_a_victory(session, zone, results_mod, bf, clock):
    results = results_mod.register(session)
    session.flow.enter("ground")
    clock.advance(0.0)
    zone._shrink_step((0.0, 0.0), 100.0, (0.0, 0.0), 0, 1.0, True)
    assert zone.closed_zone is True and results.ended is True
    assert session.flow.victory is True and session.flow.placement == 1
