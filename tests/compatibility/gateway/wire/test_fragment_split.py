"""Reliable fragment framing for large server->client bundles (lobby login bundle).

BigWorld's Bundle::iterator::unpack reads each message header from one packet; only the payload
may continue into the next fragment. A header split across fragments is "Got corrupted message
header" and the client drops the bundle. These tests pin that mercury_frag.split_bundle (used by
GateUDP._send_bundle) never splits a header, and that GateUDP sends the fragments with the
fragment footer [fragBegin][fragEnd][seq] on consecutive sequence numbers.
"""

from __future__ import annotations

import importlib
import struct
from types import SimpleNamespace

import pytest


def var8(msg_id: int, payload: bytes) -> bytes:
    return bytes([msg_id, len(payload)]) + payload


def var16(msg_id: int, payload: bytes) -> bytes:
    return bytes([msg_id]) + struct.pack("<H", len(payload)) + payload


def read_like_bigworld(mf, chunks: list[bytes]) -> list[tuple[int, bytes]]:
    """Model of Bundle::iterator over a fragment chain. Raises on a header that does not fit in
    the packet it starts in (the client's "Not enough data on stream ... for header")."""
    out, ci, off = [], 0, 0
    while ci < len(chunks):
        if off == len(chunks[ci]):
            ci, off = ci + 1, 0
            continue
        cur = chunks[ci]
        kind, param = mf.message_style(cur[off])
        hdr = 1 if kind == mf.FIXED else 1 + param
        if off + hdr > len(cur):
            raise AssertionError(f"header of 0x{cur[off]:02x} split at fragment {ci} offset {off}")
        length = param if kind == mf.FIXED else int.from_bytes(cur[off + 1:off + hdr], "little")
        if kind == mf.VAR and length == (1 << (8 * param)) - 1:
            if off + hdr + 4 > len(cur):
                raise AssertionError(f"extended length of 0x{cur[off]:02x} split at fragment {ci}")
            length = struct.unpack_from("<I", cur, off + hdr)[0]
            hdr += 4
        msg_id, need, data, off = cur[off], length, b"", off + hdr
        while need:
            if off == len(chunks[ci]):
                ci, off = ci + 1, 0
                if ci == len(chunks):
                    raise AssertionError("payload runs past the last fragment")
            take = min(need, len(chunks[ci]) - off)
            data += chunks[ci][off:off + take]
            off, need = off + take, need - take
        out.append((msg_id, data))
    return out


@pytest.fixture
def mf():
    return importlib.import_module("mercury_frag")


def lobby_like_bundle() -> bytes:
    """Entity method calls of mixed size, as in the onLogin + lobby data bundle."""
    body = b"\x04\x00"                                              # resetEntities (fixed 1)
    body += var16(0x80, b"p" * 693)                                 # next header at 698..700
    body += var16(0x81, struct.pack("<I", 10002) + b"h" * 40)       # a blind 700 cut splits it
    for i in range(400):
        n = (i * 37) % 61
        body += var8(0xC0 | (i % 60), struct.pack("<I", 10002) + bytes([i % 251]) * n)
        if i % 7 == 0:
            body += var16(0x80 | (i % 60), struct.pack("<I", 10002) + bytes(300 + i))
    return body


def test_blind_700_byte_cuts_split_headers(mf):
    body = lobby_like_bundle()
    assert mf.header_split_points(body, 700), "fixture must reproduce the old failure"
    blind = [body[i:i + 700] for i in range(0, len(body), 700)]
    with pytest.raises(AssertionError, match="header"):
        read_like_bigworld(mf, blind)


@pytest.mark.parametrize("max_body", [64, 700, 1200])
def test_split_keeps_every_header_in_one_fragment(mf, max_body):
    body = lobby_like_bundle()
    chunks = mf.split_bundle(body, max_body)
    assert b"".join(chunks) == body
    assert all(0 < len(c) <= max_body for c in chunks)
    msgs, tail = mf.parse_messages(body)
    assert tail == len(body)
    assert read_like_bigworld(mf, chunks) == [(body[s], body[s + h:e]) for s, h, e in msgs]


def test_payload_longer_than_a_fragment_spans_fragments(mf):
    body = var8(0xC1, b"x" * 10) + var16(0x81, bytes(range(256)) * 12) + var8(0xC2, b"y")
    chunks = mf.split_bundle(body, 700)
    assert len(chunks) == 5
    assert [m for m, _ in read_like_bigworld(mf, chunks)] == [0xC1, 0x81, 0xC2]


def test_extended_length_stays_with_its_header(mf):
    big = struct.pack("<I", 70000) + b"z" * 70000                   # var16 0xFFFF + int32 length
    body = var16(0x83, b"a" * 691) + bytes([0x82]) + b"\xff\xff" + big
    chunks = mf.split_bundle(body, 700)
    assert chunks[0].endswith(b"a")                                  # cut before the 0x82 header
    assert chunks[1][:3] == b"\x82\xff\xff"
    assert read_like_bigworld(mf, chunks)[1] == (0x82, b"z" * 70000)


def test_unknown_message_tail_falls_back_to_fixed_cuts(mf):
    body = var8(0xC1, b"q" * 20) + b"\x70" + b"?" * 1500             # 0x70 is not a known id
    chunks = mf.split_bundle(body, 700)
    assert b"".join(chunks) == body
    assert all(len(c) <= 700 for c in chunks)


def test_gateway_send_bundle_uses_message_boundaries(mf, monkeypatch):
    """GateUDP._send_bundle on a large body: consecutive seqs, footer [begin][end][seq], acks on
    the first fragment only, unacked copies keep the same footer, and no header is split."""
    monkeypatch.setenv("FRAG_BODY", "700")
    monkeypatch.delenv("FRAG_SPLIT", raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    gw = importlib.import_module("ros_server")
    loginapp = importlib.import_module("loginapp")
    sent = []
    key = b"\x11\x22\x33\x44\x55\x66\x77\x88"
    fake = SimpleNamespace(_in_battle={}, _seq={"a": 8}, _unacked_packets={},
                           transport=SimpleNamespace(sendto=lambda data, addr: sent.append(data)))
    body = lobby_like_bundle()
    gw.GateUDP._send_bundle(fake, "a", body, 3, key)

    chunks = []
    n = len(sent)
    for i, enc in enumerate(sent):
        pt = loginapp.custom_bf_decrypt(key, enc)
        pkt = pt[:-pt[-1]]
        flags = struct.unpack_from("<H", pkt)[0]
        assert flags & 0x0078 == 0x0078                              # on channel, reliable, frag, seq
        end = len(pkt)
        if flags & 0x0004:
            assert i == 0
            assert pkt[-1] == 1 and struct.unpack_from("<I", pkt, end - 5)[0] == 3
            end -= 5
        begin, last, seq = struct.unpack_from("<III", pkt, end - 12)
        assert (begin, last, seq) == (8, 8 + n - 1, 8 + i)
        chunks.append(pkt[2:end - 12])
        stored = fake._unacked_packets["a"][seq]
        assert stored["body"] == chunks[-1]
        assert stored["footer_prefix"] == struct.pack("<III", begin, last, seq)
    assert fake._seq["a"] == 8 + n
    assert b"".join(chunks) == body
    read_like_bigworld(mf, chunks)
