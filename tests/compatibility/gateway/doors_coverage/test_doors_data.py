"""RO-075: doors.json mirrors map700_elements and legacy Match echoes replies."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
EXTRACT = GATEWAY_SERVER / "extract" / "map700_elements.json"
DOORS = GATEWAY_SERVER / "battle" / "data" / "doors.json"
MSG_OPEN = 0x88
MSG_CLOSE = 0x89
SPACE_ID = 20001


def _observed_elem_ids(elements):
    ids = set()
    for row in elements.get("buildings") or []:
        eid = row.get("elem_id")
        if eid is not None:
            ids.add(int(eid))
    for obs in elements.get("observations") or []:
        if obs.get("elem_id") is not None:
            ids.add(int(obs["elem_id"]))
    return ids


def test_doors_json_covers_all_observed_elem_ids(elements_data):
    observed = _observed_elem_ids(elements_data)
    table = {int(d["elem_id"]) for d in json.loads(DOORS.read_text(encoding="utf-8"))["doors"]}
    assert observed <= table, "missing in doors.json: %s" % sorted(observed - table)


def test_each_door_open_state_produces_on_element_open(bf, doors_data):
    match = bf.Match()
    for door in doors_data["doors"]:
        eid = int(door["elem_id"])
        for state in door.get("open_states") or [doors_data.get("default_open_state", 1)]:
            args = struct.pack("<ib", eid, int(state))
            payload = struct.pack("<I", SPACE_ID) + args
            body = match.handle(MSG_OPEN, payload, log=lambda *_a, **_k: None)
            assert body, "openElement %s state %s" % (eid, state)
            assert bf.client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, args) in body
            assert match.doors.get(eid) == int(state)


def test_door_close_produces_on_element_close(bf, doors_data):
    match = bf.Match()
    for door in doors_data["doors"]:
        eid = int(door["elem_id"])
        args = struct.pack("<i", eid)
        payload = struct.pack("<I", SPACE_ID) + args
        body = match.handle(MSG_CLOSE, payload, log=lambda *_a, **_k: None)
        assert body
        assert match.doors.get(eid) == 0


def test_unknown_elem_still_echoes(bf):
    match = bf.Match()
    unknown = 999001
    args = struct.pack("<ib", unknown, 1)
    payload = struct.pack("<I", SPACE_ID) + args
    body = match.handle(MSG_OPEN, payload)
    assert body
    assert unknown in match.doors


def test_double_door_pair_listed(doors_data):
    by_id = {int(d["elem_id"]): d for d in doors_data["doors"]}
    d0 = by_id[4660]
    assert 4661 in (d0.get("pair_elem_ids") or [])
    assert 4661 in by_id