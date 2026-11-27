"""START handler chain: getOpenMaintenanceFightTipFlag through matchBattleGround / _enter_battle."""

import struct

import pytest

from battle.session import HALL_TEAM_MAP_GROUP
from conftest import ADDR, BF_KEY

RANKED_MODE = 4


def _names(calls):
    return [n for n, _ in calls]


@pytest.mark.parametrize("name", [
    "getOpenMaintenanceFightTipFlag",
    "createHallTeam",
    "getReadyForBattleGround",
    "changeOccupation",
    "reqPayedPartnerRel",
    "matchBattleGround",
])
def test_start_methods_decode_by_name(reqs, name):
    args = struct.pack("<i", RANKED_MODE) if name == "createHallTeam" else (
        struct.pack("<i", 0) if name == "changeOccupation" else (
            b"\x01" if name == "matchBattleGround" else b""
        )
    )
    msgid, payload = reqs.encode_call(name, args)
    assert reqs.decode(msgid, payload) == (name, args)


def test_start_tip_flag(udp, recorder):
    reply = udp._athlete_request(ADDR, "getOpenMaintenanceFightTipFlag", b"")
    assert reply
    assert recorder == [("onGetOpenMaintenanceFightTipFlag", b"\x00" + struct.pack("<i", 0))]


def test_create_hall_team_solo_map_group(udp, recorder):
    reply = udp._athlete_request(ADDR, "createHallTeam", struct.pack("<i", RANKED_MODE))
    assert reply
    assert recorder[0][0] == "onEnterHallTeam"
    assert udp._team[ADDR] == RANKED_MODE
    args = recorder[0][1]
    team_type, = struct.unpack_from("<i", args)
    assert team_type == RANKED_MODE
    assert args.endswith(struct.pack("<i", HALL_TEAM_MAP_GROUP) + b"\x00\x00")


def test_get_ready_matching_triplet(udp, recorder):
    reply = udp._athlete_request(ADDR, "getReadyForBattleGround", b"")
    assert reply
    assert _names(recorder) == ["syncReadyState", "syncMatchState", "syncMatchingProgress"]
    state, = struct.unpack_from("<h", recorder[1][1])
    assert state == 1


def test_intermediate_calls_accepted_without_reply(udp):
    assert udp._athlete_request(ADDR, "changeOccupation", struct.pack("<i", 0)) == b""
    assert udp._athlete_request(ADDR, "reqPayedPartnerRel", b"") == b""


def test_match_schedules_enter_battle_and_entering_state(gw, udp, recorder, monkeypatch, gateway_loop):
    scheduled = []

    def fake_later(delay, fn, *args):
        scheduled.append((delay, fn, args))

    monkeypatch.setattr(gateway_loop, "call_later", fake_later)
    reply = udp._athlete_request(ADDR, "matchBattleGround", b"\x01")
    assert reply
    assert _names(recorder) == ["syncMatchState"]
    enter_state, = struct.unpack_from("<h", recorder[0][1])
    assert enter_state == 2
    assert scheduled == [(3.0, udp._enter_battle, (ADDR,))]
    assert udp._handoff_bf[ADDR] == BF_KEY


def test_enter_battle_uses_pinned_bf_key(gw, udp, monkeypatch):
    monkeypatch.setenv("BATTLE_ENTER", "on")
    sent = []
    monkeypatch.setattr(udp, "_send_bundle", lambda addr, body, seq, bf: sent.append((body, bf)))
    udp._handoff_bf[ADDR] = BF_KEY
    udp._last_bf.pop(ADDR, None)
    udp._athlete_request(ADDR, "matchBattleGround", b"\x01")
    udp._enter_battle(ADDR)
    assert udp._in_battle[ADDR] is True
    assert sent and sent[0][0].startswith(b"\x04\x00")
    assert sent[0][1] == BF_KEY


def test_full_start_chain_names(udp, recorder, monkeypatch, gateway_loop):
    monkeypatch.setattr(gateway_loop, "call_later", lambda *a: None)
    for name, args in (
        ("getOpenMaintenanceFightTipFlag", b""),
        ("createHallTeam", struct.pack("<i", RANKED_MODE)),
        ("getReadyForBattleGround", b""),
        ("changeOccupation", struct.pack("<i", 0)),
        ("reqPayedPartnerRel", b""),
        ("matchBattleGround", b"\x01"),
    ):
        udp._athlete_request(ADDR, name, args)
    assert _names(recorder) == [
        "onGetOpenMaintenanceFightTipFlag",
        "onEnterHallTeam",
        "syncReadyState",
        "syncMatchState",
        "syncMatchingProgress",
        "syncMatchState",
    ]