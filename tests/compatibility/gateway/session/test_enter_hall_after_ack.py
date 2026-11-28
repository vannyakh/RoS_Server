"""enterHall waits for the client to ACK the whole onLogin/lobby bundle. Sent 0.2 s after it while
the client was still busy with that bundle, enterHall crashed Athlete._realEnterHall
('NoneType' object has no attribute 'GetComponent') and the lobby never loaded (device, 2026-11-27)."""

import time

from conftest import ADDR


class _Loop:
    def __init__(self):
        self.later = []

    def call_later(self, delay, cb, *args):
        self.later.append((delay, cb, args))


def _run(udp, monkeypatch, deadline):
    loop = _Loop()
    monkeypatch.setattr("asyncio.get_event_loop", lambda: loop)
    sent = []
    monkeypatch.setattr(udp, "_send_bundle", lambda addr, body, cseq, key: sent.append(body))
    udp._send_enter_hall_after_ack(ADDR, b"HALL", b"k" * 16, 10, deadline)
    return loop, sent


def test_enter_hall_waits_until_lobby_bundle_is_acked(udp, monkeypatch):
    udp._unacked_packets[ADDR] = {8: {}, 9: {}, 12: {}}       # 12 is newer than the bundle
    loop, sent = _run(udp, monkeypatch, time.time() + 20)
    assert sent == [] and len(loop.later) == 1                # still waiting
    udp._unacked_packets[ADDR] = {12: {}}                    # bundle ACKed
    _delay, cb, args = loop.later.pop()
    cb(*args)
    assert sent == [b"HALL"] and loop.later == []


def test_enter_hall_is_sent_at_the_deadline(udp, monkeypatch, capsys):
    udp._unacked_packets[ADDR] = {9: {}}
    loop, sent = _run(udp, monkeypatch, time.time() - 1)
    assert sent == [b"HALL"] and loop.later == []
    assert "deadline, 1 unacked" in capsys.readouterr().out
