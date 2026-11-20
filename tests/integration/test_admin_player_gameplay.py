"""Operators change a player's gameplay state through audited, permission-checked routes."""

import pytest

PASSWORD = "StrongTestPassword123!"
KEY = "test-gateway-key"


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    return {"X-Gateway-Key": KEY}


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def _game_player(client, gateway_key) -> str:
    resolved = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9100000001"}, headers=gateway_key
    )
    assert resolved.status_code == 200
    return resolved.json()["account_id"]


async def test_gameplay_profile_edit_is_applied_and_audited(client, gateway_key):
    account_id = await _game_player(client, gateway_key)
    headers = await _operator(client, "gameplay_support", ["support"])

    edited = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile",
        headers=headers,
        json={
            "level": 12,
            "experience": 3400,
            "char_type": 2,
            "outfit": {"body": [101, 102], "wear": [5001]},
            "rank_score": 1500,
            "credit_score": 120,
            "reason": "Restore progress lost in a crash.",
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["level"] == 12
    assert body["experience"] == 3400
    assert body["online"] is False
    gateway = body["gateway"]
    assert gateway["char_type"] == 2
    assert gateway["outfit"] == {"body": [101, 102], "wear": [5001]}
    assert gateway["rank_score"] == 1500
    assert gateway["credit_score"] == 120

    profile = await client.get("/api/v1/gateway/accounts/9100000001/profile", headers=gateway_key)
    credit = profile.json()["credit"]
    assert credit["score"] == 120
    assert credit["records"][0]["delta"] == 20
    assert credit["records"][0]["reason"] == -1

    unchanged = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=headers, json={"level": 12, "reason": "No change."}
    )
    assert unchanged.status_code == 422

    too_high = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=headers, json={"credit_score": 161, "reason": "Cap check."}
    )
    assert too_high.status_code == 422

    audit = await client.get("/api/v1/admin/audit", headers=headers)
    assert any(row["action"] == "player.profile" and "credit_score 100 -> 120" in row["detail"] for row in audit.json())


async def test_web_accounts_reject_client_only_fields(client):
    created = await client.post("/api/v1/auth/register", json={"username": "web_only_player", "password": PASSWORD})
    account_id = created.json()["id"]
    headers = await _operator(client, "web_support", ["support"])

    rejected = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=headers, json={"rank_score": 10, "reason": "Rank fix."}
    )
    assert rejected.status_code == 422
    leveled = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=headers, json={"level": 3, "reason": "Level fix."}
    )
    assert leveled.status_code == 200
    assert leveled.json()["level"] == 3


async def test_adjustments_never_go_below_zero(client, gateway_key):
    from app.infrastructure.database import SessionLocal
    from app.models.game_data import ItemDefinition

    account_id = await _game_player(client, gateway_key)
    headers = await _operator(client, "economy_support", ["support"])
    async with SessionLocal() as session:
        medkit = ItemDefinition(code="medkit_test", name="Medkit", category="healing")
        session.add(medkit)
        await session.commit()
        medkit_id = medkit.id

    url = f"/api/v1/admin/players/{account_id}/adjustments"
    granted = await client.post(url, headers=headers, json={"kind": "currency", "key": "GOLD", "delta": 500, "reason": "Event award."})
    assert granted.status_code == 200, granted.text
    assert {"currency_code": "gold", "balance": 500} in granted.json()["currencies"]
    overdrawn = await client.post(url, headers=headers, json={"kind": "currency", "key": "GOLD", "delta": -600, "reason": "Refund."})
    assert overdrawn.status_code == 409

    item = await client.post(url, headers=headers, json={"kind": "item", "key": medkit_id, "delta": 3, "reason": "Support grant."})
    assert item.status_code == 200
    held = {row["item_definition_id"]: row["quantity"] for row in item.json()["inventory"]}
    assert held[medkit_id] == 3
    emptied = await client.post(url, headers=headers, json={"kind": "item", "key": medkit_id, "delta": -3, "reason": "Take back."})
    assert medkit_id not in {row["item_definition_id"] for row in emptied.json()["inventory"]}

    prop = await client.post(url, headers=headers, json={"kind": "prop", "key": "70001", "delta": 1, "reason": "Outfit gift."})
    assert prop.status_code == 200
    assert prop.json()["gateway"]["props"] == [{"prop_id": 70001, "number": 1}]
    bad_prop = await client.post(url, headers=headers, json={"kind": "prop", "key": "abc", "delta": 1, "reason": "Bad id."})
    assert bad_prop.status_code == 422
    zero = await client.post(url, headers=headers, json={"kind": "currency", "key": "GOLD", "delta": 0, "reason": "Nothing."})
    assert zero.status_code == 422


async def test_gameplay_edits_need_their_own_permissions(client, gateway_key):
    account_id = await _game_player(client, gateway_key)
    headers = await _operator(client, "dashboard_only", ["game_admin"])

    progress = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=headers, json={"level": 5, "reason": "Try it."}
    )
    assert progress.status_code == 403
    economy = await client.post(
        f"/api/v1/admin/players/{account_id}/adjustments",
        headers=headers,
        json={"kind": "currency", "key": "GOLD", "delta": 1, "reason": "Try it."},
    )
    assert economy.status_code == 403
