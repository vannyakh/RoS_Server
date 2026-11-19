"""bigworld_gateway builds the client's Stats / My Page / Credit replies from RoS_Server's profile."""

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def screens(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    module = importlib.import_module("profile_screens")
    yield importlib.reload(module)
    sys.modules.pop("profile_screens", None)


# const.RecordTypeToName entries read from the running client.
CLIENT_NAMES = {
    1: "BattleGroundTotalOverallRecord",
    2: "BattleGroundRankTotalOverallRecord",
    3: "BattleGroundTotalSoloRecord",
    11: "BattleGroundRankedOverallRecord",
    21: "BattleGroundMatchingOverallRecord",
    30: "BattleGroundRankMatchingFiveRecord",
    31: "BattleGroundSeasonTotalOverallRecord",
    32: "BattleGroundRankSeasonTotalOverallRecord",
    43: "BattleGroundSeasonRankedSoloRecord",
    59: "BattleGroundSeasonMatchingFiveRecord",
}


@pytest.mark.parametrize(("record_type", "name"), sorted(CLIENT_NAMES.items()))
def test_record_type_names_match_the_client(screens, record_type, name):
    assert screens.record_type_name(record_type) == name


def test_unknown_record_types_get_no_name(screens):
    assert screens.record_type_name(0) is None
    assert screens.record_type_name(61) is None
    assert screens.record_data(None, 1001) == {}


PROFILE = {
    "nickname": "Raven",
    "level": 4,
    "rank_score": 1350,
    "space_likes": 7,
    "current_season": 21,
    "char_type": 20001,
    "portrait": "",
    "credit": {"score": 140, "status_last_week": 2, "weeks": 3, "gifts": [299054], "records": []},
    "records": [
        {"season": 21, "queue": "total", "team_mode": "overall", "fight_count": 8, "win_count": 2,
         "top5_count": 3, "kill_count": 40, "death_count": 6, "damage": 9000, "head_shot_count": 10,
         "hit_count": 50, "fire_count": 200, "fight_time_seconds": 7200, "collect_count": 300,
         "max_round_kill": 13, "max_round_heal": 4, "max_kill_distance_dm": 2340,
         "max_move_distance_dm": 22000, "max_fight_time_seconds": 1500},
        {"season": 0, "queue": "total", "team_mode": "overall", "fight_count": 100, "win_count": 9,
         "top5_count": 20},
    ],
}


def test_season_overall_stats_carry_the_keys_the_stats_panel_reads(screens):
    data = screens.record_data(PROFILE, 31)
    detail = data["BattleGroundSeasonTotalOverallRecord"]
    summary = data["BattleGroundRankSeasonTotalOverallRecord"]
    assert summary == {"fightCount": 8, "firstNum": 2, "top5Rate": 37.5}
    assert detail["maxRoundKill"] == 13
    assert detail["maxKillDis"] == 2340           # client shows /10 -> 234 M
    assert detail["maxRoundMoveDis"] == 22000     # client shows /10000 -> 2.2 KM
    assert (detail["headShot"], detail["hitCount"], detail["fireCount"]) == (10, 50, 200)
    for radar_key in ("kill", "dead", "damage", "fightTime", "collectCount"):
        assert radar_key in detail


def test_all_time_reads_season_zero_and_missing_rows_are_zero(screens):
    assert screens.record_data(PROFILE, 1)["BattleGroundRankTotalOverallRecord"]["fightCount"] == 100
    empty = screens.record_data(PROFILE, 13)["BattleGroundRankRankedSoloRecord"]
    assert empty == {"fightCount": 0, "firstNum": 0, "top5Rate": 0.0}


def test_rank_record_types_are_not_answered_directly(screens):
    assert screens.record_data(PROFILE, 32) == {}


def test_unlinked_players_get_defaults(screens):
    assert screens.credit(None) == (100, 0, 0, [], [])
    assert screens.base_info(None, "Guest") == ("Guest", 0, 1)
    assert screens.space_likes(None) == 0


def test_credit_and_personal_info(screens):
    assert screens.credit(PROFILE) == (140, 2, 3, [299054], [])
    info = screens.personal_info(PROFILE, 9020785644, "Guest", 30001, "")
    assert info == {"gid": 9020785644, "nickname": "Raven", "characterType": 20001, "protrait": "",
                    "nationalFlag": "", "dtsLevel": 4, "score": 1350}
