"""enterHall is held until the client's game thread is responsive (hall_gate.py).

LDPlayer evidence (2026-11-27): when the client blocked 12-16 s loading the tutorial Level right
after the lobby bundle, it ran enterHall as soon as the block ended, before its "Scene" GameObject
existed, and Athlete._realEnterHall failed (AttributeError 'NoneType' ... 'GetComponent', line 711).
The gateway now waits until every reliable packet is ACKed and empty reliable probes are ACKed
promptly for a settle window, then sends enterHall.
"""

import importlib
import struct

import pytest

from conftest import ADDR, BF_KEY


@pytest.fixture
def hg():
    return importlib.import_module("hall_gate")


def test_gate_sends_after_settle_when_client_acks_promptly(hg):
    g = hg.HallGate(0.0, settle=1.0, busy_after=0.25, max_wait=60)
    assert g.step(0.1, 0.1) == hg.WAIT          # lobby bundle in flight
    assert g.step(0.2, None) == hg.PROBE        # all ACKed: start settle, probe
    assert g.step(0.3, 0.05) == hg.WAIT         # probe in flight, still young
    assert g.step(0.4, None) == hg.PROBE
    assert g.step(1.2, None) == hg.SEND
    assert not g.blocked


def test_gate_restarts_settle_after_a_stall(hg):
    g = hg.HallGate(0.0, settle=1.0, busy_after=0.25, max_wait=60)
    assert g.step(0.2, None) == hg.PROBE
    assert g.step(0.5, 0.3) == hg.WAIT          # probe unacked > busy_after: client blocked
    assert g.blocked
    for t in range(1, 14):                      # 13 s block, packets stay unacked
        assert g.step(0.5 + t, 0.3 + t) == hg.WAIT
    assert g.step(14.0, None) == hg.PROBE       # unblocked: settle starts again here
    assert g.step(14.6, None) == hg.PROBE
    assert g.step(15.0, None) == hg.SEND


def test_gate_gives_up_after_max_wait(hg):
    g = hg.HallGate(0.0, settle=1.0, busy_after=0.25, max_wait=5)
    assert g.step(4.9, 4.9) == hg.WAIT
    assert g.step(5.0, 5.0) == hg.SEND


def _decode(loginapp, enc):
    pt = loginapp.custom_bf_decrypt(BF_KEY, enc)
    pkt = pt[:-pt[-1]]
    flags = struct.unpack_from("<H", pkt)[0]
    end = len(pkt)
    if flags & 0x0004:
        end -= 1 + 4 * pkt[-1]
    seq = struct.unpack_from("<I", pkt, end - 4)[0] if flags & 0x0040 else None
    return flags, pkt[2:end - (4 if flags & 0x0040 else 0)], seq


def test_gateway_holds_enter_hall_while_client_is_stalled(gw, udp, monkeypatch, gateway_loop):
    hg = importlib.import_module("hall_gate")
    loginapp = importlib.import_module("loginapp")
    clock = [1000.0]
    monkeypatch.setattr("time.time", lambda: clock[0])
    sent = []
    udp.transport = type("T", (), {"sendto": lambda self, data, addr: sent.append(data)})()
    udp._seq[ADDR] = 40
    udp._last_client_seq[ADDR] = 3
    hall_call = gw.athlete_method("enterHall", b"\x01", quiet=True)

    # Lobby bundle tail (seq 30..39) still unacked: the client stalled mid-bundle.
    udp._unacked_packets[ADDR] = {s: {"fl": 0x5C, "body": b"x", "footer_prefix": b"", "time": 999.0,
                                      "sent": 999.0} for s in range(30, 40)}
    gate = hg.HallGate(999.0)
    gen = udp._ka_gens.get(ADDR, 0)
    for _ in range(10):
        clock[0] += 1.0
        udp._hall_gate_tick(ADDR, hall_call, BF_KEY, gate, gen)
    assert sent == []                                    # nothing while the client is blocked

    udp._unacked_packets[ADDR].clear()                   # client unblocked and ACKed the tail
    udp._hall_gate_tick(ADDR, hall_call, BF_KEY, gate, gen)
    flags, body, seq = _decode(loginapp, sent[-1])
    assert (flags & 0x0050, body, seq) == (0x0050, b"", 40)      # empty reliable probe
    assert 40 in udp._unacked_packets[ADDR]

    udp._unacked_packets[ADDR].clear()                   # probe ACKed promptly
    clock[0] += 0.5
    udp._hall_gate_tick(ADDR, hall_call, BF_KEY, gate, gen)
    assert _decode(loginapp, sent[-1])[1] == b""         # still settling: another probe
    udp._unacked_packets[ADDR].clear()
    clock[0] += 0.6
    udp._hall_gate_tick(ADDR, hall_call, BF_KEY, gate, gen)
    assert _decode(loginapp, sent[-1])[1] == hall_call   # enterHall goes out now


def test_gateway_drops_gate_after_relogin(gw, udp, monkeypatch, gateway_loop):
    hg = importlib.import_module("hall_gate")
    sent = []
    udp.transport = type("T", (), {"sendto": lambda self, data, addr: sent.append(data)})()
    gate = hg.HallGate(0.0, max_wait=0)                  # would send immediately
    old_gen = udp._ka_gens.get(ADDR, 0)
    udp._ka_gens[ADDR] = old_gen + 1                     # new BaseApp login on this address
    udp._hall_gate_tick(ADDR, b"\x00", BF_KEY, gate, old_gen)
    assert sent == []
