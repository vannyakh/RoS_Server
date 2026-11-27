"""One result writer per match (results.py): RoS_Server when linked, match_results.jsonl only when not
linked, and Quit Game recorded once without the result screens."""

import json

import pytest


@pytest.fixture
def local_file(tmp_path, monkeypatch):
    import match_results

    path = tmp_path / "match_results.jsonl"
    monkeypatch.setattr(match_results, "PATH", str(path))
    return path


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_not_linked_saves_one_local_line(session, results_mod, local_file, monkeypatch):
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: None)
    mod = results_mod.register(session)
    session.flow.set_slots(humans=1, bots=9)
    session.flow.enter("waiting")
    mod.eliminate_player(reason="zone")
    mod.eliminate_player(reason="zone")                     # already ended: no second record
    rows = _lines(local_file)
    assert len(rows) == 1
    assert (rows[0]["rank"], rows[0]["total"], rows[0]["won"], rows[0]["cause"]) == (10, 10, False, "zone")


def test_linked_records_on_ros_server_only(session, results_mod, local_file, monkeypatch):
    sent = []
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: sent.append(r) or {"rank_score": 5})
    mod = results_mod.register(session)
    mod.declare_victory(placement=1, kills=3)
    assert len(sent) == 1 and _lines(local_file) == []
    assert session.flow.victory is True and session.flow.stage == "results"


def test_quit_records_once_and_moves_the_flow_to_the_lobby(session, results_mod, local_file, monkeypatch, sent):
    reports = []
    monkeypatch.setattr(results_mod.account_link, "record_match", lambda r: reports.append(r) or {"rank_score": 0})
    mod = results_mod.register(session)
    session.flow.set_slots(humans=1, bots=4)
    session.flow.enter("ground")
    before = len(sent)
    mod.record_quit()
    mod.record_quit()
    assert len(reports) == 1 and mod.ended is True
    assert session.flow.stage == "lobby" and session.flow.placement == 5
    assert len(sent) == before                              # no result screen bytes for a quit
