"""Pickle readers for Convert gateway tests."""

import pickle
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ADDR = ("10.0.0.4", 5000)


def read_blob(buf, i=0):
    n = buf[i]
    i += 1
    if n == 0xFF:
        n = int.from_bytes(buf[i:i + 3], "little")
        i += 3
    return buf[i:i + n], i + n


def read_py(buf, i=0):
    data, j = read_blob(buf, i)
    return pickle.loads(data), j


def query_convert(udp, classify=1907):
    return udp._athlete_request(ADDR, "queryAvailableConvertItem", struct.pack("<i", classify))


def convert_item(udp, convert_id, times):
    return udp._athlete_request(ADDR, "convertItem", struct.pack("<ii", convert_id, times))