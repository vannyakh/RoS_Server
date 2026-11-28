"""Leaderboard ("data" tab, ui.UIRankPanel) for the original client.

Read with client/frida/payloads/rank_dis.py, rank_panel_dis.py, rank_types.py:
  requireRankList(INT32 rankType, INT32 bufVersion, INT32 bufLength, BOOL nextBatch)
      -> onRequireBattleGround{Force,Winning,Killing}RankList(INT32 start, ARRAY rows, INT32 version, INT32 rankType)
      The reply method follows rank_list_utils.RANK_LIST_TYPE_DTS_{FORCE,WINNING,KILLING}_LIST.
      RankList.onGetRankData keeps rows when version changes and start == 0, appends when
      start == len(buffer) (nextBatch).
  requireRankInfo(INT32 rankType) -> onGetPlayerBattleGroundRank(INT32 rankType, PY_DICT
      {"rank": n, "col-3".."col-6"}) (bottom "my rank" row; n <= 0 shows ".", the name comes
      from the player's baseNickname; rates are fractions shown as value * 100 %).
  updatePlayerLBSData(STRING admin, STRING subAdmin) -> onUpdatePlayerLBSData(admin, subAdmin)
  requestLBSRankList / requestLBSPlayerRank -> onGetLBSRank(PYTHON [{"RankName", "Rank"}])

Row types (alias.xml, Parent fields first): RANK_DATA gid GID, nickname STRING, nationalFlag STRING,
value INT32; BATTLE_GROUND_RANK_DATA + identifyTagID INT32; then
  DTS_FORCE_RANK_DATA  winRate FLOAT, topFiveRate FLOAT, killDeathRate FLOAT
  DTS_WIN_RANK_DATA    winRate FLOAT, topFiveCount UINT32, topFiveRate FLOAT
  DTS_KILL_RANK_DATA   killCombo UINT16, killDeathRate FLOAT, headshotRate FLOAT

Players are the accounts this server knows (the current player from RoS_Server's profile, or the
local account); no invented entries.
"""
import struct

FORCE = (36, 35, 85, 96, 97)
WINNING = tuple(range(37, 52)) + (67, 69, 75, 77, 79, 81, 86, 87, 88, 89, 90)
KILLING = tuple(range(52, 67)) + (68, 70, 76, 78, 80, 82, 91, 92, 93, 94, 95)
QUEUES = ("total", "ranked", "matching")
MODES = ("overall", "solo", "dual", "quad", "five")
VERSION = 1


def _blob(b):
    if isinstance(b, str):
        b = b.encode()
    return (bytes([len(b)]) if len(b) < 255 else b"\xff" + struct.pack("<I", len(b))[:3]) + b


def kind(rank_type):
    if rank_type in FORCE:
        return "force"
    if rank_type in WINNING:
        return "winning"
    if rank_type in KILLING:
        return "killing"
    return None


def reply_method(rank_type):
    return {"force": "onRequireBattleGroundForceRankList", "winning": "onRequireBattleGroundWinningRankList",
            "killing": "onRequireBattleGroundKillingRankList"}.get(kind(rank_type))


def _queue_mode(rank_type):
    """Record row (queue, team mode) behind a rank type: 37-51 winning and 52-66 killing are
    Total/Ranked/Matching x Overall/Solo/Dual/Quad/Five; 36 is ranked overall; the rest overall."""
    for first in (37, 52):
        if first <= rank_type < first + 15:
            q, m = divmod(rank_type - first, 5)
            return QUEUES[q], MODES[m]
    return ("ranked" if rank_type == 36 else "total"), "overall"


def _record(profile, queue, mode):
    for row in (profile or {}).get("records", []):
        if (row.get("season"), row.get("queue"), row.get("team_mode")) == (0, queue, mode):
            return row
    return {}


def player_cols(rank_type, profile):
    """Columns 3-6 of the "my rank" row (ui.UIRankPanel *Component.infoInitFunc reads
    rankInfo['col-3'..'col-6']; rates are fractions, the client shows value * 100 %)."""
    k = kind(rank_type)
    rec = _record(profile, *_queue_mode(rank_type))
    fights = rec.get("fight_count", 0)
    wins, top5 = rec.get("win_count", 0), rec.get("top5_count", 0)
    kills, deaths = rec.get("kill_count", 0), rec.get("death_count", 0)
    win_rate = wins / fights if fights else 0.0
    top5_rate = top5 / fights if fights else 0.0
    kd = kills / max(deaths, 1) if fights else 0.0
    hs_rate = rec.get("head_shot_count", 0) / kills if kills else 0.0
    if k == "force":
        return [int((profile or {}).get("rank_score", 0)), win_rate, top5_rate, kd]
    if k == "winning":
        return [wins, win_rate, top5, top5_rate]
    return [kills, rec.get("max_round_kill", 0), kd, hs_rate]     # Kills, Most Kill, KDR, headshot


def player_row(rank_type, gid, nickname, profile):
    """(sort value, encoded row) for one player."""
    k = kind(rank_type)
    rec = _record(profile, *_queue_mode(rank_type))
    fights = rec.get("fight_count", 0)
    wins, top5 = rec.get("win_count", 0), rec.get("top5_count", 0)
    kills, deaths = rec.get("kill_count", 0), rec.get("death_count", 0)
    win_rate = wins / fights if fights else 0.0
    top5_rate = top5 / fights if fights else 0.0
    kd = kills / max(deaths, 1) if fights else 0.0
    hs_rate = rec.get("head_shot_count", 0) / kills if kills else 0.0
    value = {"force": int((profile or {}).get("rank_score", 0)), "winning": wins, "killing": kills}[k]
    head = struct.pack("<Q", int(gid)) + _blob(nickname) + _blob((profile or {}).get("national_flag", "")) + \
        struct.pack("<ii", value, 0)
    if k == "force":
        tail = struct.pack("<fff", win_rate, top5_rate, kd)
    elif k == "winning":
        tail = struct.pack("<fIf", win_rate, top5, top5_rate)
    else:
        tail = struct.pack("<Hff", rec.get("max_round_kill", 0), kd, hs_rate)
    return value, head + tail


def rank_list(rank_type, players):
    """players: [(gid, nickname, profile)] -> (encoded ARRAY, {gid: rank})."""
    rows = sorted((player_row(rank_type, gid, name, prof) + (gid,) for gid, name, prof in players),
                  key=lambda r: -r[0])
    ranks = {gid: i + 1 for i, (_v, _row, gid) in enumerate(rows)}
    return struct.pack("<I", len(rows)) + b"".join(r for _v, r, _g in rows), ranks


def list_reply_args(rank_type, next_batch, buf_length, players):
    """Arguments for the list reply: (start, rows, version, rankType). A next-batch request gets
    no more rows (the whole list fits in the first batch)."""
    rows, _ranks = rank_list(rank_type, players)
    if next_batch:
        return struct.pack("<iIii", buf_length, 0, VERSION, rank_type)
    return struct.pack("<i", 0) + rows + struct.pack("<ii", VERSION, rank_type)


def own_rank(rank_type, gid, players):
    _rows, ranks = rank_list(rank_type, players)
    return ranks.get(gid, 0)


def own_info(rank_type, gid, players):
    """onGetPlayerBattleGroundRank's dict: rank plus col-3..col-6 (missing cols raise KeyError
    in infoInitFunc and leave the row showing 00000 placeholders)."""
    info = {"rank": own_rank(rank_type, gid, players)}
    profile = next((p for g, _n, p in players if g == gid), None)
    for i, v in enumerate(player_cols(rank_type, profile)):
        info["col-%d" % (i + 3)] = v
    return info
