"""Supply-related Athlete client methods in the login stream (GateUDP._lobby_data_calls, sent
before enterHall on login and after createCharacter). A later optimisation that drops or
reorders them, or sends the full catalogue at login again, fails here."""

import struct

import pytest

from supply_helpers import ADDR, read_blob, read_py

# Full method-name order of _lobby_data_calls with default env and repo data (snapshot).
LOGIN_ORDER = [
    "syncServerTime", "syncServerTimeZone",
    "onSetSwitches", "onSetSwitches", "onSetSwitches", "onSetSwitches",       # LOBBY_SWITCHES_OFF
    "onUpdateAlreadyShowSupplyID",
    "onUpdateDtsHallThemeID",
    "onUpdateRecentGotPropIDList",      # Depot > Recent at login (RO-118); not supply-related
    "onUpdateLuckyCarnivalData",
    "gmsyncRedPoints",
    "onAccumulateChargeUpdate",
    "onQueryAvailableSupplement",
    "onUpdateBuySupplementCntDict",
    "syncVipInfo",
    # Event panel activities (RosGG-Server-v2 82fb509, server/lobby_events.py)
    "syncDailyActivity", "syncDailyActivityRewardState",
    "syncWeeklyActivity", "syncWeeklyActivityRewardState",
    "syncActivityProgress", "syncActivityState",
    "syncMonthPayRebateSpecialAwardInfo",
    "onPersonalRecommendStateUpdated",
    "syncTelkomseOpenStatus",
    "_OnBraveBookDataChanged", "onSyncSpecTrainExp", "onSyncSpecTrainRewardMain",
    "_OnBraveBookTaskDataChanged",
    "onSyncSwitches", "onSetSwitches", "onSyncSwitches", "onSetSwitches",
    "syncDtsInGameActionAppearanceIDs", "syncDtsInGameActionSuitAppearanceIDs", "onUpdateDtsEmojiList",
    "onSetPortrait",
]
SUPPLY_METHODS = {"onUpdateAlreadyShowSupplyID", "onQueryAvailableSupplement",
                  "onUpdateBuySupplementCntDict", "syncVipInfo"}
SUPPLY_ORDER = ["onSetSwitches:SysEnableMonthSupply", "onUpdateAlreadyShowSupplyID",
                "onQueryAvailableSupplement", "onUpdateBuySupplementCntDict", "syncVipInfo"]


def _switch(args):
    name, i = read_blob(args)
    return name.decode(), args[i]


def _supply_view(calls):
    """Supply-related calls only, switches labelled by name."""
    out = []
    for name, args in calls:
        if name == "onSetSwitches" and _switch(args)[0] == "SysEnableMonthSupply":
            out.append("onSetSwitches:SysEnableMonthSupply")
        elif name in SUPPLY_METHODS:
            out.append(name)
    return out


def test_login_stream_method_order_snapshot(gw, udp, recorder):
    udp._lobby_data_calls()
    assert [n for n, _ in recorder] == LOGIN_ORDER


def test_supply_methods_come_in_a_fixed_order(gw, udp, recorder):
    udp._lobby_data_calls()
    assert _supply_view(recorder) == SUPPLY_ORDER
    names = [n for n, _ in recorder]
    # server clock first: supply/monthly pages compare dates against it
    assert names.index("syncServerTime") < names.index("onQueryAvailableSupplement")


def test_login_supplement_is_an_empty_stub_not_the_catalogue(gw, udp, recorder):
    udp._lobby_data_calls()
    (args,), = [[a] for n, a in recorder if n == "onQueryAvailableSupplement"]
    stub, end = read_py(args)
    assert stub == {} and end == len(args)
    assert len(args) < 16                  # the 264-box catalogue (> 15 KB) waits for the query


def test_login_buy_counts_are_three_empty_dicts(gw, udp, recorder):
    udp._lobby_data_calls()
    (args,), = [[a] for n, a in recorder if n == "onUpdateBuySupplementCntDict"]
    a, i = read_py(args)
    b, j = read_py(args, i)
    c, k = read_py(args, j)
    assert (a, b, c, k) == ({}, {}, {}, len(args))


def test_month_supply_switch_is_turned_off_by_default(gw, udp, recorder):
    udp._lobby_data_calls()
    switches = [_switch(a) for n, a in recorder if n == "onSetSwitches"]
    assert switches[:4] == [("SysEnableMonthSupply", 0), ("SysEnableHuiliuRecallSystem", 0),
                            ("EnableRecallPlayer", 0), ("EnableNewRecallPlayer", 0)]


def test_lobby_switches_off_env_keeps_month_supply_on(gw, udp, recorder, monkeypatch):
    """config.cmd keeps SysEnableMonthSupply on for an emulator dated 2022 (LOBBY_FINDINGS)."""
    monkeypatch.setenv("LOBBY_SWITCHES_OFF", "EnableRecallPlayer")
    udp._lobby_data_calls()
    assert "onSetSwitches:SysEnableMonthSupply" not in _supply_view(recorder)
    assert [_switch(a) for n, a in recorder if n == "onSetSwitches"][0] == ("EnableRecallPlayer", 0)


def test_weekly_push_id_defaults_to_zero(gw, udp, recorder):
    udp._lobby_data_calls()
    assert ("onUpdateAlreadyShowSupplyID", struct.pack("<i", 0)) in recorder


def test_supply_catalog_at_login_sends_the_cached_blob(gw, udp, recorder, monkeypatch):
    """SUPPLY_CATALOG_AT_LOGIN avoids an empty dict until queryAvailableSupplement returns."""
    monkeypatch.setenv("SUPPLY_CATALOG_AT_LOGIN", "1")
    gw.supply_cache.invalidate()
    udp._lobby_data_calls()
    blob = gw.supply_cache.supplement_info_blob()
    sent = [a for n, a in recorder if n == "onQueryAvailableSupplement"]
    assert sent == [blob]
    assert len(blob) > 10000


def test_supply_preack_weekly_push_sets_shown_id_at_login(gw, udp, recorder, monkeypatch):
    """SUPPLY_PREACK_WEEKLY_PUSH stops the weekly Supreme auto-open on a fresh account."""
    monkeypatch.setenv("SUPPLY_PREACK_WEEKLY_PUSH", "1")
    udp._lobby_data_calls()
    sid = gw.athlete_requests.this_week_supply_id()
    assert ("onUpdateAlreadyShowSupplyID", struct.pack("<i", sid)) in recorder
    assert gw.load_accounts()["supply_push"] == {"id": sid}


def test_weekly_push_recorded_by_the_empty_def_call_is_sent_at_next_login(gw, udp, recorder):
    udp._athlete_request(ADDR, "setHasAlreadyShowSupplyID", b"")
    recorder.clear()
    udp._lobby_data_calls()
    sent = [a for n, a in recorder if n == "onUpdateAlreadyShowSupplyID"]
    assert sent == [struct.pack("<i", gw.athlete_requests.this_week_supply_id())]
    assert sent[0] != struct.pack("<i", 0)


def test_create_character_sends_the_lobby_stream_before_enter_hall(gw, udp, recorder):
    args = struct.pack("<i", 20001) + bytes([5]) + b"Raven"
    reply = udp._athlete_request(ADDR, "createCharacter", args)
    assert reply
    names = [n for n, _ in recorder]
    assert names[-1] == "enterHall"
    assert names[-1 - len(LOGIN_ORDER):-1] == LOGIN_ORDER
