"""Athlete iItemConvert: queryAvailableConvertItem and convertItem."""

import struct

import athlete_requests
from convert_helpers import ADDR, convert_item, query_convert, read_py


def test_query_lists_duplicate_appearance_only(gw, udp, recorder):
    reply = query_convert(udp)
    assert reply
    assert [n for n, _ in recorder] == ["onQueryAvailableConvertItem"]
    classify, i = struct.unpack_from("<i", recorder[0][1])[0], 4
    assert classify == athlete_requests.CONVERT_APPEARANCE_CLASSIFY
    catalog, i = read_py(recorder[0][1], i)
    times, i = read_py(recorder[0][1], i)
    remind, i = read_py(recorder[0][1], i)
    assert i == len(recorder[0][1])
    assert times == {} and remind == {}
    rows = catalog[athlete_requests.CONVERT_APPEARANCE_CLASSIFY]
    assert 120920 in rows and rows[120920]["CAN_CONVERT_TIMES"] == 2
    assert 102004 not in rows
    assert rows[120920]["CURRENCY_ITEM_LIST"][0]["id"] == athlete_requests.CLOTHING_CHIPS


def test_convert_consumes_duplicate_and_grants_shards(gw, udp, recorder):
    prop = 120920
    before = udp._counts(ADDR)[prop]
    reply = convert_item(udp, prop, 1)
    assert reply
    assert udp._counts(ADDR)[prop] == before - 1
    names = [n for n, _ in recorder]
    assert "onDelDtsAppearanceFoldedItem" in names
    assert "onCurrencyUpdated" in names
    assert "onConvertItem" in names
    wallet = udp._session_wallet(ADDR)
    assert wallet.balances.get(athlete_requests.CLOTHING_CHIPS, 0) > 0


def test_convert_reply_prop_array_matches_times(gw, udp, recorder):
    """onConvertItem second argument is ARRAY<INT32> with one prop id per converted copy."""
    prop = 120920
    convert_item(udp, prop, 2)
    args = [a for n, a in recorder if n == "onConvertItem"][0]
    cid, i = struct.unpack_from("<i", args)[0], 4
    assert cid == prop
    n = struct.unpack_from("<I", args, i)[0]
    i += 4
    props = [struct.unpack_from("<i", args, i + 4 * k)[0] for k in range(n)]
    assert n == 2 and props == [prop, prop]