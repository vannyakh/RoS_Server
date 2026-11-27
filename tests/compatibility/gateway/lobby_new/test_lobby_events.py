"""Event panel, daily sign-in and Activity Points (server/lobby_events.py + ros_server hooks).

Wire shapes from extract Athlete.def (bwdefs): requestDtsSigninAward() -> onSetSignAwardTime(INT32),
onRequestDtsSignInAward(ARRAY<INT32>, INT32), onSetSignAwardLevel(INT32);
getActivityReward / getDailyActivityReward / getWeeklyActivityReward(INT32) ->
syncSingleActivityState(INT32, INT8), syncSingle{Daily,Weekly}ActivityRewardState(INT32, INT8),
onGetActivityReward(ARRAY<INT32>); queryAvailableActivity() -> onQueryAvailableActivity(PYTHON)."""

import calendar
import struct
import time

import pytest

from lobby_new_helpers import ADDR, GATEWAY_SERVER, args_of, i32, names, read_py

NOW = calendar.timegm(time.strptime("2022-04-20 12:00:00", "%Y-%m-%d %H:%M:%S"))
DAY = 86400


def _arr_i32(vals):
    return struct.pack("<I", len(vals)) + b"".join(struct.pack("<i", v) for v in vals)


def _signin(udp, gw, monkeypatch, now):
    monkeypatch.setattr(gw.athlete_requests, "game_now", lambda: now)
    return udp._athlete_request(ADDR, "requestDtsSigninAward", b"")


# ---- Event panel -----------------------------------------------------------------------------

def test_query_available_activity_sends_empty_catalogue_and_red_points(udp, recorder):
    assert udp._athlete_request(ADDR, "queryAvailableActivity", b"")
    assert names(recorder) == ["onQueryAvailableActivity", "onUpdateActivityRedPointInfo"]
    assert [read_py(a)[0] for _n, a in recorder] == [{}, {}]


def test_select_activity_is_accepted_without_reply(udp, recorder):
    assert udp._athlete_request(ADDR, "selectActivity", i32(3) + b"\x01") == b""
    assert recorder == []


# ---- sign-in ---------------------------------------------------------------------------------

def test_signin_claim_once_per_day_then_next_level(gw, udp, recorder, monkeypatch):
    import lobby_events
    awards = lobby_events.SIGNIN_AWARDS

    _signin(udp, gw, monkeypatch, NOW)
    assert recorder == [("onSetSignAwardTime", i32(NOW)), ("onRequestDtsSignInAward", _arr_i32([awards[0]]) + i32(1))]
    assert gw.load_accounts()[gw._signin_key()] == {"level": 1, "day": "2022-04-20", "ts": NOW}

    recorder.clear()
    _signin(udp, gw, monkeypatch, NOW + 3600)                   # same day: no award
    assert recorder == [("onSetSignAwardTime", i32(NOW)), ("onSetSignAwardLevel", i32(1))]
    assert gw.load_accounts()[gw._signin_key()]["level"] == 1

    recorder.clear()
    _signin(udp, gw, monkeypatch, NOW + DAY)                    # next day: level 2
    assert args_of(recorder, "onRequestDtsSignInAward") == [_arr_i32([awards[1]]) + i32(2)]


def test_signin_level_stops_at_the_last_day(gw):
    import lobby_events as le
    st = None
    for d in range(len(le.SIGNIN_AWARDS) + 2):
        st, award, _calls = le.signin_claim(st, NOW + d * DAY)
    assert st["level"] == len(le.SIGNIN_AWARDS) and award == le.SIGNIN_AWARDS[-1]


def test_signin_login_calls_restore_time_and_level(gw):
    import lobby_events as le
    assert le.signin_login_calls(None) == []
    assert le.signin_login_calls({"ts": NOW, "level": 3}) == [("onSetSignAwardTime", i32(NOW)),
                                                              ("onSetSignAwardLevel", i32(3))]


def test_signin_state_is_per_account(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("CBP_GID", "111")
    _signin(udp, gw, monkeypatch, NOW)
    monkeypatch.setenv("CBP_GID", "222")
    recorder.clear()
    _signin(udp, gw, monkeypatch, NOW + 60)
    assert len(args_of(recorder, "onRequestDtsSignInAward")) == 1


# ---- Activity Points (module logic, with an injected table) ----------------------------------

TABLE = {"activities": {0: {"kind": "match", "count": 2, "points": 30},
                        1: {"kind": "login", "count": 1, "points": 40}},
         "daily": [{"points": 30, "props": [[200027, 1]]}, {"points": 70, "props": [[203011, 2]]}],
         "weekly": [{"points": 60, "props": [[291210, 1]]}]}


@pytest.fixture
def le(gw, monkeypatch):
    import lobby_events
    monkeypatch.setattr(lobby_events, "_table", TABLE)
    return lobby_events


def test_activity_claim_only_when_met_and_only_once(le):
    st = le.activity_state(None, NOW)
    assert le.activity_claim(st, 0) == []                       # UNMET: nothing
    assert st["daily"] == 0
    calls = le.activity_event(st, "match")
    assert calls == [("syncSingleActivityProgress", i32(0) + i32(1))] and st["state"][0] == le.UNMET
    calls = le.activity_event(st, "match")
    assert ("syncSingleActivityState", i32(0) + struct.pack("<b", le.MET)) in calls
    claim = le.activity_claim(st, 0)
    assert claim[0] == ("syncSingleActivityState", i32(0) + struct.pack("<b", le.GOT))
    assert st["daily"] == 30 and st["weekly"] == 30
    assert le.activity_claim(st, 0) == []                       # second claim: nothing
    assert st["daily"] == 30
    assert le.activity_event(st, "match") == []                 # GOT activities stop counting
    assert le.activity_claim(st, 99) == []


def test_daily_tier_claim_only_when_met_and_only_once(le):
    st = le.activity_state(None, NOW)
    assert le.tier_claim(st, False, 0) == ([], [])              # 0 points: UNMET
    le.activity_event(st, "match", 2)
    le.activity_claim(st, 0)                                    # 30 points
    props, calls = le.tier_claim(st, False, 0)
    assert props == [200027]
    assert calls == [("syncSingleDailyActivityRewardState", i32(0) + struct.pack("<b", le.GOT)),
                     ("onGetActivityReward", _arr_i32([200027]))]
    assert le.tier_claim(st, False, 0) == ([], [])              # once
    assert le.tier_claim(st, False, 1) == ([], [])              # 70 not reached
    assert le.tier_claim(st, False, 5) == ([], [])              # out of range
    assert le.tier_claim(st, False, -1) == ([], [])


def test_weekly_tier_and_weekly_points_survive_the_daily_reset(le):
    st = le.activity_state(None, NOW)                           # Wed 2022-04-20 (ISO week 16)
    le.activity_event(st, "match", 2)
    le.activity_claim(st, 0)                                    # 30
    st = le.activity_state(st, NOW + DAY)                       # Thursday, same week
    assert st["daily"] == 0 and st["weekly"] == 30 and st["state"][0] == le.UNMET
    le.activity_event(st, "match", 2)
    le.activity_claim(st, 0)                                    # weekly 60
    props, calls = le.tier_claim(st, True, 0)
    assert props == [291210] and calls[0][0] == "syncSingleWeeklyActivityRewardState"
    assert le.tier_claim(st, True, 0) == ([], [])
    st = le.activity_state(st, NOW + 7 * DAY)                   # next week: weekly reset
    assert st["weekly"] == 0 and st["weekly_tiers"] == [le.UNMET]


def test_tier_props_repeat_per_count(le):
    st = le.activity_state(None, NOW)
    st["daily"] = 70
    props, _calls = le.tier_claim(st, False, 1)
    assert props == [203011, 203011]


def test_activity_table_without_the_client_file_is_the_shape_only_fallback(gw, monkeypatch, tmp_path):
    """No extract/daily_activity.json: no crash, the login sizes (14 activities, 4 daily and 2 weekly
    tiers) and nothing claimable, so the Get buttons answer with the unchanged state."""
    import lobby_events
    monkeypatch.setattr(lobby_events, "TABLE_FILE", str(tmp_path / "missing.json"))
    monkeypatch.setattr(lobby_events, "_table", None)
    table = lobby_events.activity_table()
    assert table["source"] == "fallback" and table["activities"] == {}
    assert [t["points"] for t in table["daily"]] == [30, 60, 90, 120]
    assert [t["points"] for t in table["weekly"]] == [300, 600]
    st = lobby_events.activity_state(None, NOW)
    assert len(st["progress"]) == 14 and len(st["state"]) == 14
    assert lobby_events.activity_claim(st, 0) == []
    assert lobby_events.tier_claim(st, False, 0) == ([], [])
    assert lobby_events.activity_claim(st, 999) == []                   # out of range: nothing


def test_activity_buttons_answer_with_the_state_when_nothing_is_claimable(gw, udp, recorder, monkeypatch,
                                                                          tmp_path):
    import lobby_events
    monkeypatch.setattr(lobby_events, "TABLE_FILE", str(tmp_path / "missing.json"))
    monkeypatch.setattr(lobby_events, "_table", None)
    for method in ("getActivityReward", "getDailyActivityReward", "getWeeklyActivityReward"):
        recorder.clear()
        udp._athlete_request(ADDR, method, i32(0))
        assert [n for n, _ in recorder] == ["syncDailyActivity", "syncDailyActivityRewardState",
                                            "syncWeeklyActivity", "syncWeeklyActivityRewardState",
                                            "syncActivityProgress", "syncActivityState"]


def test_activity_tier_claim_grants_props_once_per_account(le, udp, recorder, gw, monkeypatch):
    monkeypatch.setenv("CBP_GID", "111")
    st = le.activity_state(None, gw.athlete_requests.game_now())
    st["daily"] = 30
    gw.save_account("activity:111", st)
    udp._athlete_request(ADDR, "getDailyActivityReward", i32(0))
    assert args_of(recorder, "onGetActivityReward") == [struct.pack("<Ii", 1, 200027)]
    recorder.clear()
    udp._athlete_request(ADDR, "getDailyActivityReward", i32(0))       # already GOT
    assert args_of(recorder, "onGetActivityReward") == []
    monkeypatch.setenv("CBP_GID", "222")                              # other account: its own state
    recorder.clear()
    udp._athlete_request(ADDR, "getDailyActivityReward", i32(0))
    assert args_of(recorder, "onGetActivityReward") == []


@pytest.mark.xfail(strict=True, reason="GAP: extract/daily_activity.json (activity kinds, counts, points, tier "
                   "props) is not extracted from the client yet (RosGG has no copy either); needs a read-only "
                   "Frida dump of iterDailyActivityData / getActivityRewardData on a device")
def test_activity_table_loads_from_the_repository(gw):
    import lobby_events
    assert (GATEWAY_SERVER / "extract" / "daily_activity.json").exists()
    table = lobby_events.activity_table()
    assert table["activities"]


@pytest.mark.parametrize("method", ["getActivityReward", "getDailyActivityReward", "getWeeklyActivityReward"])
def test_activity_claim_requests_reach_lobby_events(le, udp, monkeypatch, method):
    seen = []
    real_claim, real_tier = le.activity_claim, le.tier_claim
    monkeypatch.setattr(le, "activity_claim", lambda st, aid: seen.append(("activity", aid)) or real_claim(st, aid))
    monkeypatch.setattr(le, "tier_claim", lambda st, weekly, idx: seen.append(("tier", weekly, idx))
                        or real_tier(st, weekly, idx))
    udp._athlete_request(ADDR, method, i32(0))
    assert seen, "the request never reached lobby_events"
