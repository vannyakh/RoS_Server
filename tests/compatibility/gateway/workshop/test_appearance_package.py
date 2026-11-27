"""dtsAppearancePackage (DTS_APPEARANCE_PACKAGE3) carries real item counts: ITEM_DATA3 is
{uuid BLOB, itemID INT32, number INT32, info PY_DICT} (extract/entities_out/640_ea6b2959.bin)."""

import importlib
import pickle
import struct
import sys

import pytest

import bwdefs


def _blob(b, i):
    n = b[i]
    if n == 0xFF:
        return b[i + 4:i + 4 + int.from_bytes(b[i + 1:i + 4], "little")], i + 4 + int.from_bytes(b[i + 1:i + 4], "little")
    return b[i + 1:i + 1 + n], i + 1 + n


def decode_pkg(b):
    """-> ([(itemID, number, info)], itemsList count, layoutInfo, capacity)."""
    (count,), i = struct.unpack_from("<I", b, 0), 4
    items = []
    for _ in range(count):
        uuid, i = _blob(b, i)
        assert len(uuid) == 16
        item_id, number = struct.unpack_from("<ii", b, i)
        i += 8
        info, i = _blob(b, i)
        items.append((item_id, number, pickle.loads(info)))
    (items_list,), i = struct.unpack_from("<I", b, i), i + 4
    layout, i = _blob(b, i)
    (cap,), i = struct.unpack_from("<I", b, i), i + 4
    assert i == len(b)
    return items, items_list, pickle.loads(layout), cap


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    module = importlib.reload(importlib.import_module("ros_server"))
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


def test_counts_above_one_survive_and_zero_counts_are_omitted(gw):
    counts = gw._item_counts([{"prop_id": 142091, "number": 2}, {"prop_id": 142092, "number": 0},
                              {"prop_id": 270002}])
    assert counts == {142091: 2, 270002: 1}
    raw = gw._encode_appearance_pkg(bwdefs, list(counts.items()) + [(150000, 0)], 20000)
    items, items_list, layout, cap = decode_pkg(raw)
    assert [(i, n) for i, n, _ in items] == [(142091, 2), (270002, 1)]
    assert all(info == {"ex_tm": 0} for _, _, info in items)
    assert (items_list, layout, cap) == (0, {}, 20000)


def test_plain_ids_still_encode_as_count_one(gw):
    """UNLOCK_ALL=stream passes plain prop ids."""
    items, _, _, cap = decode_pkg(gw._encode_appearance_pkg(bwdefs, [140056, 140057], 64))
    assert [(i, n) for i, n, _ in items] == [(140056, 1), (140057, 1)]
    assert cap == 64
