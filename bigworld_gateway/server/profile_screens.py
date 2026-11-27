"""Replies for the original client's My Page, Stats and Credit screens.

Read from the client (ui.UIMeetMainPage.UIBattleGroundRecordPanel, ui.UICreditSystem,
ui.UIPersonalSpace; payloads in client/frida, bytecode compared in the running game):

- Stats: requireRecordData(gid, recordType) -> onGetRecordData(gid, data). The panel needs
  data[RecordTypeToName[recordType]] (detail: kills, headshots, distances, radar values) and
  data[RecordTypeToName[recordType + 1]] (the "Rank" record: fightCount, firstNum = wins,
  top5Rate in percent). recordType is odd. 1..30 are all-time and 31..60 the current season,
  each in blocks of ten: Total, Ranked, Matching; inside a block Overall, Solo, Dual, Quad, Five.
- Base info: requireBaseInfo(gid) -> onGetBaseInfo(gid, nickname, isFriend, score, serverID,
  identifyTagID, dtsLevel, nationalFlag). score is the ranked score behind the tier badge.
- Credit: queryCreditScore() -> queryCreditScoreCB(score, records) and
  syncCreditStatus(statusLastWeek, consecutiveWeeks, giftPropIds). requireCreditReward() ->
  requireCreditRewardCB(awardPropIds).
- My Page: queryPersonalInfo(gid) -> queryPersonalInfoCB(gid, info) with the keys
  UIPersonalSpace._getPersonInfo reads; queryPersonalSpaceLikeCnt -> queryPersonalSpaceLikeCntCB.

The profile dict is RoS_Server's GET /api/v1/gateway/accounts/{uid}/profile body. Without the
link every screen gets zeros, which is what a new player has.
"""

import hero_rules


QUEUES = ("total", "ranked", "matching")
TEAM_MODES = ("overall", "solo", "dual", "quad", "five")
_QUEUE_NAMES = {"total": "Total", "ranked": "Ranked", "matching": "Matching"}
_MODE_NAMES = {m: m.capitalize() for m in TEAM_MODES}
LAST_RECORD_TYPE = 60

# Credit history rows the client list cannot be checked against yet: send none.
SEND_CREDIT_HISTORY = False


def record_key(record_type):
    """(season_block, queue, team_mode, is_rank_record) for a client record type, or None."""
    if not 1 <= record_type <= LAST_RECORD_TYPE:
        return None
    index = record_type - 1
    season_block, index = divmod(index, 30)
    queue_index, index = divmod(index, 10)
    mode_index, rank = divmod(index, 2)
    return season_block == 1, QUEUES[queue_index], TEAM_MODES[mode_index], rank == 1


def record_type_name(record_type):
    """The client's const.RecordTypeToName entry, e.g. 31 -> BattleGroundSeasonTotalOverallRecord."""
    key = record_key(record_type)
    if key is None:
        return None
    seasonal, queue, mode, rank = key
    return "BattleGround{}{}{}{}Record".format(
        "Rank" if rank else "", "Season" if seasonal else "", _QUEUE_NAMES[queue], _MODE_NAMES[mode]
    )


def _row(profile, seasonal, queue, mode):
    season = (profile or {}).get("current_season", 1) if seasonal else 0
    for row in (profile or {}).get("records", []):
        if (row["season"], row["queue"], row["team_mode"]) == (season, queue, mode):
            return row
    return {}


def _top5_rate(row):
    fights = row.get("fight_count", 0)
    return round(row.get("top5_count", 0) * 100.0 / fights, 1) if fights else 0.0


def record_data(profile, record_type):
    """onGetRecordData's dict for one requested record type ({} for types this server does not keep)."""
    if record_key(record_type) is None or record_key(record_type)[3]:
        return {}
    seasonal, queue, mode, _rank = record_key(record_type)
    row = _row(profile, seasonal, queue, mode)
    fights = row.get("fight_count", 0)
    detail = {
        "fightCount": fights,
        "kill": row.get("kill_count", 0),
        "dead": row.get("death_count", 0),
        "damage": row.get("damage", 0),
        "fightTime": row.get("fight_time_seconds", 0),
        "collectCount": row.get("collect_count", 0),
        "headShot": row.get("head_shot_count", 0),
        "hitCount": row.get("hit_count", 0),
        "fireCount": row.get("fire_count", 0),
        "maxRoundKill": row.get("max_round_kill", 0),
        "maxRoundHealCount": row.get("max_round_heal", 0),
        "maxKillDis": row.get("max_kill_distance_dm", 0),
        "maxRoundMoveDis": row.get("max_move_distance_dm", 0),
        "maxFightTime": row.get("max_fight_time_seconds", 0),
    }
    summary = {"fightCount": fights, "firstNum": row.get("win_count", 0), "top5Rate": _top5_rate(row)}
    return {record_type_name(record_type): detail, record_type_name(record_type + 1): summary}


def base_info(profile, fallback_name):
    """(nickname, rank score, level) for onGetBaseInfo."""
    profile = profile or {}
    return profile.get("nickname") or fallback_name, int(profile.get("rank_score", 0)), int(profile.get("level", 1))


def credit(profile):
    """(score, status_last_week, weeks, gift prop ids, history rows) for the Credit screen."""
    c = (profile or {}).get("credit") or {}
    rows = c.get("records", []) if SEND_CREDIT_HISTORY else []
    return int(c.get("score", 100)), int(c.get("status_last_week", 0)), int(c.get("weeks", 0)), list(c.get("gifts", [])), rows


def national_flag(profile, fallback=""):
    return (profile or {}).get("national_flag") or fallback or ""


def personal_info(profile, gid, fallback_name, char_type, portrait):
    """queryPersonalInfoCB's dict (keys from UIPersonalSpace._getPersonInfo; 'protrait' is the client's spelling)."""
    profile = profile or {}
    return {
        "gid": gid,
        "nickname": profile.get("nickname") or fallback_name,
        "characterType": hero_rules.normalize_hero(profile.get("char_type") or char_type),
        # FilePicker id served by the gateway (portrait_file_id); this build has no built-in portraits.
        "protrait": profile.get("portrait") or portrait,
        "nationalFlag": national_flag(profile),
        "dtsLevel": int(profile.get("level", 1)),
        "score": int(profile.get("rank_score", 0)),
    }


def space_likes(profile):
    return int((profile or {}).get("space_likes", 0))


# --- Match exp and level up (21.07 / 21.08) --------------------------------------------------
# The client shows exp with Athlete.onAddDtsExp(INT32 dtsExp, INT32 dtsLevel, BOOL newLevelup)
# (iDtsLevelSystem; newLevelup True opens the level-up popup). ExpLevelTable[level].levelExp is the
# exp needed to leave that level (extract/level_exp.json). The original exp-per-match formula is not
# known; match_exp() is this server's own rule. battle_flow calls grant_match_exp() when a match ends;
# the lobby applies the pending exp at its next profile sync (ros_server._sync_lobby_portrait).
PENDING_EXP = {}   # gid -> exp earned in matches, not yet shown in the lobby


def match_exp(rank, total, kills=0):
    """Exp for one finished match: 20 base, +1 per player outlived, +10 per kill, +50 for a win."""
    rank, total, kills = max(int(rank), 1), max(int(total), 1), max(int(kills), 0)
    return 20 + max(total - rank, 0) + 10 * kills + (50 if rank == 1 else 0)


def grant_match_exp(gid, rank, total, kills=0):
    """Queue a match's exp for gid; returns the amount (for the result screen's "exp" row)."""
    amount = match_exp(rank, total, kills)
    PENDING_EXP[str(gid)] = PENDING_EXP.get(str(gid), 0) + amount
    return amount


def add_exp(level, exp, amount, level_exp):
    """(level, exp, levelled_up) after adding amount; level_exp maps level -> exp to leave it."""
    top = max(level_exp)
    level, exp = min(max(int(level), 1), top), max(int(exp), 0) + max(int(amount), 0)
    start = level
    while level < top and exp >= level_exp[level]:
        exp -= level_exp[level]
        level += 1
    if level == top:
        exp = min(exp, level_exp[top] - 1)
    return level, exp, level > start
