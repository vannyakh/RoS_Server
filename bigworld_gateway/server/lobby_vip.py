"""VIP Privilege screen (ui.UIVipPrivilege, entities iVip).

The client keeps player.vipInfo keyed by card type (const.Vip.TYPE_SILVER 0, TYPE_GOLD 1):
    {0: {"level": int, "rewardStatus": {level: status}, "num": top-up total, "redPoint": bool,
         "activeTime": start ts}, 1: {...}}
dts_vip_utils.hasRewardAvailable walks vipInfo.iteritems() -> info["rewardStatus"].iteritems(),
getFirstAvailableLevel reads vipInfo[type]["level"] and ["rewardStatus"][level], and
lucky_carnival_common reads vipInfo[TYPE_SILVER]["level"]. Status: REWARD_NA 0, AVAILABLE 1, DONE 2.

Levels come from VIP_SILVER_LEVEL / VIP_GOLD_LEVEL (default 0); the gold level never exceeds the
silver level (the client's "Gold VIP level cannot be higher than Silver VIP level"). Claimed
rewards are saved per account in saved_accounts.json ("vip:<gid>").
"""
import json
import os
import time

SILVER, GOLD = 0, 1
NA, AVAILABLE, DONE = 0, 1, 2

_table = None


def table():
    """{"max": {type: max level}, "levels": {type: {level: {"props", "top_up"}}}} (int keys)."""
    global _table
    if _table is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "vip_levels.json"),
                  encoding="utf-8") as f:
            raw = json.load(f)
        _table = {"max": {int(t): int(v) for t, v in raw["max"].items()},
                  "levels": {int(t): {int(lv): v for lv, v in lvs.items()} for t, lvs in raw["levels"].items()}}
    return _table


def levels():
    t = table()["max"]
    silver = max(0, min(t[SILVER], int(os.environ.get("VIP_SILVER_LEVEL", "0") or 0)))
    gold = max(0, min(t[GOLD], silver, int(os.environ.get("VIP_GOLD_LEVEL", "0") or 0)))
    return {SILVER: silver, GOLD: gold}


def vip_info(claimed):
    """player.vipInfo for syncVipInfo. `claimed`: {type: set(levels)}."""
    lv = levels()
    now = int(time.time())
    days = int(os.environ.get("VIP_CARD_DAYS", "30"))
    info = {}
    for t in (SILVER, GOLD):
        status = {}
        for level in range(1, table()["max"][t] + 1):
            if level in claimed.get(t, ()):
                status[level] = DONE
            elif level <= lv[t]:
                status[level] = AVAILABLE
            else:
                status[level] = NA
        # num: top-up total for this card (UIVipPrivilege.setRightPanel progress vs TOP_UP_NUM);
        # activeTime: card start, the timer shows activeTime + 30 days - now (refreshTimer).
        row = table()["levels"].get(t, {}).get(lv[t])
        # redPoint: red badge on the card (UIVipPrivilege.refreshVipinfo).
        info[t] = {"level": lv[t], "rewardStatus": status, "num": int(row["top_up"]) if row else 0,
                   "redPoint": any(s == AVAILABLE for s in status.values()),
                   "activeTime": now - (30 - days) * 86400 if lv[t] else 0}
    return info


def reward_props(vip_type, level):
    row = table()["levels"].get(int(vip_type), {}).get(int(level))
    return list(row["props"]) if row else []
