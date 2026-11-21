"""Weapon balance: operators with weapons.manage tune weapons; every change is audited."""

PASSWORD = "StrongTestPassword123!"

RIFLE = {
    "name": "AR-Alpha",
    "weapon_class": "assault",
    "damage": 38,
    "fire_rate": 650,
    "magazine": 30,
    "reload_seconds": 2.4,
    "effective_range": 60,
    "max_range": 180,
    "falloff_percent": 40,
    "spread": 2.2,
    "recoil": 46,
    "head_multiplier": 2,
    "torso_multiplier": 1,
    "limb_multiplier": 0.8,
    "vehicle_damage": 60,
}


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_create_update_list_and_delete_with_audit(client):
    headers = await _operator(client, "weapon_admin", ["support"])

    created = await client.put("/api/v1/admin/weapons/ar_alpha", headers=headers, json=RIFLE)
    assert created.status_code == 200, created.text
    assert (created.json()["code"], created.json()["revision"], created.json()["damage"]) == ("ar_alpha", 1, 38)

    changed = await client.put(
        "/api/v1/admin/weapons/ar_alpha",
        headers=headers,
        json={**RIFLE, "damage": 41, "head_multiplier": 2.2, "expected_revision": 1, "reason": "Patch 7 balance"},
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["revision"], changed.json()["damage"]) == (2, 41)

    same = await client.put("/api/v1/admin/weapons/ar_alpha", headers=headers, json={**RIFLE, "damage": 41, "head_multiplier": 2.2})
    assert same.json()["revision"] == 2  # nothing changed, no new revision

    listed = await client.get("/api/v1/admin/weapons", headers=headers)
    assert [row["code"] for row in listed.json()] == ["ar_alpha"]

    audit = await client.get("/api/v1/admin/audit", headers=headers)
    rows = {row["action"]: row for row in audit.json()}
    assert {"weapon.create", "weapon.update"} <= set(rows)
    assert "damage=41" in rows["weapon.update"]["detail"]

    assert (await client.delete("/api/v1/admin/weapons/ar_alpha?reason=retired", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/admin/weapons", headers=headers)).json() == []
    assert (await client.delete("/api/v1/admin/weapons/ar_alpha", headers=headers)).status_code == 404


async def test_stale_revision_is_refused(client):
    headers = await _operator(client, "weapon_conflict", ["support"])
    await client.put("/api/v1/admin/weapons/ar_alpha", headers=headers, json=RIFLE)
    await client.put("/api/v1/admin/weapons/ar_alpha", headers=headers, json={**RIFLE, "damage": 40})
    stale = await client.put("/api/v1/admin/weapons/ar_alpha", headers=headers, json={**RIFLE, "damage": 50, "expected_revision": 1})
    assert stale.status_code == 409
    current = (await client.get("/api/v1/admin/weapons", headers=headers)).json()[0]
    assert current["damage"] == 40


async def test_rejects_bad_values_and_missing_permission(client):
    headers = await _operator(client, "weapon_validate", ["support"])
    assert (await client.put("/api/v1/admin/weapons/Bad-Code", headers=headers, json=RIFLE)).status_code == 422
    assert (await client.put("/api/v1/admin/weapons/x", headers=headers, json={**RIFLE, "weapon_class": "laser"})).status_code == 422
    assert (await client.put("/api/v1/admin/weapons/x", headers=headers, json={**RIFLE, "damage": 0})).status_code == 422
    assert (await client.put("/api/v1/admin/weapons/x", headers=headers, json={**RIFLE, "max_range": 10})).status_code == 422
    assert (await client.put("/api/v1/admin/weapons/x", headers=headers, json={**RIFLE, "falloff_percent": 140})).status_code == 422

    limited = await _operator(client, "weapon_viewer", ["game_admin"])
    assert (await client.get("/api/v1/admin/weapons", headers=limited)).status_code == 403
    assert (await client.put("/api/v1/admin/weapons/x", headers=limited, json=RIFLE)).status_code == 403
    assert (await client.get("/api/v1/admin/weapons")).status_code == 401
