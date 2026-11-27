"""Byte-level tests for RO-059 create_entity / leave_aoi / update_property / entity_method.

Fixtures marked CAPTURED come from RO-056 live gateway hex or documented offline samples.
Golden files pin the verified encoder layout for Plane / DtsProp / Robot / methods where
no independent live hex was recorded. This is private-gateway framing evidence, not an
original-server compatibility claim.
"""

from __future__ import annotations

import struct
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_hex(name: str) -> bytes:
    text = (FIXTURES / name).read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return bytes.fromhex(text)


def test_legacy_ce_switches_not_consulted(bf, monkeypatch):
    """CE_PROPS / CE_PREFIX / CE_INDEX / CE_DIR / CE_MASK / CE_ENTER_AOI must not change layout."""
    base = bf.debug_command("space")
    for key, val in (
        ("CE_PROPS", "on"),
        ("CE_PREFIX", "on"),
        ("CE_INDEX", "all"),
        ("CE_DIR", "f3"),
        ("CE_MASK", "off"),
        ("CE_ENTER_AOI", "off"),
    ):
        monkeypatch.setenv(key, val)
    assert bf.debug_command("space") == base
    for key in ("CE_PROPS", "CE_PREFIX", "CE_INDEX", "CE_DIR", "CE_MASK", "CE_ENTER_AOI"):
        monkeypatch.delenv(key, raising=False)
    assert bf.debug_command("space") == base


def test_create_entity_space_matches_ro056_capture(bf):
    # CAPTURED: createentity_notes.json live_space_trigger_hex / CREATE_ENTITY_FRAMING.md
    expected = load_hex("space_create.hex")
    got = bf.debug_command("space")
    assert got == expected
    assert got[:1] == b"\x0b"  # enterAoI
    assert got[6:7] == b"\x09"  # createEntity
    assert struct.unpack_from("<I", got, 1)[0] == 20001
    assert struct.unpack_from("<H", got, 7)[0] == 0x0060  # var16 payload length


def test_leave_aoi_matches_ro056_capture(bf):
    # CAPTURED: CREATE_ENTITY_FRAMING.md `leave 20001` -> 0f0400214e0000
    expected = load_hex("leave_aoi_20001.hex")
    assert bf.leave_aoi(20001) == expected
    assert expected == bytes.fromhex("0f0400214e0000")


def test_create_entity_plane_golden(bf):
    expected = load_hex("plane_create.hex")
    got = bf.debug_command("plane")
    assert got == expected
    assert got[:1] == b"\x0b"
    assert struct.unpack_from("<I", got, 1)[0] == bf.PLANE_ID
    # createEntity header: eid + type Plane
    ce = got[6:]
    assert ce[0] == 9
    payload = ce[3:]
    eid, typ = struct.unpack_from("<IH", payload, 0)
    assert eid == bf.PLANE_ID
    assert typ == bf.client_type("Plane")
    # flag, compression, mask_flag after pos(12)+dir(3)
    stream = payload[4 + 2 + 12 + 3 :]
    assert stream[:3] == b"\x00\x00\x01"
    assert len(bf.other_client_props("Plane")) == 8


def test_create_entity_dtsprop_golden(bf):
    expected = load_hex("dtsprop_create.hex")
    got = bf.Match().spawn_prop(1001, 1, (10.0, 20.0, 30.0), 700)
    assert got == expected
    assert struct.unpack_from("<I", got, 1)[0] == 30000
    assert len(bf.other_client_props("DtsProp")) == 10


def test_create_entity_robot_empty_golden(bf):
    expected = load_hex("robot_create_empty.hex")
    got = bf.create_entity(40001, "Robot")
    assert got == expected
    assert bf.client_type("Robot") == 58
    # empty values => full mask, short property body
    ce = got[6:]
    payload = ce[3:]
    stream = payload[4 + 2 + 12 + 3 :]
    assert stream[:3] == b"\x00\x00\x01"
    n = len(bf.other_client_props("Robot"))
    mask_len = (n + 7) // 8
    expected_mask = bytearray(mask_len)
    for i in range(n):
        expected_mask[i >> 3] |= 1 << (i & 7)
    assert stream[3 : 3 + mask_len] == bytes(expected_mask)
    assert stream[3 + mask_len :] == b""


def test_update_property_dts_cur_weapon_captured(bf):
    # CAPTURED/DOCUMENTED: ENTITY_PROPERTY_UPDATE_FORMAT.md section 3
    expected = load_hex("prop_dtsCurWeapon.hex")
    got = bf.update_property("BattleGroundAvatar", "dtsCurWeapon", bf.i32(7))
    assert got == expected
    assert got == bf.prop_update("BattleGroundAvatar", 10003, "dtsCurWeapon", bf.i32(7))
    assert expected == bytes.fromhex("fd0a0013270000d78007000000")


def test_update_property_space_circle_stage_direct(bf):
    """BattleGroundSpace update list is small enough that circleStage uses 0xC0|idx."""
    lst = bf.update_prop_list("BattleGroundSpace")
    idx = [p[0] for p in lst].index("circleStage")
    assert idx <= 60
    got = bf.update_property("BattleGroundSpace", "circleStage", bf.i32(1), eid=20001)
    assert got[0] == 0xC0 | idx
    assert got[1] == 8  # var8 length: eid(4) + i32(4)
    assert struct.unpack_from("<I", got, 2)[0] == 20001
    assert got[6:] == bf.i32(1)


def test_entity_method_on_element_open_golden(bf):
    expected = load_hex("method_onElementOpen.hex")
    args = bf.i32(832) + bf.i8(1)
    got = bf.entity_method(20001, "BattleGroundSpace", "onElementOpen", args)
    assert got == expected
    assert got == bf.client_call("BattleGroundSpace", "onElementOpen", 20001, args)
    assert got[0] & 0x80 == 0x80
    assert got[0] < 0xC0
    assert struct.unpack_from("<H", got, 1)[0] == len(got) - 3
    assert struct.unpack_from("<I", got, 3)[0] == 20001


def test_entity_method_show_circle_notify_golden(bf):
    expected = load_hex("method_showCircleNotify.hex")
    got = bf.entity_method(20001, "BattleGroundSpace", "showCircleNotify", bf.i32(1))
    assert got == expected


def test_create_entity_list_counts_match_ro056_notes(bf):
    assert len(bf.other_client_props("BattleGroundSpace")) == 92
    assert len(bf.other_client_props("Plane")) == 8
    assert len(bf.update_prop_list("BattleGroundSpace")) == 95
    assert len(bf.update_prop_list("Plane")) == 11


def test_module_documents_legacy_ce_switches(bf):
    doc = bf.__doc__ or ""
    for name in ("CE_PROPS", "CE_PREFIX", "CE_INDEX", "CE_DIR"):
        assert name in doc
    assert "Legacy experiment" in doc
    # Runtime no longer reads the switches.
    assert "CE_MASK" not in bf.prop_data.__code__.co_names
    assert "CE_DIR" not in bf._direction.__code__.co_names
    assert "CE_INDEX" not in bf.prop_index.__code__.co_names
    assert "CE_ENTER_AOI" not in bf.create_entity.__code__.co_names
