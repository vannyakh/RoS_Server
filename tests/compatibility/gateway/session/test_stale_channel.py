"""A BaseApp packet that no session key decrypts belongs to a dead channel (gateway restart or a
second login): the gateway drops it and stops that address's keepalive, so the client times the
channel out and logs in again instead of hanging on the menu/lobby."""

import os

from conftest import ADDR


class _Transport:
    def __init__(self):
        self.sent = []

    def sendto(self, data, addr):
        self.sent.append((data, addr))


def test_undecryptable_packet_is_dropped_and_keepalive_stopped(gw, udp, capsys):
    udp.transport = _Transport()
    gen0 = udp._ka_gens.get(ADDR, 0)
    udp._unacked_packets[ADDR] = {5: {"body": b"x"}}
    junk = os.urandom(24)                       # 24 B, multiple of 8, matches no key
    import loginapp
    while gw._bf_plain_ok(loginapp.custom_bf_decrypt(bytes(gw.CURRENT_BF_KEY or b"\xaa\x6a\x4a\x51"), junk)):
        junk = os.urandom(24)
    udp.datagram_received(junk, ADDR)
    udp.datagram_received(junk, ADDR)
    assert udp._ka_gens.get(ADDR, 0) == gen0                # two strikes: nothing ended yet
    udp.datagram_received(junk, ADDR)
    udp.datagram_received(junk, ADDR)
    out = capsys.readouterr().out
    assert out.count("stale channel") == 1                  # logged once per address, at strike 3
    assert udp._stale_addrs[ADDR][0] == 4
    assert udp._ka_gens[ADDR] == gen0 + 1                   # running keepalive timers stop
    assert ADDR not in udp._unacked_packets
    assert udp.transport.sent == []                          # nothing answered on the dead channel
    assert "BASEAPP RECV" not in out                         # the garbage was not parsed


def test_capture_files_are_off_by_default(gw):
    assert gw.GATE_CAPTURE is False and gw.LOG_RAW is False


def test_silent_client_is_dropped_and_resends_stop(gw, udp, capsys):
    """A crashed client: after PEER_TIMEOUT seconds with no packet the keepalive stops resending."""
    import time
    udp.transport = _Transport()
    gen0 = udp._ka_gens.get(ADDR, 0)
    udp._unacked_packets[ADDR] = {5: {"body": b"x", "time": 0, "fl": 0, "footer_prefix": b""}}
    udp._last_recv[ADDR] = time.time() - gw.PEER_TIMEOUT - 1
    udp._keepalive(ADDR, b"\x01" * 16, gen0)
    out = capsys.readouterr().out
    assert "client gone" in out
    assert udp._ka_gens[ADDR] == gen0 + 1
    assert ADDR not in udp._unacked_packets
    assert udp.transport.sent == []                          # nothing resent to the dead client


def test_recent_client_is_kept(gw, udp):
    import time
    gen0 = udp._ka_gens.get(ADDR, 0)
    udp._last_recv[ADDR] = time.time()
    udp.transport = _Transport()
    try:
        udp._keepalive(ADDR, b"\x01" * 16, gen0)
    except Exception:
        pass                                                 # later keepalive work needs a loop
    assert udp._ka_gens.get(ADDR, 0) == gen0
