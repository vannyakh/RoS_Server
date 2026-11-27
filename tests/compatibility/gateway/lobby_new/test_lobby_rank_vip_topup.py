"""Leaderboard (server/lobby_rank.py), VIP Privilege (server/lobby_vip.py) and Top-Up
(server/lobby_topup.py, server/pay_goods.py) through GateUDP._athlete_request.

Wire shapes from extract Athlete.def / alias.xml (bwdefs):
  requireRankList(INT32 type, INT32 ver, INT32 len, BOOL next) ->
      onRequireBattleGround{Force,Winning,Killing}RankList(INT32, ARRAY<..._RANK_DATA>, INT32, INT32)
  requireRankInfo(INT32) -> onGetPlayerBattleGroundRank(INT32, PY_DICT)
  updatePlayerLBSData(STRING, STRING) -> onUpdatePlayerLBSData(STRING, STRING)
  getVipReward(INT32, INT32) -> syncVipInfo(PYTHON) + onGetVipReward(INT32, INT32)
  getAllVipReward() -> syncVipInfo(PYTHON) + onGetAllVipReward(PYTHON)
  requestRealNameAuthenCheckBeforeRequsetingPayGoods(STRING) ->
      onRequestRealNameAuthenCheckBeforeRequsetingPayGoods(STRING, BOOL),
      onConfirmPayOrder(BOOL, STRING, INT32, INT32, ARRAY<STRING>)"""

import json
import struct

import pytest

from lobby_new_helpers import ADDR, GATEWAY_SERVER, args_of, blob, i32, names, read_blob, read_py

YUANBAO = 2


# ---- rank ------------------------------------------------------------------------------------

def _rank_list(udp, rank_type, next_batch=0, buf_len=0):
    return udp._athlete_request(ADDR, "requireRankList",
                                struct.pack("<iiib", rank_type, 0, buf_len, next_batch))


def _decode_head(buf):
    gid = struct.unpack_from("<Q", buf)[0]
    nick, i = read_blob(buf, 8)
    flag, i = read_blob(buf, i)
    value, tag = struct.unpack_from("<ii", buf, i)
    return gid, nick, flag, value, tag, i + 8


@pytest.mark.parametrize("rank_type,method,tail", [
    (36, "onRequireBattleGroundForceRankList", "<fff"),       # DTS_FORCE_RANK_DATA
    (37, "onRequireBattleGroundWinningRankList", "<fIf"),     # DTS_WIN_RANK_DATA
    (52, "onRequireBattleGroundKillingRankList", "<Hff"),     # DTS_KILL_RANK_DATA
])
def test_rank_list_reply_method_and_row_layout(gw, udp, recorder, rank_type, method, tail):
    reply = _rank_list(udp, rank_type)
    assert reply and names(recorder) == [method]
    (args,) = args_of(recorder, method)
    start, count = struct.unpack_from("<iI", args)
    assert (start, count) == (0, 1)                           # only this server's own player
    gid, nick, _flag, value, tag, i = _decode_head(args[8:])
    assert gid == gw.account_link.current_gid() and nick and value == 0 and tag == 0
    i += 8 + struct.calcsize(tail)
    version, echoed = struct.unpack_from("<ii", args, i)
    assert (version, echoed) == (gw.lobby_rank.VERSION, rank_type)
    assert i + 8 == len(args)


def test_rank_list_next_batch_sends_no_rows(gw, udp, recorder):
    _rank_list(udp, 37, next_batch=1, buf_len=1)
    (args,) = args_of(recorder, "onRequireBattleGroundWinningRankList")
    assert struct.unpack("<iIii", args) == (1, 0, gw.lobby_rank.VERSION, 37)


def test_rank_list_unknown_type_is_not_answered(udp, recorder):
    assert _rank_list(udp, 999) == b""
    assert recorder == []


def test_rank_rows_sorted_by_value(gw):
    lr = gw.lobby_rank
    rec = lambda kills: {"records": [{"season": 0, "queue": "total", "team_mode": "overall",
                                      "fight_count": 4, "kill_count": kills, "death_count": 2}]}
    players = [(1, "a", rec(3)), (2, "b", rec(9)), (3, "c", None)]
    assert lr.own_rank(52, 2, players) == 1 and lr.own_rank(52, 1, players) == 2
    assert lr.own_rank(52, 3, players) == 3 and lr.own_rank(52, 4, players) == 0


def test_rank_info_dict_has_rank_and_col3_to_col6(gw, udp, recorder):
    udp._athlete_request(ADDR, "requireRankInfo", i32(36))
    (args,) = args_of(recorder, "onGetPlayerBattleGroundRank")
    assert struct.unpack_from("<i", args)[0] == 36
    info, j = read_py(args, 4)
    assert j == len(args)
    assert set(info) == {"rank", "col-3", "col-4", "col-5", "col-6"} and info["rank"] == 1


def test_lbs_data_echo_and_empty_lbs_rank(udp, recorder):
    udp._athlete_request(ADDR, "updatePlayerLBSData", blob("EU") + blob("DE"))
    assert recorder == [("onUpdatePlayerLBSData", blob("EU") + blob("DE"))]
    recorder.clear()
    udp._athlete_request(ADDR, "requestLBSRankList", b"")
    assert names(recorder) == ["onGetLBSRank"] and read_py(recorder[0][1])[0] == []


# ---- VIP -------------------------------------------------------------------------------------

def _vip_table():
    return json.loads((GATEWAY_SERVER / "extract" / "vip_levels.json").read_text(encoding="utf-8"))


def _last_vip_info(recorder):
    info, j = read_py(args_of(recorder, "syncVipInfo")[-1])
    assert j == len(args_of(recorder, "syncVipInfo")[-1])
    return info


def test_vip_info_shape_and_gold_never_above_silver(gw, monkeypatch):
    monkeypatch.setenv("VIP_SILVER_LEVEL", "2")
    monkeypatch.setenv("VIP_GOLD_LEVEL", "5")
    info = gw.lobby_vip.vip_info({})
    assert set(info) == {0, 1}
    assert info[0]["level"] == 2 and info[1]["level"] == 2      # gold clamped to silver
    for t in (0, 1):
        assert set(info[t]) == {"level", "rewardStatus", "num", "redPoint", "activeTime"}
        assert sorted(info[t]["rewardStatus"]) == list(range(1, int(_vip_table()["max"][str(t)]) + 1))
    assert info[0]["rewardStatus"][1] == 1 and info[0]["rewardStatus"][3] == 0
    assert info[0]["redPoint"] is True


def test_vip_reward_claim_once(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("VIP_SILVER_LEVEL", "2")
    props = _vip_table()["levels"]["0"]["1"]["props"]
    udp._athlete_request(ADDR, "getVipReward", struct.pack("<ii", 0, 1))
    assert args_of(recorder, "onGetVipReward") == [struct.pack("<ii", 0, 1)]
    assert [struct.unpack_from("<i", a)[0] for a in args_of(recorder, "onAddDtsAppearanceItem")] == props
    assert _last_vip_info(recorder)[0]["rewardStatus"][1] == 2                  # DONE
    assert gw.vip_claimed() == {0: {1}}                                         # saved per account

    recorder.clear()
    udp._athlete_request(ADDR, "getVipReward", struct.pack("<ii", 0, 1))      # second claim
    assert names(recorder) == ["syncVipInfo"]                                   # nothing granted


def test_vip_reward_above_level_is_refused(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("VIP_SILVER_LEVEL", "1")
    udp._athlete_request(ADDR, "getVipReward", struct.pack("<ii", 0, 3))
    assert names(recorder) == ["syncVipInfo"]
    assert gw.vip_claimed() == {}


def test_vip_all_rewards_claims_every_available_level_once(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("VIP_SILVER_LEVEL", "2")
    monkeypatch.setenv("VIP_GOLD_LEVEL", "1")
    t = _vip_table()["levels"]
    expected = t["0"]["1"]["props"] + t["0"]["2"]["props"] + t["1"]["1"]["props"]
    udp._athlete_request(ADDR, "getAllVipReward", b"")
    (all_args,) = args_of(recorder, "onGetAllVipReward")
    assert read_py(all_args)[0] == {p: 1 for p in expected}
    assert gw.vip_claimed() == {0: {1, 2}, 1: {1}}
    recorder.clear()
    udp._athlete_request(ADDR, "getAllVipReward", b"")
    assert names(recorder) == ["syncVipInfo"]


# ---- Top-Up ----------------------------------------------------------------------------------

def _packs():
    return json.loads((GATEWAY_SERVER / "extract" / "pay_goods.json").read_text(encoding="utf-8"))


def _pay(udp, goods):
    return udp._athlete_request(ADDR, "requestRealNameAuthenCheckBeforeRequsetingPayGoods", blob(goods))


def _confirm(args):
    ok = args[0]
    sn, i = read_blob(args, 1)
    base, bonus = struct.unpack_from("<ii", args, i)
    n = struct.unpack_from("<I", args, i + 8)[0]
    bids, j = [], i + 12
    for _ in range(n):
        b, j = read_blob(args, j)
        bids.append(b.decode())
    assert j == len(args)
    return ok, sn, base, bonus, bids


def test_topup_private_flow_confirms_and_credits(gw, udp, recorder):
    _pay(udp, "6000")
    assert names(recorder)[0] == "onRequestRealNameAuthenCheckBeforeRequsetingPayGoods"
    assert args_of(recorder, "onRequestRealNameAuthenCheckBeforeRequsetingPayGoods") == [blob("6000") + b"\x00"]
    ok, sn, base, bonus, bids = _confirm(args_of(recorder, "onConfirmPayOrder")[0])
    assert ok == 1 and sn and bids == ["6000"]
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 + base + bonus
    (yb,) = args_of(recorder, "onYBUpdated")
    assert struct.unpack("<qqi", yb) == (1000 + base + bonus, 0, 0)


def test_topup_off_sends_only_the_refused_auth_check(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("GATEWAY_PRIVATE_TOPUP", "off")
    _pay(udp, "6000")
    assert recorder == [("onRequestRealNameAuthenCheckBeforeRequsetingPayGoods", blob("6000") + b"\x00")]
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000


def test_lobby_topup_grant_matches_the_client_pay_goods_table(gw):
    packs = _packs()
    some = sorted(packs)[:5]
    for gid in some:
        assert gw.lobby_topup.grant(gid) == (int(packs[gid].get("AMOUNT") or 0),
                                             int(packs[gid].get("NORMAL_PRESENT") or 0))
    assert gw.lobby_topup.grant("not-a-pack") is None


def test_topup_unknown_pack_falls_back_to_the_bid_heuristic(gw, udp, recorder):
    """An id missing from pay_goods.json still credits (pay_goods.diamonds_for_bid fallback)."""
    goods = "private.pack.300"
    assert gw.lobby_topup.grant(goods) is None
    base, bonus = gw.pay_goods.diamonds_for_bid(goods)
    udp._athlete_request(ADDR, "requestRealNameAuthenCheckBeforeRequsetingPayGoods", blob(goods))
    ok, _sn, b, n, bids = _confirm(args_of(recorder, "onConfirmPayOrder")[0])
    assert (ok, b, n, bids) == (1, base, bonus, [goods])


def test_topup_client_pack_credits_the_pay_goods_table_amount(gw, udp, recorder):
    goods = "com.netease.h45na.128"
    base, bonus = gw.lobby_topup.grant(goods)                 # (AMOUNT, NORMAL_PRESENT) from the client table
    _pay(udp, goods)
    ok, _sn, b, n, _bids = _confirm(args_of(recorder, "onConfirmPayOrder")[0])
    assert (ok, b, n) == (1, base, bonus)
