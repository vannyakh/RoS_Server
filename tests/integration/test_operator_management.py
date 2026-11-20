"""Operator management: list details, password reset, forced sign-out, suspension ends sessions."""

PASSWORD = "StrongTestPassword123!"
NEW_PASSWORD = "AnotherStrongPassword456!"


async def _operator(client, username: str, roles: list[str]) -> tuple[str, dict[str, str]]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        created = await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return created.id, {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_list_shows_permissions_and_live_sessions(client):
    lead_id, lead = await _operator(client, "lead_ops", ["support"])
    listed = await client.get("/api/v1/admin/operators", headers=lead)
    row = next(item for item in listed.json() if item["id"] == lead_id)
    assert row["active_sessions"] == 1
    assert "operators.manage" in row["permissions"]
    assert row["created_at"]


async def test_reset_password_and_sign_out_end_the_other_operators_sessions(client):
    _lead_id, lead = await _operator(client, "reset_lead", ["support"])
    helper_id, helper = await _operator(client, "reset_helper", ["game_admin"])

    reset = await client.post(
        f"/api/v1/admin/operators/{helper_id}/password", headers=lead, json={"password": NEW_PASSWORD, "reason": "Forgot password."}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["sessions_ended"] == 1
    assert (await client.get("/api/v1/admin/me", headers=helper)).status_code == 401
    old = await client.post("/api/v1/admin/auth/login", json={"username": "reset_helper", "password": PASSWORD})
    assert old.status_code == 401
    fresh = await client.post("/api/v1/admin/auth/login", json={"username": "reset_helper", "password": NEW_PASSWORD})
    assert fresh.status_code == 200
    helper = {"Authorization": f"Bearer {fresh.json()['access_token']}"}

    ended = await client.post(f"/api/v1/admin/operators/{helper_id}/sign-out", headers=lead, json={"reason": "Lost laptop."})
    assert ended.json()["sessions_ended"] == 1
    assert (await client.get("/api/v1/admin/me", headers=helper)).status_code == 401

    audit = (await client.get("/api/v1/admin/audit", headers=lead)).json()
    assert {"operator.password", "operator.sign_out"} <= {row["action"] for row in audit}


async def test_cannot_reset_own_password_and_needs_manage(client):
    lead_id, lead = await _operator(client, "self_lead", ["support"])
    own = await client.post(f"/api/v1/admin/operators/{lead_id}/password", headers=lead, json={"password": NEW_PASSWORD, "reason": "Try."})
    assert own.status_code == 403
    short = await client.post(f"/api/v1/admin/operators/{lead_id}/sign-out", headers=lead, json={})
    assert short.status_code == 200

    _viewer_id, viewer = await _operator(client, "plain_viewer", ["game_admin"])
    denied = await client.post(f"/api/v1/admin/operators/{lead_id}/sign-out", headers=viewer, json={})
    assert denied.status_code == 403


async def test_suspending_ends_sessions(client):
    _lead_id, lead = await _operator(client, "suspend_lead", ["support"])
    helper_id, helper = await _operator(client, "suspend_helper", ["game_admin"])
    suspended = await client.patch(f"/api/v1/admin/operators/{helper_id}", headers=lead, json={"status": "suspended"})
    assert suspended.status_code == 200
    listed = await client.get("/api/v1/admin/operators", headers=lead)
    row = next(item for item in listed.json() if item["id"] == helper_id)
    assert (row["status"], row["active_sessions"]) == ("suspended", 0)
    assert (await client.get("/api/v1/admin/me", headers=helper)).status_code == 401
