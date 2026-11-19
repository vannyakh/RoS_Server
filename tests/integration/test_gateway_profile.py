"""Profile data for the original client's My Page, Stats and Credit screens."""

import pytest

KEY = "test-gateway-key"


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    monkeypatch.setattr(settings, "gateway_current_season", 21)
    return {"X-Gateway-Key": KEY}


async def _resolve(client, headers, uid="9020785644"):
    response = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": uid}, headers=headers)
    assert response.status_code == 200
    return response.json()


def _row(profile, season, queue, team_mode):
    rows = [r for r in profile["records"] if (r["season"], r["queue"], r["team_mode"]) == (season, queue, team_mode)]
    assert len(rows) == 1, rows
    return rows[0]


async def test_a_new_player_has_default_credit_and_no_records(client, gateway_key):
    await _resolve(client, gateway_key)
    response = await client.get("/api/v1/gateway/accounts/9020785644/profile", headers=gateway_key)
    assert response.status_code == 200
    body = response.json()
    assert body["rank_score"] == 0
    assert body["space_likes"] == 0
    assert body["current_season"] == 21
    assert body["records"] == []
    assert body["credit"] == {"score": 100, "status_last_week": 0, "weeks": 0, "gifts": [], "records": []}


async def test_profile_needs_the_gateway_key_and_a_known_uid(client, gateway_key):
    assert (await client.get("/api/v1/gateway/accounts/9020785644/profile")).status_code == 401
    unknown = await client.get("/api/v1/gateway/accounts/123/profile", headers=gateway_key)
    assert unknown.status_code == 404


async def test_a_match_updates_season_all_time_mode_and_overall_rows(client, gateway_key):
    await _resolve(client, gateway_key)
    first = {
        "queue": "ranked", "team_mode": "solo", "placement": 1, "kills": 7, "deaths": 0, "assists": 2,
        "damage": 1450, "head_shots": 4, "hits": 30, "fires": 90, "fight_time_seconds": 1500,
        "collect_count": 40, "heal_count": 3, "kill_distance_dm": 2340, "move_distance_dm": 52000,
        "rank_score_delta": 25,
    }
    second = {
        "queue": "ranked", "team_mode": "solo", "placement": 9, "kills": 13, "deaths": 1,
        "kill_distance_dm": 800, "fight_time_seconds": 600, "rank_score_delta": -5,
    }
    for report in (first, second):
        response = await client.post("/api/v1/gateway/accounts/9020785644/matches", json=report, headers=gateway_key)
        assert response.status_code == 200
    profile = response.json()

    assert profile["rank_score"] == 20
    assert len(profile["records"]) == 4   # season 21 and all-time, each for solo and overall
    for season in (21, 0):
        for mode in ("solo", "overall"):
            row = _row(profile, season, "ranked", mode)
            assert row["fight_count"] == 2
            assert row["win_count"] == 1
            assert row["top5_count"] == 1
            assert row["kill_count"] == 20
            assert row["death_count"] == 1
            assert row["max_round_kill"] == 13
            assert row["max_kill_distance_dm"] == 2340
            assert row["max_move_distance_dm"] == 52000
            assert row["fight_time_seconds"] == 2100
            assert row["max_fight_time_seconds"] == 1500


async def test_a_match_also_counts_on_the_web_profile(client, gateway_key):
    account = await _resolve(client, gateway_key)
    report = {"team_mode": "quad", "placement": 1, "kills": 3, "deaths": 1, "fight_time_seconds": 900}
    await client.post("/api/v1/gateway/accounts/9020785644/matches", json=report, headers=gateway_key)

    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.player import Player, PlayerStatistics

    async with SessionLocal() as session:
        player = await session.scalar(select(Player).where(Player.account_id == account["account_id"]))
        stats = await session.scalar(select(PlayerStatistics).where(PlayerStatistics.player_id == player.id))
    assert (stats.total_matches, stats.total_wins, stats.total_kills, stats.total_deaths) == (1, 1, 3, 1)
    assert stats.total_playtime_seconds == 900


async def test_match_reports_are_validated(client, gateway_key):
    await _resolve(client, gateway_key)
    for bad in ({"placement": 0}, {"placement": 1, "team_mode": "overall"}, {"placement": 1, "queue": "x"}):
        response = await client.post("/api/v1/gateway/accounts/9020785644/matches", json=bad, headers=gateway_key)
        assert response.status_code == 422, bad


async def test_credit_reward_is_granted_once(client, gateway_key):
    await _resolve(client, gateway_key)
    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.gateway import GatewayIdentity

    async with SessionLocal() as session:
        identity = await session.scalar(select(GatewayIdentity).where(GatewayIdentity.external_uid == "9020785644"))
        identity.credit_status_last_week = 2
        identity.credit_weeks = 3
        identity.credit_gifts = [299054, 490857]
        await session.commit()

    claimed = await client.post("/api/v1/gateway/accounts/9020785644/credit/claim", headers=gateway_key)
    assert claimed.status_code == 200
    assert claimed.json()["awards"] == [299054, 490857]
    assert claimed.json()["credit"]["gifts"] == []
    assert claimed.json()["credit"]["status_last_week"] == 2

    again = await client.post("/api/v1/gateway/accounts/9020785644/credit/claim", headers=gateway_key)
    assert again.json()["awards"] == []

    state = await client.get("/api/v1/gateway/accounts/9020785644/state", headers=gateway_key)
    assert {i["prop_id"] for i in state.json()["items"]} >= {299054, 490857}
