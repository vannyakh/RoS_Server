"""Roles: holder counts, rename, delete only when unused, system role protected."""

PASSWORD = "StrongTestPassword123!"


async def _lead(client) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator("role_lead", PASSWORD, ["support"], audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": "role_lead", "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_role_lifecycle(client):
    headers = await _lead(client)
    created = await client.post("/api/v1/admin/roles", headers=headers, json={"code": "night_shift", "name": "Night shift"})
    assert created.status_code == 201
    role_id = created.json()["id"]

    renamed = await client.patch(f"/api/v1/admin/roles/{role_id}", headers=headers, json={"name": "Night moderators", "description": "After-hours cover."})
    assert renamed.json()["name"] == "Night moderators"

    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    support = next(role for role in roles if role["code"] == "support")
    night = next(role for role in roles if role["id"] == role_id)
    assert support["operator_count"] >= 1
    assert (night["operator_count"], night["description"]) == (0, "After-hours cover.")

    assert (await client.patch(f"/api/v1/admin/roles/{support['id']}", headers=headers, json={"name": "X"})).status_code == 403
    assert (await client.delete(f"/api/v1/admin/roles/{support['id']}", headers=headers)).status_code == 403

    created_op = await client.post("/api/v1/admin/operators", headers=headers, json={"username": "night_one", "password": PASSWORD, "roles": ["night_shift"]})
    assert created_op.status_code == 201
    held = await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
    assert held.status_code == 409

    await client.put(f"/api/v1/admin/operators/{created_op.json()['id']}/roles", headers=headers, json={"roles": []})
    assert (await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)).status_code == 204
    assert all(role["id"] != role_id for role in (await client.get("/api/v1/admin/roles", headers=headers)).json())
    audit = {row["action"] for row in (await client.get("/api/v1/admin/audit", headers=headers)).json()}
    assert {"role.update", "role.delete"} <= audit
