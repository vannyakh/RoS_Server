"""Login, lobby, coin, diamond, and skin routes."""

PASSWORD = "StrongTestPassword123!"


async def _token(client, username: str) -> str:
    created = await client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_login_lobby_wallet_and_skins(client):
    token = await _token(client, "lobby_wallet")
    headers = _headers(token)

    profile = await client.get("/api/v1/players/me", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["coin"] == 500
    assert body["diamond"] == 20
    assert body["equipped_skin"] == "recruit"
    assert body["owned_skins"] == ["recruit"]

    opened = await client.post("/api/v1/lobby", json={"code": "WALLET-ROOM", "max_players": 4}, headers=headers)
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]
    joined = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=headers)
    assert joined.status_code == 201
    ready = await client.post(f"/api/v1/lobby/{lobby_id}/ready", json={"ready": True}, headers=headers)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True

    catalog = await client.get("/api/v1/cosmetics/skins", headers=headers)
    assert catalog.status_code == 200
    offers = {row["code"]: row for row in catalog.json()}
    assert offers["recruit"]["owned"] is True
    assert offers["field_jacket"]["price"] == 200
    assert offers["field_jacket"]["currency"] == "coin"
    assert offers["night_ops"]["currency"] == "diamond"

    minted = await client.post(
        "/api/v1/inventory/currency",
        json={"currency_code": "coin", "amount": 1, "reason": "mint"},
        headers=headers,
    )
    assert minted.status_code == 409

    jacket = await client.post("/api/v1/cosmetics/skins/field_jacket/purchase", headers=headers)
    assert jacket.status_code == 200
    assert jacket.json()["coin"] == 300
    assert "field_jacket" in jacket.json()["owned_skins"]

    again = await client.post("/api/v1/cosmetics/skins/field_jacket/purchase", headers=headers)
    assert again.status_code == 409

    missing = await client.post("/api/v1/cosmetics/skins/unknown_skin/purchase", headers=headers)
    assert missing.status_code == 404

    locked = await client.post("/api/v1/cosmetics/skins/night_ops/equip", headers=headers)
    assert locked.status_code == 409

    night = await client.post("/api/v1/cosmetics/skins/night_ops/purchase", headers=headers)
    assert night.status_code == 200
    assert night.json()["diamond"] == 5

    equipped = await client.post("/api/v1/cosmetics/skins/night_ops/equip", headers=headers)
    assert equipped.status_code == 200
    assert equipped.json()["equipped_skin"] == "night_ops"
    assert equipped.json()["coin"] == 300

    still_in_lobby = await client.get(f"/api/v1/lobby/{lobby_id}", headers=headers)
    assert still_in_lobby.status_code == 200
    assert still_in_lobby.json()["code"] == "WALLET-ROOM"
