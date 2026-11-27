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
