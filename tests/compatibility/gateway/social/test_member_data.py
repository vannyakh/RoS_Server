"""ros_server._hall_team_member: the fields the client needs to draw a teammate."""

import pickle
import struct

import bwdefs


def _fields(blob):
    sizes = {"INT32": 4, "UINT32": 4, "UINT64": 8, "INT64": 8, "INT8": 1, "UINT8": 1, "BOOL": 1}
    pos, out = 0, {}
    for name, kind, _default in bwdefs.Defs().resolve("HALL_TEAM_MEMBER_CLIENT")[1]:
        if kind[0] in ("STRING", "PYTHON"):
            n = blob[pos]
            out[name] = blob[pos + 1:pos + 1 + n]
            pos += 1 + n
        elif kind[0] == "ARRAY":
            n = struct.unpack_from("<I", blob, pos)[0]
            out[name] = list(struct.unpack_from("<%di" % n, blob, pos + 4))
            pos += 4 + 4 * n
        elif kind[0] == "VECTOR2":
            pos += 8
        else:
            out[name] = blob[pos:pos + sizes[kind[0]]]
            pos += sizes[kind[0]]
    assert pos == len(blob)
    return out


def test_member_fields_for_drawing_a_teammate(monkeypatch):
    """UIMain adds [gender] to outGameWeapon and character_scene.initDressInfo reads items 0, 1, 2."""
    import account_link
    import athlete_requests
    import ros_server

    monkeypatch.setattr(account_link, "current_gid", lambda: 77)
    monkeypatch.setattr(account_link, "current",
                        lambda: {"nickname": "A", "is_new": False, "national_flag": "AU", "char_type": 20001})
    gate = ros_server.GateUDP.__new__(ros_server.GateUDP)
    outfit = athlete_requests.Outfit()
    outfit.hall_vehicle = [111, 222]
    gate._outfit = {"addr": outfit}
    fields = _fields(gate._hall_team_member("addr", in_world=False))
    assert pickle.loads(fields["outGameWeapon"]) == [0, 0]
    assert fields["hallVehicleAppearanceList"] == [111, 222]
    assert fields["nationalFlag"] == b"AU"
    assert fields["inWorld"] == bytes(1)
