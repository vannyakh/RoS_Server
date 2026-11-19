"""Support records stay behind the operator permission that owns each action."""

PASSWORD = "StrongTestPassword123!"


async def _support(client):
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator("support_admin", PASSWORD, ["support"], audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": "support_admin", "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_support_workflow_records_a_reason_and_does_not_punish_from_a_report(client):
    created = await client.post("/api/v1/auth/register", json={"username": "reported_player", "password": PASSWORD})
    assert created.status_code == 201
    account_id = created.json()["id"]
    token = await _support(client)
    headers = _headers(token)

    denied = await client.get("/api/v1/admin/support", headers={"Authorization": "Bearer player"})
    assert denied.status_code == 401

    found = await client.get("/api/v1/admin/players?q=reported_player", headers=headers)
    assert found.status_code == 200
    assert found.json()["items"][0]["id"] == account_id

    case = await client.post(
        "/api/v1/admin/support",
        headers=headers,
        json={
            "account_id": account_id,
            "subject": "Cannot sign in",
            "description": "The player reports a failed sign-in.",
            "category": "login",
            "priority": "high",
        },
    )
    assert case.status_code == 201
    case_id = case.json()["id"]
    note = await client.post(
        f"/api/v1/admin/support/{case_id}/notes",
        headers=headers,
        json={"body": "Checked the account status.", "visibility": "internal"},
    )
    assert note.status_code == 201
    resolved = await client.patch(
        f"/api/v1/admin/support/{case_id}",
        headers=headers,
        json={"status": "resolved", "resolution": "Password reset guidance sent."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["notes"][0]["visibility"] == "internal"

    report = await client.post(
        "/api/v1/admin/reports",
        headers=headers,
        json={"reported_account_id": account_id, "category": "gameplay", "description": "Reported for griefing."},
    )
    assert report.status_code == 201
    dismissed = await client.patch(
        f"/api/v1/admin/reports/{report.json()['id']}",
        headers=headers,
        json={"status": "dismissed", "resolution": "No evidence in the stored match."},
    )
    assert dismissed.status_code == 200
    still_active = await client.get(f"/api/v1/admin/players/{account_id}", headers=headers)
    assert still_active.json()["status"] == "active"

    banned = await client.post(
        f"/api/v1/admin/players/{account_id}/actions",
        headers=headers,
        json={"action": "ban", "reason": "Repeated confirmed abuse."},
    )
    assert banned.status_code == 200
    assert banned.json()["resulting_status"] == "closed"
    blocked = await client.post("/api/v1/auth/login", json={"username": "reported_player", "password": PASSWORD})
    assert blocked.status_code == 401

    audit = await client.get("/api/v1/admin/audit", headers=headers)
    assert any(row["action"] == "player.ban" and row["reason"] == "Repeated confirmed abuse." for row in audit.json())
    dashboard = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["closed_accounts"] >= 1


async def test_limited_operator_cannot_ban_or_deactivate_the_last_support_operator(client):
    token = await _support(client)
    headers = _headers(token)
    me = await client.get("/api/v1/admin/me", headers=headers)
    refused = await client.patch(
        f"/api/v1/admin/operators/{me.json()['id']}",
        headers=headers,
        json={"status": "suspended"},
    )
    assert refused.status_code == 403

    created = await client.post(
        "/api/v1/admin/roles",
        headers=headers,
        json={"code": "agent", "name": "Agent", "description": "Cases only"},
    )
    role_id = created.json()["id"]
    await client.put(
        f"/api/v1/admin/roles/{role_id}/permissions",
        headers=headers,
        json={"permissions": ["players.read", "support.read", "support.write"]},
    )
    await client.post(
        "/api/v1/admin/operators",
        headers=headers,
        json={"username": "agent_one", "password": PASSWORD, "roles": ["agent"]},
    )
    agent_login = await client.post("/api/v1/admin/auth/login", json={"username": "agent_one", "password": PASSWORD})
    agent = _headers(agent_login.json()["access_token"])
    player = await client.post("/api/v1/auth/register", json={"username": "agent_target", "password": PASSWORD})
    banned = await client.post(
        f"/api/v1/admin/players/{player.json()['id']}/actions",
        headers=agent,
        json={"action": "ban", "reason": "This agent cannot ban."},
    )
    assert banned.status_code == 403
