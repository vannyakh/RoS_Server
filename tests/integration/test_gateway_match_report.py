"""Gateway match reports: RoS_Server POST /matches and account_link.record_match (RO-070)."""

import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[2] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

KEY = "test-gateway-match-report"


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    return {"X-Gateway-Key": KEY}


async def _resolve(client, headers):
    response = await client.post(
        "/api/v1/gateway/accounts/resolve",
        json={"external_uid": "9020000070", "ip_address": "192.168.1.70"},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


async def test_match_report_updates_rank_and_statistics_exactly_once(client, gateway_key):
    """One POST updates rank_score and PlayerStatistics once; a second POST adds again (no id)."""
    uid = "9020000070"
    account = await _resolve(client, gateway_key)
    report = {
        "team_mode": "solo",
        "placement": 5,
        "kills": 4,
        "deaths": 1,
        "rank_score_delta": 10,
        "fight_time_seconds": 600,
    }
    first = await client.post(f"/api/v1/gateway/accounts/{uid}/matches", json=report, headers=gateway_key)
    assert first.status_code == 200
    assert first.json()["rank_score"] == 10

    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.player import Player, PlayerStatistics

    async with SessionLocal() as session:
        player = await session.scalar(select(Player).where(Player.account_id == account["account_id"]))
        stats = await session.scalar(select(PlayerStatistics).where(PlayerStatistics.player_id == player.id))
    assert stats.total_matches == 1
    assert stats.total_kills == 4
    assert stats.total_deaths == 1

    second = await client.post(
        f"/api/v1/gateway/accounts/{uid}/matches",
        json={**report, "kills": 1, "placement": 12},
        headers=gateway_key,
    )
    assert second.status_code == 200
    async with SessionLocal() as session:
        stats = await session.scalar(select(PlayerStatistics).where(PlayerStatistics.player_id == player.id))
    assert stats.total_matches == 2
    assert stats.total_kills == 5


def test_record_match_returns_none_without_link(monkeypatch):
    import account_link

    account_link._current = {"external_uid": "9000000001"}
    monkeypatch.setattr(
        account_link,
        "_setting",
        lambda name, default="": "" if name == "GATEWAY_API_KEY" else default,
    )
    assert account_link.record_match({"placement": 1, "kills": 0}) is None


def test_record_match_posts_to_matches_path(monkeypatch):
    import account_link

    monkeypatch.setenv("GATEWAY_API_KEY", "secret")
    account_link._current = {"external_uid": "9000000070"}
    seen = []

    def fake_call(method, path, body):
        seen.append((method, path, body))
        return {"rank_score": 42, "records": []}

    monkeypatch.setattr(account_link, "_call", fake_call)
    profile = account_link.record_match({"placement": 1, "kills": 2, "team_mode": "solo"})
    assert profile["rank_score"] == 42
    assert seen == [("POST", "/api/v1/gateway/accounts/9000000070/matches", {"placement": 1, "kills": 2, "team_mode": "solo"})]