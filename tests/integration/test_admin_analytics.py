"""Dashboard analytics count stored rows per UTC day and never invent data."""

PASSWORD = "StrongTestPassword123!"


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_analytics_counts_signups_logins_and_devices(client):
    await client.post("/api/v1/auth/register", json={"username": "chart_player", "password": PASSWORD})
    await client.post("/api/v1/auth/login", json={"username": "chart_player", "password": PASSWORD})
    await client.post("/api/v1/auth/login", json={"username": "chart_player", "password": "wrong-password-1"})
    headers = await _operator(client, "chart_admin", ["support"])

    response = await client.get("/api/v1/admin/analytics?days=7", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["days"] == 7
    assert len(body["daily"]) == 7
    today = body["daily"][-1]
    assert today["registrations_web"] >= 1
    assert today["logins"] >= 1
    assert today["failed_logins"] >= 1
    assert today["active_players"] >= 1
    assert body["sources"].get("web", 0) >= 1
    assert any(row["name"] == "Web browser" for row in body["devices"])
    assert body["statuses"]["active"] >= 1
    assert sum(row["count"] for row in body["levels"]) >= 1
    assert all(len(cell) == 3 for cell in body["hourly_logins"])
    assert body["country_activity"] == [] or {"code", "logins", "players", "online"} <= set(body["country_activity"][0])
    assert body["online_now"] >= 0

    assert (await client.get("/api/v1/admin/analytics?days=0", headers=headers)).status_code == 422

    from datetime import date, timedelta

    today = date.today()
    ranged = await client.get(f"/api/v1/admin/analytics?start={today - timedelta(days=2)}&end={today}", headers=headers)
    assert ranged.status_code == 200
    assert (ranged.json()["days"], ranged.json()["end"]) == (3, today.isoformat())
    assert ranged.json()["daily"][-1]["logins"] >= 1
    past = await client.get(f"/api/v1/admin/analytics?start={today - timedelta(days=40)}&end={today - timedelta(days=30)}", headers=headers)
    assert sum(row["logins"] for row in past.json()["daily"]) == 0
    backwards = await client.get(f"/api/v1/admin/analytics?start={today}&end={today - timedelta(days=1)}", headers=headers)
    assert backwards.status_code == 422
    too_long = await client.get(f"/api/v1/admin/analytics?start={today - timedelta(days=400)}&end={today}", headers=headers)
    assert too_long.status_code == 422
    half = await client.get(f"/api/v1/admin/analytics?start={today}", headers=headers)
    assert half.status_code == 422


async def test_analytics_needs_dashboard_read(client):
    created = await client.post("/api/v1/auth/register", json={"username": "not_operator", "password": PASSWORD})
    assert created.status_code == 201
    assert (await client.get("/api/v1/admin/analytics")).status_code == 401


async def test_country_activity_counts_players_and_online(client, monkeypatch):
    from app.networking.admin_hub import admin_hub

    monkeypatch.setattr("app.services.account_service.country_for", lambda ip: "KH")
    admin_hub.reset()
    created = await client.post("/api/v1/auth/register", json={"username": "map_player", "password": PASSWORD})
    account_id = created.json()["id"]
    for _ in range(2):
        await client.post("/api/v1/auth/login", json={"username": "map_player", "password": PASSWORD})
    admin_hub.presence(account_id, True)
    headers = await _operator(client, "map_admin", ["support"])

    body = (await client.get("/api/v1/admin/analytics?days=7", headers=headers)).json()
    kh = next(row for row in body["country_activity"] if row["code"] == "KH")
    assert (kh["logins"], kh["players"], kh["online"]) == (2, 1, 1)
    assert body["online_now"] == 1
    admin_hub.reset()
