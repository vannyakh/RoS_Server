"""RO-071: gameEnd, onBattleGroundResult, record_match, session teardown, lobby callback."""

from __future__ import annotations

import os
import struct

import pytest

RESULTS_LOBBY_DELAY = float(os.environ.get("RESULTS_LOBBY_DELAY", "3.0"))


def test_record_match_called_once_on_death(session, sent, clock, results_mod, solo_fill_mod, monkeypatch):
    reports = []

    def fake_record(report):
        reports.append(report)
        return {"rank_score": 10, "records": []}

    monkeypatch.setattr(results_mod.account_link, "record_match", fake_record)

    session.solo_fill = solo_fill_mod.load_solo_fill()
    lobby = []

    def ret():
        lobby.append(1)

    session.return_to_lobby = ret

    mod = results_mod.register(session)
    mod.counters.kills = 2
    mod.eliminate_player(placement=8)

    assert mod.ended
    assert len(reports) == 1
    assert reports[0]["placement"] == 8
    assert reports[0]["kills"] == 2
    assert reports[0]["deaths"] == 1
    assert reports[0]["team_mode"] == "solo"
    assert len(sent) >= 2

    mod.eliminate_player(placement=1)
    assert len(reports) == 1

    clock.advance(RESULTS_LOBBY_DELAY)
    assert lobby == [1]
    assert session.closed


def test_victory_sends_game_end_and_result(session, sent, clock, results_mod, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: {"rank_score": 30})

    mod = results_mod.register(session)
    mod.declare_victory(placement=1, kills=5)

    assert mod.ended
    assert len(sent) >= 2
    clock.advance(5.0)
    assert session.closed


def test_suicide_inbound_triggers_end(session, results_mod, bf, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    mod = results_mod.register(session)

    # suicideFromClient is raw BattleGroundAvatar exposed index 61: msg 0xBC (first extended id,
    # eff=60) with sub-byte 61-60=1. It is unshifted: the Avatar shift starts in 151..207
    # (requestGetOffPlane 77 and verifyClientValue 150 arrive unshifted, battle_flow.decode_request).
    msgid = 0xBC
    payload = struct.pack("<I", bf.AVATAR_ID) + bytes([1])
    assert bf.decode_request(msgid, payload)[2] == "suicideFromClient"

    handled = session.dispatch_inbound(msgid, payload)
    assert handled == b""
    assert mod.ended


def test_second_session_starts_clean_after_end(session, sent, clock, results_mod, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    from battle.session import MatchSession

    results_mod.register(session)
    session.results_module.declare_victory()
    clock.advance(5.0)

    sent.clear()
    session2 = MatchSession(session.addr, lambda b: sent.append(b), clock=clock, scheduler=clock)
    results_mod.register(session2)
    assert session2.closed is False
    session2.results_module.declare_victory()
    assert len(sent) >= 2


def test_build_match_report_rank_delta(results_mod):
    rm = results_mod

    c = rm.MatchCounters()
    win = rm.build_match_report(c, placement=1)
    mid = rm.build_match_report(c, placement=8)
    assert win["rank_score_delta"] == 25
    assert mid["rank_score_delta"] == -5


def test_end_match_uses_gate_when_no_callback(session, sent, clock, results_mod, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    calls = []

    class Gate:
        _in_battle = {session.addr: True}
        _athlete_sent = {session.addr: True}
        _hall_entered = {session.addr: True}
        _matches = {session.addr: object()}
        _last_bf = {session.addr: b"\xde\xad"}

        def _end_match_session(self, addr):
            calls.append("end")

        def _transition_to_athlete(self, addr, bf_key):
            calls.append(("transition", bf_key))

    session.gate = Gate()
    session.bf_key = b"\xde\xad"
    mod = results_mod.register(session)
    mod.eliminate_player(placement=6)
    clock.advance(RESULTS_LOBBY_DELAY + 1.0)
    assert calls == ["end", ("transition", b"\xde\xad")]


def test_apply_lobby_return_invokes_gate_hooks(results_mod):
    class Gate:
        def __init__(self):
            self._matches = {"addr": object()}
            self._in_battle = {"addr": True}
            self._athlete_sent = {"addr": True}
            self._hall_entered = {"addr": True}
            self.calls = []

        def _end_match_session(self, addr):
            self.calls.append("end_session")

        def _transition_to_athlete(self, addr, bf_key):
            self.calls.append(("transition", bf_key))

    gate = Gate()
    results_mod.apply_lobby_return(gate, "addr", b"\x01\x02")
    assert gate._in_battle["addr"] is False
    assert "addr" not in gate._matches
    assert "end_session" in gate.calls
    assert ("transition", b"\x01\x02") in gate.calls