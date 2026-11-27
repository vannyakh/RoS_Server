"""Local-mode Store persistence (saved_accounts.json "inventory:<gid>") and what the next login
sends back (athlete_create_message: dtsAppearancePackage, freeYuanbao), plus two client
addresses buying at the same time."""

import json
import struct

import pytest

from store_helpers import ADDR, ADDR_B, BRIGADE, GOBI, YUANBAO, buy, buy_multi, names


def prop(gw, good):
    return gw.athlete_requests.mall_good_prop(good)


def saved(gw):
    with open(gw.ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def inventory(gw, gid=None):
    return saved(gw)[f"inventory:{gid if gid is not None else gw.account_link.current_gid()}"]


def test_local_buy_saves_items_and_diamonds(gw, udp, recorder):
    buy(udp, BRIGADE)
    inv = inventory(gw)
    assert inv["yuanbao"] == 1000 - 209
    assert inv["items"] == [prop(gw, BRIGADE)]
    assert inv["recent_got"][0] == prop(gw, BRIGADE)
    state = gw.local_state()
    assert state["yuanbao"] == 791 and state["items"] == [{"prop_id": prop(gw, BRIGADE)}]


def test_local_multi_buy_saves_every_item_once(gw, udp, recorder):
    buy_multi(udp, [BRIGADE, GOBI], [2, 1])
    assert inventory(gw)["items"] == [prop(gw, BRIGADE), prop(gw, GOBI)]
    assert inventory(gw)["yuanbao"] == 1000 - 627


def test_local_counts_above_one_last_for_the_session_only(gw, udp, recorder):
    """Documented local-mode limit (_cultivate_compound docstring): saved_accounts.json keeps item
    ids only, so buying 3 copies is saved as one."""
    buy(udp, BRIGADE, 3)
    assert udp._counts(ADDR)[prop(gw, BRIGADE)] == 3
    assert inventory(gw)["items"] == [prop(gw, BRIGADE)]


def test_failed_buy_saves_nothing(gw, udp, recorder):
    buy(udp, 10000003)                                            # 1280 > 1000
    assert names(recorder) == ["onBuyMallGoodFailed"]
    with pytest.raises(FileNotFoundError):
        saved(gw)


def test_next_login_sends_bought_items_and_remaining_diamonds(gw, udp, recorder):
    buy(udp, BRIGADE)
    p = prop(gw, BRIGADE)
    # Next login of the same account (local mode: athlete_create_message reads local_state()).
    gw.LOGIN_STATE = None
    msg = gw.athlete_create_message()
    assert gw.LOGIN_STATE["yuanbao"] == 791
    assert gw.login_yuanbao() == 791
    assert struct.pack("<ii", p, 1) in msg                        # ITEM_DATA3 itemID, number
    assert struct.pack("<q", 791) in msg                          # freeYuanbao
    # A new session starts from the saved state.
    fresh = gw.GateUDP(25000)
    assert fresh._session_wallet(ADDR).balances[YUANBAO] == 791
    assert p in fresh._owned(ADDR)


def test_next_login_then_another_buy_keeps_both_items(gw, udp, recorder):
    buy(udp, BRIGADE)
    gw.LOGIN_STATE = None
    gw.athlete_create_message()
    again = gw.GateUDP(25000)
    buy(again, GOBI)
    assert inventory(gw)["items"] == [prop(gw, BRIGADE), prop(gw, GOBI)]
    assert inventory(gw)["yuanbao"] == 791 - 209


# ---- two addresses ---------------------------------------------------------------------------------

def test_two_addresses_of_one_account_share_the_saved_diamond_balance(gw, udp, recorder):
    """Both addresses log in as the same (default) account: each buy re-reads the account's saved
    diamonds before charging, so the second address pays from what the first one left."""
    buy(udp, BRIGADE, addr=ADDR)
    buy(udp, GOBI, 2, addr=ADDR_B)
    assert udp._session_wallet(ADDR_B).balances[YUANBAO] == 1000 - 209 - 418
    assert inventory(gw)["yuanbao"] == 1000 - 209 - 418
    assert udp._owned(ADDR) == {prop(gw, BRIGADE)}
    assert udp._owned(ADDR_B) == {prop(gw, GOBI)}


def test_two_players_save_under_their_own_inventory_key(gw, udp, recorder):
    """Sessions swap account_link._login_uid per packet (_activate); the gid picks the key."""
    gw.account_link._login_uid = "111"
    buy(udp, BRIGADE, addr=ADDR)
    gw.account_link._login_uid = "222"
    buy(udp, GOBI, addr=ADDR_B)
    assert inventory(gw, 111) == {"yuanbao": 791, "items": [prop(gw, BRIGADE)],
                                  "recent_got": [prop(gw, BRIGADE)]}
    assert inventory(gw, 222)["items"] == [prop(gw, GOBI)]
    assert inventory(gw, 222)["yuanbao"] == 791


def test_same_account_on_two_addresses_cannot_spend_twice(gw, udp, recorder):
    """Local mode: the second address's buy re-reads the account's saved balance (164), so the
    same 1000 diamonds cannot be spent twice."""
    gw.account_link._login_uid = "111"
    buy(udp, BRIGADE, 4, addr=ADDR)                               # 836 of 1000
    buy(udp, BRIGADE, 4, addr=ADDR_B)                             # another 836 of the same 1000
    assert names(recorder).count("onBuyMallGood") == 1
    assert inventory(gw, 111)["yuanbao"] == 1000 - 836
