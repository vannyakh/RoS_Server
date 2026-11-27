"""Step 1 of the gameplay restoration: one stage controller, one timeline, one decoder,
and inbound requests reaching the module that owns them (battle/flow.py, battle/session.py)."""

import struct
from pathlib import Path

import pytest


MODULES_DIR = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server" / "battle" / "modules"


@pytest.fixture
def clock():
    from battle.session import FakeClock

    return FakeClock(start=0.0)


@pytest.fixture
def sent():
    return []


@pytest.fixture
def session(sent, clock):
    from battle.session import MatchSession

    return MatchSession(("192.168.1.10", 20001), lambda body: sent.append(body), clock=clock, log=lambda *a, **k: None)


# ---- MatchFlow -----------------------------------------------------------------------------------

def test_flow_moves_forward_only_and_calls_listeners(session):
    from battle.flow import STAGES

    seen = []
    for stage in STAGES:
        session.flow.on_enter(stage, seen.append)
    assert session.flow.enter("waiting") and session.flow.enter("aircraft")
    assert session.flow.enter("waiting") is False          # never back
    assert session.flow.enter("aircraft") is False         # not twice
    assert session.flow.enter("ground", "landed")           # may skip ahead
    assert session.flow.enter("parachute") is False         # a late jump cannot pull a landed player back
    assert seen == ["waiting", "aircraft", "ground"]
    assert session.flow.reached("aircraft") and not session.flow.reached("results")
    with pytest.raises(KeyError):
        session.flow.enter("lobbyy")


def test_flow_follows_the_session_timeline(session, clock):
    session.timeline.durations.update({"warmup": 5.0, "boarding": 2.0, "flight": 10.0, "play": 0.0})
    session.timeline.start(session)
    clock.advance(0.0)
    assert session.flow.stage == "waiting"
    clock.advance(5.0)
    assert session.flow.stage == "aircraft"
    clock.advance(20.0)
    assert session.flow.stage == "aircraft"                 # parachute / ground come from the player


def test_flow_counters_and_summary(session, clock):
    session.flow.set_slots(humans=1, bots=9)
    session.flow.enter("waiting")
    clock.advance(30.0)
    session.flow.add_kill()
    session.flow.add_damage(dealt=120, taken=35)
    session.flow.enter("results")
    s = session.flow.summary()
    assert (s["slots"], s["kills"], s["damage_dealt"], s["damage_taken"]) == (10, 1, 120, 35)
    assert s["survival_seconds"] == 30.0 and s["stages"] == ["waiting", "results"]


# ---- inbound dispatch ----------------------------------------------------------------------------

def test_handler_returning_none_lets_the_next_handler_try(session):
    calls = []
    session.on_inbound(lambda mid, pay: True, lambda mid, pay: calls.append("first") or None)
    session.on_inbound(0xBC, lambda mid, pay: calls.append("second") or b"ok")
    assert session.dispatch_inbound(0xBC, b"") == b"ok"
    assert calls == ["first", "second"]
    assert session.dispatch_inbound(0xBD, b"") is None      # nobody handled it


# ---- one decoder ---------------------------------------------------------------------------------

def test_one_decoder_rule_matches_the_captured_packets():
    import battle.requests as reqs
    import battle_flow as bf

    jump = bytes.fromhex("00000000" "13" "ffffffff")       # request_get_off_plane.hex.txt
    assert bf.decode_request(0xBC, jump)[2] == "requestGetOffPlane"
    assert reqs.EXPOSED_SHIFT_FROM == bf.EXPOSED_SHIFT_FROM and reqs.EXPOSED_SHIFT == bf.EXPOSED_SHIFT
    assert bf.decode_request(0xB4, struct.pack("<I", 0))[2] == "fire"       # unshifted below the start
    for raw in (52, 61, 77, 150, 289, 305):
        assert bf.avatar_raw_index(bf.avatar_wire_index(raw)) == raw


# ---- requests reach their module with every module loaded ----------------------------------------

def test_jump_request_reaches_the_jump_module_with_all_modules_loaded(session, sent, clock, monkeypatch):
    """Regression: results.py used to claim every 0x80-0xBF request, so Jump never reached jump.py."""
    from battle.session import load_battle_modules

    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    load_battle_modules(session, MODULES_DIR, log=lambda *a, **k: None)
    clock.advance(0.0)
    jump = session.jump_module
    jump.in_jump_window = lambda: True                      # the plane's jump area is open
    session.flow.enter("aircraft")

    handled = session.dispatch_inbound(0xBC, bytes.fromhex("00000000" "13" "ffffffff"))
    assert handled is not None
    assert jump.off_plane is True and session.flow.stage == "parachute"
    assert session.results_module.ended is False            # the Jump did not end the match


def test_results_only_claims_the_leave_requests(session, clock):
    import battle_flow as bf
    from battle.session import load_battle_modules

    load_battle_modules(session, MODULES_DIR, log=lambda *a, **k: None)
    clock.advance(0.0)
    other = struct.pack("<I", bf.AVATAR_ID) + bytes([bf.avatar_wire_index(79) - 60])   # markFloor
    session.dispatch_inbound(0xBC, other)
    assert session.results_module.ended is False
    suicide = struct.pack("<I", bf.AVATAR_ID) + bytes([bf.avatar_wire_index(61) - 60])
    session.dispatch_inbound(0xBC, suicide)
    assert session.results_module.ended is True and session.flow.stage == "results"


def test_slots_from_solo_fill_reach_results(session, clock):
    from battle.session import load_battle_modules

    load_battle_modules(session, MODULES_DIR, log=lambda *a, **k: None)
    clock.advance(0.0)
    fill = session.solo_fill
    assert session.flow.slots == fill.human_count + fill.bot_count
    assert session.results_module._alive_start == session.flow.slots
