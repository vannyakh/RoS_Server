"""Store catalogue replies: queryAvailableMallGoods, queryAvailableMallGoodsByType,
queryAvailableMallGoodsForAppearanceMall, and the RoS_Server operator listings (off-sale and
price overrides) applied to them."""

import struct

import pytest

from store_helpers import (ADDR, APPEARANCE, BRIGADE, GOBI, GP, YUANBAO, names, read_py)

FIELDS = {"CURRENCY_ID", "PRICE", "DISCOUNT", "BUY_TIMES"}


@pytest.mark.parametrize("name", ["queryAvailableMallGoods", "queryAvailableMallGoodsByType",
                                  "queryAvailableMallGoodsForAppearanceMall", "buyMallGood",
                                  "buyMallGoodInAppearanceMall", "buyMultipleMallGood", "buyDtsHallProp"])
def test_store_requests_round_trip_by_name(reqs_module, name):
    msgid, payload = reqs_module.encode_call(name, b"\x01\x00\x00\x00")
    assert reqs_module.decode(msgid, payload) == (name, b"\x01\x00\x00\x00")


@pytest.fixture
def reqs_module(gw):
    return gw.athlete_requests


def test_query_all_sends_every_client_good_in_one_message(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "queryAvailableMallGoods", b"")
    assert reply and names(recorder) == ["onQueryAvailableMallGoods"]
    args = recorder[0][1]
    goods, end = read_py(args)
    assert end == len(args)
    assert args[0] == 0xFF and len(args) < 64 * 1024             # long blob, still one var16 message
    assert len(goods) == 1160 and all(isinstance(k, int) for k in goods)
    assert set(goods) == set(gw.athlete_requests.mall_goods(0))
    for g in goods.values():
        assert FIELDS <= set(g)
    # The full catalogue is too large with NAME; the client has the names in its own table.
    assert all("NAME" not in g for g in goods.values())
    assert goods[BRIGADE] == {"CURRENCY_ID": YUANBAO, "PRICE": 209, "DISCOUNT": 100, "BUY_TIMES": 0}


def test_query_by_type_echoes_the_mask_and_sends_that_location(gw, udp, recorder):
    udp._athlete_request(ADDR, "queryAvailableMallGoodsByType", struct.pack("<I", 8))
    assert names(recorder) == ["onQueryAvailableMallGoodsByType"]
    args = recorder[0][1]
    assert struct.unpack_from("<I", args)[0] == 8
    goods, end = read_py(args, 4)
    assert end == len(args)
    table = gw.athlete_requests._mall_table()
    assert set(goods) == table["by_type"][8]
    assert 0 < len(goods) < 1160
    assert all(FIELDS <= set(g) for g in goods.values())


def test_query_by_type_with_two_bits_is_the_union(gw, udp, recorder):
    udp._athlete_request(ADDR, "queryAvailableMallGoodsByType", struct.pack("<I", 8 | 32))
    goods, _ = read_py(recorder[0][1], 4)
    table = gw.athlete_requests._mall_table()
    assert set(goods) == table["by_type"][8] | table["by_type"][32]


@pytest.mark.parametrize("mask", [0, 2])
def test_query_by_type_zero_or_unknown_bit_sends_everything(gw, udp, recorder, mask):
    udp._athlete_request(ADDR, "queryAvailableMallGoodsByType", struct.pack("<I", mask))
    args = recorder[0][1]
    assert struct.unpack_from("<I", args)[0] == mask
    goods, _ = read_py(args, 4)
    assert len(goods) == 1160


def test_query_appearance_mall_sends_the_appearance_table(gw, udp, recorder):
    udp._athlete_request(ADDR, "queryAvailableMallGoodsForAppearanceMall", b"")
    assert names(recorder) == ["onQueryAvailableMallGoodsForAppearanceMall"]
    goods, end = read_py(recorder[0][1])
    assert end == len(recorder[0][1])
    assert len(goods) == 6 and APPEARANCE in goods
    assert goods[APPEARANCE]["CURRENCY_ID"] == YUANBAO and goods[APPEARANCE]["PRICE"] == 9999
    assert "NAME" in goods[APPEARANCE]                            # small table keeps NAME


# ---- operator listings --------------------------------------------------------------------------

def test_off_sale_good_is_hidden_from_every_catalogue(gw, udp, recorder, listings):
    listings += [{"goods_id": BRIGADE, "item_id": None, "on_sale": False, "currency": "diamond", "price": 1},
                 {"goods_id": APPEARANCE, "item_id": None, "on_sale": False, "currency": "diamond", "price": 1}]
    udp._athlete_request(ADDR, "queryAvailableMallGoods", b"")
    udp._athlete_request(ADDR, "queryAvailableMallGoodsByType", struct.pack("<I", 0))
    udp._athlete_request(ADDR, "queryAvailableMallGoodsForAppearanceMall", b"")
    everything, _ = read_py(recorder[0][1])
    by_type, _ = read_py(recorder[1][1], 4)
    appearance, _ = read_py(recorder[2][1])
    assert BRIGADE not in everything and BRIGADE not in by_type
    assert GOBI in everything and len(everything) == 1160 - 2   # 9901 is also in the main table
    assert APPEARANCE not in appearance and len(appearance) == 5


def test_price_override_replaces_currency_price_and_discount(gw, udp, recorder, listings):
    listings += [{"goods_id": BRIGADE, "item_id": None, "on_sale": True, "currency": "coin", "price": 77},
                 {"goods_id": 1030, "item_id": None, "on_sale": True, "currency": "diamond", "price": 300}]
    udp._athlete_request(ADDR, "queryAvailableMallGoods", b"")
    goods, _ = read_py(recorder[0][1])
    assert goods[BRIGADE] == {"CURRENCY_ID": GP, "PRICE": 77, "DISCOUNT": 100, "BUY_TIMES": 0}
    assert goods[1030]["PRICE"] == 300 and goods[1030]["DISCOUNT"] == 100     # was 400 at 48 %
    assert gw.athlete_requests.mall_good_price(BRIGADE, 2) == (GP, 154)
    assert gw.athlete_requests.mall_good_price(1030) == (YUANBAO, 300)


def test_listing_with_unknown_currency_is_ignored(gw, listings):
    listings.append({"goods_id": BRIGADE, "item_id": None, "on_sale": False, "currency": "gems", "price": 1})
    assert BRIGADE in gw.athlete_requests.mall_goods(0)
    assert gw.athlete_requests.mall_good_price(BRIGADE) == (YUANBAO, 209)


def test_broken_listing_source_falls_back_to_client_prices(gw):
    def broken():
        raise RuntimeError("down")
    gw.athlete_requests.set_listing_source(broken)
    assert len(gw.athlete_requests.mall_goods(0)) == 1160
    assert gw.athlete_requests.mall_good_price(BRIGADE) == (YUANBAO, 209)


def test_discount_is_applied_per_unit_then_multiplied(gw):
    assert gw.athlete_requests.mall_good_price(1030) == (YUANBAO, 400 * 48 // 100)
    assert gw.athlete_requests.mall_good_price(1030, 3) == (YUANBAO, 192 * 3)
    assert gw.athlete_requests.mall_good_price(BRIGADE, 0) == (YUANBAO, 209)   # num < 1 counts as 1


def test_unknown_good_has_no_price(gw):
    assert gw.athlete_requests.mall_good_price(424242) is None
    assert gw.athlete_requests.mall_good_prop(424242) is None
