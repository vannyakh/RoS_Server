"""MatchSession seam: id allocation, ordered sends, timeline, module auto-load (RO-058)."""

from pathlib import Path

import pytest

from battle.session import (
    BOT_ID_BASE,
    FakeClock,
    MatchSession,
    PLANE_ENTITY_ID,
    PROP_ID_BASE,
    SPACE_ENTITY_ID,
    load_battle_modules,
)
from conftest import ADDR


@pytest.fixture
def sent():
    return []


@pytest.fixture
def session(sent):
    return MatchSession(ADDR, lambda body: sent.append(body))


def test_entity_id_ranges(session):
    assert session.alloc_space_id() == SPACE_ENTITY_ID == 20001
    assert session.alloc_plane_id() == PLANE_ENTITY_ID == 20002
    assert session.alloc_prop_id() == PROP_ID_BASE == 30000
    assert session.alloc_prop_id() == 30001
    assert session.alloc_bot_id() == BOT_ID_BASE == 40000
    assert session.alloc_bot_id() == 40001
    # space/plane stay fixed across calls
    assert session.alloc_space_id() == 20001
    assert session.alloc_plane_id() == 20002


def test_ordered_sends(session, sent):
    session.enqueue(b"\x01")
    session.enqueue(b"\x02")
    session.enqueue(b"\x03")
    assert sent == [b"\x01", b"\x02", b"\x03"]


def test_enqueue_during_send_preserves_order(sent):
    """A send callback that enqueues more bytes still drains FIFO."""
    session_box = []

    def send(body):
        sent.append(body)
        if body == b"a" and len(sent) == 1:
            session_box[0].enqueue(b"b")

    session = MatchSession(ADDR, send)
    session_box.append(session)
    session.enqueue(b"a")
    session.enqueue(b"c")
    assert sent == [b"a", b"b", b"c"]


def test_timeline_callbacks_with_fake_clock():
    clock = FakeClock()
    fired = []
    session = MatchSession(ADDR, lambda _b: None, clock=clock)
    session.schedule(1.0, fired.append, "one")
    session.schedule(2.5, fired.append, "two")
    session.schedule(0.5, fired.append, "half")
    assert fired == []
    clock.advance(0.4)
    assert fired == []
    clock.advance(0.2)
    assert fired == ["half"]
    clock.advance(0.5)
    assert fired == ["half", "one"]
    clock.advance(2.0)
    assert fired == ["half", "one", "two"]


def test_timeline_callback_exception_does_not_kill_session():
    clock = FakeClock()
    later = []
    session = MatchSession(ADDR, lambda _b: None, clock=clock, log=lambda *_a, **_k: None)

    def boom():
        raise RuntimeError("timeline boom")

    session.schedule(0.1, boom)
    session.schedule(0.2, later.append, "ok")
    clock.advance(1.0)
    assert later == ["ok"]
    assert not session.closed


def test_load_modules_missing_dir_is_noop(session, tmp_path):
    missing = tmp_path / "no_modules_here"
    assert load_battle_modules(session, missing, log=lambda *_a, **_k: None) == []
    assert session.modules == []
    assert session.dispatch_inbound(0x88, b"\x00" * 4) is None


def test_module_auto_load_registers_inbound(session, tmp_path, sent):
    mod = tmp_path / "demo_door.py"
    mod.write_text(
        "def register(session):\n"
        "    session.on_inbound(0x88, lambda msgid, payload: b'\\xaa\\xbb')\n"
        "    session.space = session.alloc_space_id()\n",
        encoding="utf-8",
    )
    loaded = load_battle_modules(session, tmp_path)
    assert len(loaded) == 1
    assert len(session.modules) == 1
    assert getattr(loaded[0], "register")
    reply = session.dispatch_inbound(0x88, b"\x01\x00\x00\x00\x01")
    assert reply == b"\xaa\xbb"
    session.enqueue(reply)
    assert sent == [b"\xaa\xbb"]
    # unrelated msgid falls through
    assert session.dispatch_inbound(0x89, b"\x00" * 4) is None


def test_module_that_raises_session_survives(session, tmp_path):
    bad = tmp_path / "bad_mod.py"
    bad.write_text(
        "def register(session):\n"
        "    raise RuntimeError('register failed')\n",
        encoding="utf-8",
    )
    good = tmp_path / "good_mod.py"
    good.write_text(
        "def register(session):\n"
        "    session.on_inbound('ping', lambda m, p: b'pong')\n",
        encoding="utf-8",
    )
    logs = []
    loaded = load_battle_modules(session, tmp_path, log=logs.append)
    assert len(loaded) == 1
    assert not session.closed
    assert session.dispatch_inbound(1, b"", method_name="ping") == b"pong"
    assert any("bad_mod.py" in line for line in logs)


def test_module_import_error_session_survives(session, tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("raise SystemExit('nope')\n", encoding="utf-8")
    # SystemExit might be harsh; use plain Exception via syntax that exec_module raises
    broken.write_text("this is not valid python {{{{\n", encoding="utf-8")
    logs = []
    loaded = load_battle_modules(session, tmp_path, log=logs.append)
    assert loaded == []
    assert not session.closed
    assert session.alloc_prop_id() == PROP_ID_BASE


def test_enter_battle_starts_session_without_modules(gw, udp, monkeypatch, tmp_path):
    """No modules dir → MatchSession exists; enter-battle handoff still sends resetEntities."""
    from battle import session as battle_session

    monkeypatch.setattr(battle_session, "DEFAULT_MODULES_DIR", tmp_path / "empty_modules")
    sent = []
    monkeypatch.setattr(udp, "_send_bundle", lambda addr, body, seq, bf: sent.append((body, bf)))
    udp._last_bf[ADDR] = b"\xaa\xbb\xcc\xdd"
    udp._enter_battle(ADDR)
    assert udp._in_battle[ADDR] is True
    assert udp._match_session(ADDR) is not None
    assert udp._match_session(ADDR).modules == []
    assert sent and sent[0][0].startswith(b"\x04\x00")


def test_end_match_session_on_leave(gw, udp, monkeypatch, tmp_path):
    from battle import session as battle_session

    monkeypatch.setattr(battle_session, "DEFAULT_MODULES_DIR", tmp_path / "empty_modules")
    monkeypatch.setattr(udp, "_send_bundle", lambda *a, **k: None)
    monkeypatch.setattr(udp, "_transition_to_athlete", lambda *a, **k: None)
    udp._last_bf[ADDR] = b"\xaa\xbb\xcc\xdd"
    udp._enter_battle(ADDR)
    assert udp._match_session(ADDR) is not None
    match = udp._battle_match(ADDR)
    match.leave = True
    # mirror the leave path in datagram_received
    udp._matches.pop(ADDR, None)
    udp._end_match_session(ADDR)
    udp._in_battle[ADDR] = False
    assert udp._match_session(ADDR) is None
