"""Framed openElement / closeElement bytes for door module tests."""

from __future__ import annotations

import struct


def pack_open(reqs, elem_id, state, *, space_id=20001):
    args = struct.pack("<ib", int(elem_id), int(state))
    frame = reqs.encode_call("BattleGroundSpace", "openElement", space_id, args)
    return frame[0], frame[3:]


def pack_close(reqs, elem_id, *, space_id=20001):
    args = struct.pack("<i", int(elem_id))
    frame = reqs.encode_call("BattleGroundSpace", "closeElement", space_id, args)
    return frame[0], frame[3:]