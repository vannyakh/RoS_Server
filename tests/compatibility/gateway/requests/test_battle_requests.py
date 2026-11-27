"""RO-060: named in-battle cell-method decode from RO-057 captures.

Passing these tests is gateway decode coverage only — not original-server
Rules of Survival compatibility.
"""

from __future__ import annotations

import struct

import pytest


def test_open_element_from_capture(reqs, capture_hex, logs):
    lines, log = logs
    frame = capture_hex("open_element_832.hex.txt")
    assert frame == bytes.fromhex("880900214e00004003000001")
    call = reqs.decode_frame(frame, log=log)
    assert call is not None
    assert call.entity_id == 20001
    assert call.entity == "BattleGroundSpace"
    assert call.method == "openElement"
    assert call.args == bytes.fromhex("4003000001")
    elem, state = struct.unpack("<ib", call.args)
    assert (elem, state) == (832, 1)
    assert call.verified is True
    assert lines == []


def test_close_element_from_ro057_sample(reqs, logs):
    """closeElement sample from BATTLE_CLIENT_REQUESTS.md / extract _captures."""
    lines, log = logs
    frame = bytes.fromhex("890800214e000040030000")
    call = reqs.decode_frame(frame, log=log)
    assert call is not None
    assert call.entity_id == 20001
    assert call.method == "closeElement"
    assert struct.unpack("<i", call.args)[0] == 832
    assert lines == []


def test_try_pickup_from_capture(reqs, capture_hex, logs):
    lines, log = logs
    frame = capture_hex("try_pickup_30023.hex.txt")
    call = reqs.decode_frame(frame, log=log)
    assert call is not None
    assert call.entity_id == 30023
    assert call.entity == "DtsProp"
    assert call.method == "tryPickUp"
    assert call.args == bytes.fromhex("0100000001")
    assert lines == []


def test_request_get_off_plane_shift_and_length_quirk(reqs, capture_hex, logs):
    """Wire sub 0x13 → client idx 79 → EXPOSED_SHIFT → raw 77; keep ffffffff args.

    RO-057 capture note: .def signature is empty but the gateway logged payload
    ``0000000013ffffffff`` (args=ffffffff). The comment file's ``full_message_hex``
    writes length ``0800`` while that payload is 9 bytes — honor the logged
    payload / ``bundle_peer`` form, not the inconsistent length nibble.
    """
    lines, log = logs
    frame_doc = capture_hex("request_get_off_plane.hex.txt")
    assert frame_doc == bytes.fromhex("bc08000000000013ffffffff")

    # Payload form as logged next to the decode line / extract _captures.
    payload = bytes.fromhex("0000000013ffffffff")
    call = reqs.decode(0xBC, payload, log=log)
    assert call is not None
    assert call.entity_id == 0
    assert call.entity == "BattleGroundAvatar"
    assert call.method == "requestGetOffPlane"
    assert call.args == b"\xff\xff\xff\xff"
    assert call.verified is True

    # Framed with a length that matches the 9-byte payload (capture length quirk).
    framed = bytes([0xBC]) + struct.pack("<H", 9) + payload
    call2 = reqs.decode_frame(framed, log=log)
    assert call2 == call

    # Length-8 framing drops the last 0xff; still decodes the method name safely.
    call3 = reqs.decode_frame(frame_doc, log=log)
    assert call3 is not None
    assert call3.method == "requestGetOffPlane"
    assert call3.args == b"\xff\xff\xff"
    assert lines == []


def test_choose_parachute_and_glider_by_name(reqs, logs):
    """Unverified in RO-057 extract; still decode by name via client index + shift."""
    lines, log = logs
    para = reqs.encode_call("BattleGroundAvatar", "chooseParachute", 0)
    glider = reqs.encode_call("BattleGroundAvatar", "chooseGlider", 0)
    # Extended Avatar: msgid 0xBC, client sub 130 / 131 after eid u32.
    assert para[0] == 0xBC
    assert glider[0] == 0xBC
    assert para[7] == 130
    assert glider[7] == 131

    c1 = reqs.decode_frame(para, log=log)
    c2 = reqs.decode_frame(glider, log=log)
    assert c1 is not None and c1.method == "chooseParachute" and c1.args == b""
    assert c2 is not None and c2.method == "chooseGlider" and c2.args == b""
    assert c1.verified is False and c2.verified is False
    assert lines == []


def test_msg_0xbc_is_cell_method_not_position(reqs, logs):
    """0xBC sample from msg_0xbc_0xbd_samples → onRecvClientFPS, not xyz."""
    lines, log = logs
    # onRecvClientFPS(30): bc090000000000e71e000000
    frame = bytes.fromhex("bc090000000000e71e000000")
    call = reqs.decode_frame(frame, log=log)
    assert call is not None
    assert call.method == "onRecvClientFPS"
    assert call.args == struct.pack("<i", 30)
    tracker = reqs.PositionTracker()
    # Feeding 0xBC into the position path must not invent coordinates.
    reqs.decode_position(0xBC, call.args, tracker=tracker, log=log)
    assert tracker.status == "unknown"
    assert tracker.last is None


def test_client_interface_msg3_position_unknown(reqs, logs):
    lines, log = logs
    tracker = reqs.PositionTracker()
    fake = b"\x00" * 20
    assert reqs.decode_position(reqs.CLIENT_INTERFACE_POSITION_MSG, fake, tracker=tracker, log=log) is None
    assert tracker.status == "unknown"
    assert tracker.last is None
    assert tracker.last_raw == fake
    assert any("layout=unknown" in line for line in lines)
    # Second note: still unknown, no extra log spam.
    n = len(lines)
    reqs.decode_position(3, fake, tracker=tracker, log=log)
    assert len(lines) == n


@pytest.mark.parametrize(
    "blob,label",
    [
        (b"", "empty"),
        (b"\x88", "msgid_only"),
        (b"\x88\x09\x00", "len_without_payload"),
        (b"\x88\x09\x00\x21\x4e", "truncated_eid"),
        (bytes([0xBC, 0x05, 0x00]) + b"\x00\x00\x00\x00", "extended_missing_sub"),
    ],
)
def test_truncated_never_raises(reqs, logs, blob, label):
    lines, log = logs
    assert reqs.decode_frame(blob, log=log) is None
    assert len(lines) == 1, label


def test_oversized_payload_never_raises(reqs, logs):
    lines, log = logs
    # Declared length huge vs available bytes → truncated frame path.
    blob = bytes([0x88, 0xFF, 0xFF]) + b"\x00" * 8
    assert reqs.decode_frame(blob, log=log) is None
    assert len(lines) == 1
    # Explicit oversized decode on a too-long payload buffer.
    reqs.reset_log_state()
    lines.clear()
    huge = b"\x00" * (reqs.MAX_VAR16_LEN + 8)
    assert reqs.decode(0x88, huge, log=log) is None
    assert len(lines) == 1


def test_unknown_msgid_and_index_log_once(reqs, logs):
    lines, log = logs
    # Outside cell-method range.
    assert reqs.decode(0x01, b"\x00\x00\x00\x00", log=log) is None
    assert reqs.decode(0x01, b"\x00\x00\x00\x00", log=log) is None
    assert sum("unknown msgid" in x for x in lines) == 1

    # Extended Avatar index past the table.
    reqs.reset_log_state()
    lines.clear()
    payload = struct.pack("<I", 0) + bytes([0xFF]) + b"\x00" * 4
    # msgid 0xBF = eff+3 path → very large k after shift
    assert reqs.decode(0xBF, payload, log=log) is None
    assert reqs.decode(0xBF, payload, log=log) is None
    assert sum("unknown" in x for x in lines) == 1


def test_encode_roundtrip_open_element(reqs):
    frame = reqs.encode_call(
        "BattleGroundSpace",
        "openElement",
        20001,
        struct.pack("<ib", 832, 1),
    )
    assert frame == bytes.fromhex("880900214e00004003000001")
    call = reqs.decode_frame(frame)
    assert call.method == "openElement"
