"""Shared readers and request builders for the lobby_new gateway tests (basename kept unique for
pytest's prepend import mode). Importing it puts bigworld_gateway/server on sys.path, as the
gateway process runs with that directory as its import root."""

import pickle
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATEWAY_SERVER = REPO / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

ADDR = ("10.0.0.7", 5007)


def blob(b):
    """BigWorld STRING/BLOB: u8 length (or 0xFF + u24) + bytes."""
    if isinstance(b, str):
        b = b.encode()
    if len(b) < 255:
        return bytes([len(b)]) + b
    return b"\xff" + struct.pack("<I", len(b))[:3] + b


def read_blob(buf, i=0):
    n = buf[i]
    i += 1
    if n == 0xFF:
        n = int.from_bytes(buf[i:i + 3], "little")
        i += 3
    return bytes(buf[i:i + n]), i + n


def read_py(buf, i=0):
    """PYTHON / PY_DICT argument (pickle in a BLOB). Test-side only, on bytes the gateway built."""
    data, j = read_blob(buf, i)
    return pickle.loads(data), j


def i32(v):
    return struct.pack("<i", v)


def names(calls):
    return [n for n, _a in calls]


def args_of(calls, name):
    """Arguments of every recorded call `name`, in order."""
    return [a for n, a in calls if n == name]


def encode_cell_request(bf, eid, entity, method, args=b""):
    """Client -> server cell call bytes (msgid, payload) that battle_flow.decode_request maps to
    `method` on `entity`: the exact inverse of decode_request (extended index scheme and the
    BattleGroundAvatar EXPOSED_SHIFT from 180). The client-side index itself is still unverified
    on device for the lane 5 methods; this only proves the gateway's own decoder round-trips."""
    tab = bf.exposed_cell(entity)
    raw = [m[0] for m in tab].index(method)
    k = raw
    if entity == "BattleGroundAvatar" and raw + 2 >= 180:
        k = raw + 2
    eff = 62 - (len(tab) + 192) // 255
    head = struct.pack("<I", eid)
    if k < eff:
        return 0x80 | k, head + args
    j = eff + ((k - eff) >> 8)
    return 0x80 + j, head + bytes([(k - eff) & 0xFF]) + args
