"""Shared data readers and request builders for the Supply gateway tests (imported by the test
modules and conftest.py; basename kept unique for pytest's prepend import mode)."""


import json
import pickle
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATEWAY_SERVER = REPO / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

SUPPLEMENT_INFO = GATEWAY_SERVER / "extract" / "supplement_info.json"
SUPPLEMENT_PROPS = GATEWAY_SERVER / "extract" / "supplement_props.json"
# Client enum names for the KIND field (supplement_utils.SupplementKindEnum), dumped with the
# lobby reference data: data/reference/original_lobby.json "supply"[].kind, keyed by box id.
ORIGINAL_LOBBY = REPO / "data" / "reference" / "original_lobby.json"

ADDR = ("10.0.0.3", 5000)


def raw_info():
    """supplement_info.json as stored on disk (before athlete_requests adds NEXT_BUY_TIMES_PRICE)."""
    return {int(k): v for k, v in json.loads(SUPPLEMENT_INFO.read_text(encoding="utf-8")).items()}


def kind_names():
    """{box id: client SupplementKindEnum name} from the lobby reference dump."""
    rows = json.loads(ORIGINAL_LOBBY.read_text(encoding="utf-8"))["supply"]
    return {int(r["id"]): r["kind"] for r in rows}


def read_blob(buf, i=0):
    """BigWorld STRING/BLOB at buf[i:] -> (bytes, next index)."""
    n = buf[i]
    i += 1
    if n == 0xFF:
        n = int.from_bytes(buf[i:i + 3], "little")
        i += 3
    return buf[i:i + n], i + n


def read_py(buf, i=0):
    """Pickled PYTHON argument at buf[i:] -> (object, next index)."""
    data, j = read_blob(buf, i)
    return pickle.loads(data), j



def open_box(udp, sid, currency, watch_ad=0):
    return udp._athlete_request(ADDR, "openSupplyBox",
                                struct.pack("<iiI", sid, currency, 0) + struct.pack("<b", watch_ad))


def open_multi(udp, sid, currency):
    return udp._athlete_request(ADDR, "openMultipleSupplyBox", struct.pack("<iiI", sid, currency, 0))


def open_free(udp, sid):
    return udp._athlete_request(ADDR, "openSupplyBoxFree", struct.pack("<i", sid))
