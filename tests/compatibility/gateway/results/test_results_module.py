"""RO-071: gameEnd, onBattleGroundResult, record_match, session teardown, lobby callback."""

from __future__ import annotations

import os
import struct

import pytest

RESULTS_LOBBY_DELAY = float(os.environ.get("RESULTS_LOBBY_DELAY", "60"))


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
    assert len(sent) >= 1

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
    assert len(sent) >= 1
    clock.advance(RESULTS_LOBBY_DELAY)
    assert session.closed


def test_suicide_inbound_triggers_end(session, results_mod, bf, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    mod = results_mod.register(session)

    # suicideFromClient (raw exposed index 61) as the client sends it: msg 0xBC (eff=60) with the
    # sub-byte for its wire index under the one shift rule (battle_flow.avatar_wire_index).
    msgid = 0xBC
    wire = bf.avatar_wire_index(61)
    payload = struct.pack("<I", bf.AVATAR_ID) + bytes([wire - 60])
    assert bf.decode_request(msgid, payload)[2] == "suicideFromClient"

    handled = session.dispatch_inbound(msgid, payload)
    assert handled == b""
    assert mod.ended


def test_second_session_starts_clean_after_end(session, sent, clock, results_mod, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    from battle.session import MatchSession

    results_mod.register(session)
    session.results_module.declare_victory()
    clock.advance(RESULTS_LOBBY_DELAY)

    sent.clear()
    session2 = MatchSession(session.addr, lambda b: sent.append(b), clock=clock, scheduler=clock)
    results_mod.register(session2)
    assert session2.closed is False
    session2.results_module.declare_victory()
    assert len(sent) >= 1


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

def test_result_uses_the_client_layout(session, sent, clock, results_mod, bf, monkeypatch):
    """Device 2026-11-27: the old 7 fields left the result panel on its placeholder text
    (LINGZI x5, 32000, /120 Teams). The client reads gameType, teamSize, rank, total, bannerID,
    {gid: row}, killerInfo (LOBBY_FINDINGS index 267)."""
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    monkeypatch.setattr(results_mod.account_link, "current_gid", lambda: 4242)
    monkeypatch.setattr(results_mod, "_nickname", lambda: "QATester")
    session.flow.set_slots(bots=9)
    mod = results_mod.register(session)
    mod.counters.kills = 3
    mod.eliminate_player(placement=4)
    expected = bf.result_call(4, 10, 4242, "QATester", kills=3)
    assert expected in sent


def test_solo_death_sends_no_spectate_die_call(session, sent, results_mod, bf, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    mod = results_mod.register(session)
    mod.eliminate_player(placement=7)
    assert bf.die_call() not in sent
    monkeypatch.setenv("RESULT_DIE_CALL", "on")
    sent.clear()
    mod2 = results_mod.ResultsModule(session)
    mod2.end_match(placement=7, victory=False)
    assert bf.die_call() in sent


def test_lobby_return_waits_for_the_result_screen(session, clock, results_mod, monkeypatch):
    """Returning 3 s after the result left the panel open on top of the lobby."""
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    lobby = []
    session.return_to_lobby = lambda: lobby.append(1)
    mod = results_mod.register(session)
    mod.eliminate_player(placement=5)
    clock.advance(10.0)
    assert lobby == [] and not session.closed
    clock.advance(RESULTS_LOBBY_DELAY)
    assert lobby == [1] and session.closed


def test_result_row_has_the_gold_screen_keys(bf):
    """UIBattlegroundsResultGold.showResult unpacks row['getGPs'] into 5 values and reads
    row['randomGP'], row['nickname'], row['kill'] (Frida disassembly 2026-11-28)."""
    import pickle

    body = bf.result_call(3, 10, 4242, "QATester", kills=2)
    start = body.index(b"\x80\x02")                      # first pickle: the results dict
    results = pickle.loads(body[start:])
    row = results[4242]
    assert len(row["getGPs"]) == 5
    assert (row["randomGP"], row["nickname"], row["kill"]) == (0, "QATester", 2)


def test_result_call_uses_the_measured_client_index():
    """Raw 264 + 3 = 267 ran onBattleGroundGoldBattleResult on device; the client index is raw + 2."""
    import battle_flow as bf
    idx, _n = bf.client_methods("BattleGroundAvatar")
    assert idx["onBattleGroundResult"] == 266
    assert idx["onBattleGroundDie"] == 265


def test_space_leaves_fight_status_before_the_result(session, sent, results_mod, bf, monkeypatch):
    """UIBattlegroundsResult.delayShowResult closes itself when the player is alive and the space is
    in FIGHT (run 3: a winner got no panel). The space goes to END before onBattleGroundResult."""
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    monkeypatch.setattr(results_mod.account_link, "current_gid", lambda: 4242)
    monkeypatch.setattr(results_mod, "_nickname", lambda: "QATester")
    mod = results_mod.register(session)
    mod.declare_victory(placement=1)
    end = bf.update_property("BattleGroundSpace", "gameStatus", bf.i32(bf.GS_END), eid=mod.space_id)
    result = bf.result_call(1, mod._alive_start, 4242, "QATester", kills=0)
    assert bf.GS_END == 4
    assert end in sent and result in sent
    assert sent.index(end) < sent.index(result)


def test_result_row_has_every_key_showresult_subscripts(bf):
    """UIBattlegroundsResult.showResult reads these with row[key] (Frida disassembly 2026-11-28);
    a missing one (run 5: 'randomScore') stops the screen before the member row and the countdown."""
    import pickle

    body = bf.result_call(1, 10, 4242, "QATester", kills=0)
    row = pickle.loads(body[body.index(b"\x80\x02"):])[4242]
    for key in ("gps", "dailyFirstGameReward", "randomGP", "nickname", "kill", "score", "nationalFlag",
                "moveDis", "collectCount", "healTeammate", "randomScore"):
        assert key in row, key
