"""Lane 2 lobby events: daily sign-in (UIDtsSign) and Benefits > Activity Points (daily/weekly missions).

Every function returns a list of (Athlete client method name, packed args); ros_server wraps them with
athlete_method. State lives in saved_accounts.json through the load/save callables the caller passes.

Sign-in (client iDtsSignin): the popup opens when checkDtsSigninNotSameDay() (the calendar day of
childBaseClientProperty.signAwardTime differs from server time) and signAwardLevel < DTS_SIGN_IN_AWARD_MAX.
childBaseClientPropertyList cannot be sent at login (stream bug, LOBBY_FINDINGS 5), but the client methods
onSetSignAwardTime(INT32) / onSetSignAwardLevel(INT32) set the same two fields, so the gateway sends them at
login with the stored claim and after each claim.

Daily activity (client iDailyActivity / ui.UIDailyActivity): activities (properties.iterDailyActivityData)
are done when progress >= count; "Get" (getActivityReward(idx)) adds their points to the daily and weekly
totals; tier boxes (getDailyActivityReward(i) / getWeeklyActivityReward(i)) open when the total reaches the
tier and award props (onGetActivityReward(ARRAY INT32)). States are const.RewardState: 0 UnmetNeeds,
1 MetNeeds, 2 GotReward. Daily values reset each game day, weekly values each ISO week.
"""
import json
import os
import struct
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
UNMET, MET, GOT = 0, 1, 2

# Daily sign-in rewards by day (client legacyProperties.iterDtsSigninData, days 1-5).
SIGNIN_AWARDS = [200027, 203011, 200012, 203012, 291210]


def _i32(v):
    return struct.pack("<i", int(v))


def _arr(fmt, vals):
    return struct.pack("<I", len(vals)) + b"".join(struct.pack(fmt, int(v)) for v in vals)


def day_of(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def week_of(ts):
    import datetime
    y, w, _d = datetime.datetime.utcfromtimestamp(ts).isocalendar()
    return "%d-W%02d" % (y, w)


# ---------------------------------------------------------------- sign-in

def signin_login_calls(state):
    """Calls for login: the last claim time and level, so a claim today keeps the popup closed."""
    st = state or {}
    calls = []
    if int(st.get("ts") or 0) > 0:
        calls.append(("onSetSignAwardTime", _i32(st["ts"])))
    if int(st.get("level") or 0) > 0:
        calls.append(("onSetSignAwardLevel", _i32(st["level"])))
    return calls


def signin_claim(state, now):
    """(new state, award prop id or None, calls). One claim per game day; a second claim the same day
    only resends the stored time/level (the client then sees "signed today" and closes the popup)."""
    st = dict(state or {"level": 0, "day": ""})
    today = day_of(now)
    if st.get("day") == today:
        st.setdefault("ts", int(now))
        return st, None, signin_login_calls(st)
    level = min(int(st.get("level") or 0) + 1, len(SIGNIN_AWARDS))
    st = {"level": level, "day": today, "ts": int(now)}
    award = SIGNIN_AWARDS[level - 1]
    calls = [("onSetSignAwardTime", _i32(now)),
             ("onRequestDtsSignInAward", _arr("<i", [award]) + _i32(level))]
    return st, award, calls


# ---------------------------------------------------------------- daily activity (missions)

_table = None


def activity_table():
    """extract/daily_activity.json (read from the client: iterDailyActivityData, getActivityRewardData)."""
    global _table
    if _table is None:
        path = os.path.join(_HERE, "extract", "daily_activity.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        _table = {"activities": {int(k): v for k, v in raw["activities"].items()},
                  "daily": raw["daily_tiers"], "weekly": raw["weekly_tiers"]}
    return _table


def _fresh(now, old=None):
    t = activity_table()
    n = max(t["activities"]) + 1 if t["activities"] else 0
    st = {"day": day_of(now), "week": week_of(now), "progress": [0] * n, "state": [UNMET] * n,
          "daily": 0, "daily_tiers": [UNMET] * len(t["daily"]),
          "weekly": 0, "weekly_tiers": [UNMET] * len(t["weekly"])}
    if old and old.get("week") == st["week"]:          # same week: weekly points survive the daily reset
        st["weekly"] = int(old.get("weekly") or 0)
        st["weekly_tiers"] = list(old.get("weekly_tiers") or st["weekly_tiers"])
    return st


def activity_state(state, now):
    """Stored state, reset when the game day (daily part) or the week (weekly part) changed."""
    st = state or {}
    if st.get("day") == day_of(now) and st.get("week") == week_of(now) and "progress" in st:
        return st
    return _fresh(now, st)


def _tiers(points, tiers, states):
    return [s if s == GOT else (MET if points >= int(t["points"]) else UNMET) for t, s in zip(tiers, states)]


def activity_sync_calls(st):
    t = activity_table()
    st["daily_tiers"] = _tiers(st["daily"], t["daily"], st["daily_tiers"])
    st["weekly_tiers"] = _tiers(st["weekly"], t["weekly"], st["weekly_tiers"])
    return [("syncDailyActivity", _i32(st["daily"])),
            ("syncDailyActivityRewardState", _arr("<b", st["daily_tiers"])),
            ("syncWeeklyActivity", _i32(st["weekly"])),
            ("syncWeeklyActivityRewardState", _arr("<b", st["weekly_tiers"])),
            ("syncActivityProgress", _arr("<i", st["progress"])),
            ("syncActivityState", _arr("<b", st["state"]))]


def activity_event(st, kind, amount=1):
    """Add progress to every activity of `kind` (table field "kind"); returns the calls for the changes."""
    calls = []
    for aid, a in activity_table()["activities"].items():
        if a.get("kind") != kind or st["state"][aid] == GOT:
            continue
        st["progress"][aid] = min(st["progress"][aid] + int(amount), int(a["count"]))
        calls.append(("syncSingleActivityProgress", _i32(aid) + _i32(st["progress"][aid])))
        if st["progress"][aid] >= int(a["count"]) and st["state"][aid] == UNMET:
            st["state"][aid] = MET
            calls.append(("syncSingleActivityState", _i32(aid) + struct.pack("<b", MET)))
    return calls


def activity_claim(st, aid):
    """getActivityReward(idx): MET -> GOT and add the points. Returns calls ([] if not claimable)."""
    a = activity_table()["activities"].get(int(aid))
    if a is None or st["state"][aid] != MET:
        return []
    st["state"][aid] = GOT
    st["daily"] += int(a["points"])
    st["weekly"] += int(a["points"])
    return [("syncSingleActivityState", _i32(aid) + struct.pack("<b", GOT))] + activity_sync_calls(st)


def tier_claim(st, weekly, idx):
    """getDailyActivityReward / getWeeklyActivityReward(idx): (prop ids, calls). Nothing unless MET."""
    t = activity_table()
    tiers, key = (t["weekly"], "weekly_tiers") if weekly else (t["daily"], "daily_tiers")
    activity_sync_calls(st)                       # refresh MET flags from the totals
    if not 0 <= idx < len(tiers) or st[key][idx] != MET:
        return [], []
    st[key][idx] = GOT
    props = [int(p) for p, n in tiers[idx]["props"] for _ in range(max(int(n), 1))]
    single = "syncSingleWeeklyActivityRewardState" if weekly else "syncSingleDailyActivityRewardState"
    return props, [(single, _i32(idx) + struct.pack("<b", GOT)), ("onGetActivityReward", _arr("<i", props))]
