"""Private Top-up (iPay) Athlete handlers."""

import struct

import pytest

from supply_helpers import ADDR, read_py

ADDR2 = ADDR
YUANBAO = 2


@pytest.fixture
def topup_gw(gw, monkeypatch):
    monkeypatch.setenv("GATEWAY_PRIVATE_TOPUP", "on")
    return gw


def names(calls):
    return [n for n, _ in calls]


def test_check_purchase_limit_answers(topup_gw, udp, recorder):
    bid = b"com.netease.ros.diamond.300"
    reply = udp._athlete_request(ADDR, "checkPurchaseLimitAndTime", topup_gw._bw_blob(bid))
    assert reply
    assert recorder == [("onCheckPurchaseLimitAndTime", topup_gw._bw_blob(bid))]


def test_private_topup_grants_diamonds_and_confirms(topup_gw, udp, recorder):
    goods = "6000"
    reply = udp._athlete_request(
        ADDR,
        "requestRealNameAuthenCheckBeforeRequsetingPayGoods",
        topup_gw._bw_blob(goods.encode()),
    )
    assert reply
    assert names(recorder)[0] == "onRequestRealNameAuthenCheckBeforeRequsetingPayGoods"
    assert "onRequirePayOrder" in names(recorder)
    assert "onConfirmPayOrder" in names(recorder)
    assert "onYBUpdated" in names(recorder)
    # 6000 pack: 6000 + 3000 bonus
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 + 9000


def test_query_rebate_tabs_do_not_crash(topup_gw, udp, recorder):
    for method, reply_name in (
        ("queryPayExtDayFirstFlags", "onPayExtDayFirstFlags"),
        ("querySumCash", "onQuerySumCash"),
        ("queryAvailblePayRebateAwards", "onQueryAvailblePayRebateAwards"),
        ("queryAvailbleMonthPayRebateAwards", "onQueryAvailbleMonthPayRebateAwards"),
    ):
        recorder.clear()
        reply = udp._athlete_request(ADDR, method, b"")
        assert reply and recorder[-1][0] == reply_name
        if reply_name.endswith("PayRebateAwards"):
            py1, i = read_py(recorder[-1][1])
            py2, j = read_py(recorder[-1][1], i)
            assert (py1, py2) == ({}, {}) and j + 4 == len(recorder[-1][1])
        if reply_name == "onQuerySumCash":
            assert struct.unpack_from("<i", recorder[-1][1])[0] == 0