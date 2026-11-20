"""Operators read the original client's battle item catalog; players and anonymous callers cannot."""

PASSWORD = "StrongTestPassword123!"


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_catalog_lists_filters_and_reads_one(client):
    headers = await _operator(client, "catalog_reader", ["support"])

    everything = (await client.get("/api/v1/admin/original/props", headers=headers)).json()
    assert everything["total"] == 411
    assert everything["types"]["Gun"] == 99

    guns = (await client.get("/api/v1/admin/original/props?type=Gun", headers=headers)).json()
    assert guns["total"] == 99 and all(r["type"] == "Gun" for r in guns["items"])

    found = (await client.get("/api/v1/admin/original/props?q=m4a1", headers=headers)).json()
    assert found["items"][0]["id"] == 1001 and all("m4a1" in r["name"].lower() for r in found["items"])

    one = (await client.get("/api/v1/admin/original/props/1101", headers=headers)).json()
    assert (one["name"], one["type"], one["capacity"]) == ("SG Ammo", "Bullet", 15)
    assert (await client.get("/api/v1/admin/original/props/999999", headers=headers)).status_code == 404


async def test_catalog_needs_an_operator(client):
    assert (await client.get("/api/v1/admin/original/props")).status_code == 401


async def test_lobby_catalogs(client):
    headers = await _operator(client, "lobby_reader", ["support"])

    guns = (await client.get("/api/v1/admin/original/lobby?category=firearms&limit=500", headers=headers)).json()
    assert guns["total"] == 734 and guns["categories"]["clothes"] == 3162
    skin = next(r for r in guns["items"] if r["id"] == 120920)
    assert skin["name"] == "Pew Pew Pew" and skin["category"] == "firearms"
    assert (await client.get("/api/v1/admin/original/lobby?category=nope", headers=headers)).status_code == 422

    sets = (await client.get("/api/v1/admin/original/sets", headers=headers)).json()
    assert len(sets) == 14 and len(sets[0]["item_names"]) == len(sets[0]["items"])

    store = (await client.get("/api/v1/admin/original/store?q=brigade", headers=headers)).json()
    assert store["items"][0]["id"] == 10000001

    supply = (await client.get("/api/v1/admin/original/supply?on_sale=true", headers=headers)).json()
    assert supply and all(box["on_sale"] for box in supply)
