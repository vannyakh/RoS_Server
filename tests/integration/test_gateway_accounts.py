"""Original-client gateway accounts appear in the admin console and obey its moderation."""

import pytest

PASSWORD = "StrongTestPassword123!"
KEY = "test-gateway-key"


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    return {"X-Gateway-Key": KEY}


async def _operator(client) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator("gw_support", PASSWORD, ["support"], audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": "gw_support", "password": PASSWORD})
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_gateway_routes_are_off_without_a_configured_key(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", "")
    response = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000001"}, headers={"X-Gateway-Key": "x"}
    )
    assert response.status_code == 404


async def test_gateway_routes_reject_a_wrong_key(client, gateway_key):
    missing = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000001"})
    assert missing.status_code == 401
    wrong = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000001"}, headers={"X-Gateway-Key": "nope"}
    )
    assert wrong.status_code == 401


async def test_first_login_creates_an_account_the_admin_console_can_find(client, gateway_key):
    first = await client.post(
        "/api/v1/gateway/accounts/resolve",
        json={"external_uid": "9000000001", "ip_address": "192.168.1.50"},
        headers=gateway_key,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["username"] == "gw_9000000001"
    assert body["is_new"] is True
    assert body["can_play"] is True
    assert body["char_type"] is None

    again = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000001"}, headers=gateway_key
    )
    assert again.json()["account_id"] == body["account_id"]

    operator = await _operator(client)
    found = await client.get("/api/v1/admin/players?q=gw_9000000001", headers=operator)
    assert found.status_code == 200
    assert [row["id"] for row in found.json()["items"]] == [body["account_id"]]

    login = await client.post("/api/v1/auth/login", json={"username": "gw_9000000001", "password": ""})
    assert login.status_code in (401, 422)


async def test_character_creation_sets_the_nickname_and_rejects_a_taken_one(client, gateway_key):
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "111"}, headers=gateway_key)
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "222"}, headers=gateway_key)

    created = await client.put(
        "/api/v1/gateway/accounts/111/character", json={"nickname": "Raven", "char_type": 20001}, headers=gateway_key
    )
    assert created.status_code == 200
    assert created.json()["nickname"] == "Raven"
    assert created.json()["char_type"] == 20001
    assert created.json()["is_new"] is False

    taken = await client.put(
        "/api/v1/gateway/accounts/222/character", json={"nickname": "Raven", "char_type": 20001}, headers=gateway_key
    )
    assert taken.status_code == 409

    unknown = await client.put(
        "/api/v1/gateway/accounts/333/character", json={"nickname": "Nobody", "char_type": 1}, headers=gateway_key
    )
    assert unknown.status_code == 404


async def test_portrait_is_saved_and_returned_on_the_next_login(client, gateway_key):
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "444"}, headers=gateway_key)

    saved = await client.put(
        "/api/v1/gateway/accounts/444/portrait", json={"portrait": "5f2a9c01-ab"}, headers=gateway_key
    )
    assert saved.status_code == 200
    assert saved.json()["portrait"] == "5f2a9c01-ab"

    again = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "444"}, headers=gateway_key)
    assert again.json()["portrait"] == "5f2a9c01-ab"

    cleared = await client.put("/api/v1/gateway/accounts/444/portrait", json={"portrait": ""}, headers=gateway_key)
    assert cleared.json()["portrait"] == ""

    bad = await client.put(
        "/api/v1/gateway/accounts/444/portrait", json={"portrait": "../etc/passwd"}, headers=gateway_key
    )
    assert bad.status_code == 422
    unknown = await client.put("/api/v1/gateway/accounts/555/portrait", json={"portrait": "x"}, headers=gateway_key)
    assert unknown.status_code == 404
    keyless = await client.put("/api/v1/gateway/accounts/444/portrait", json={"portrait": "x"})
    assert keyless.status_code == 401


async def test_an_admin_ban_stops_the_next_gateway_login(client, gateway_key):
    created = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000002"}, headers=gateway_key
    )
    account_id = created.json()["account_id"]
    operator = await _operator(client)

    banned = await client.post(
        f"/api/v1/admin/players/{account_id}/actions",
        headers=operator,
        json={"action": "ban", "reason": "Cheating on the test server."},
    )
    assert banned.status_code == 200

    after = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9000000002"}, headers=gateway_key
    )
    assert after.status_code == 200
    assert after.json()["status"] == "closed"
    assert after.json()["can_play"] is False


async def test_admin_sees_game_client_data_and_edits_the_profile(client, gateway_key):
    created = await client.post(
        "/api/v1/gateway/accounts/resolve",
        json={"external_uid": "9020785644", "ip_address": "192.168.1.60"},
        headers=gateway_key,
    )
    account_id = created.json()["account_id"]
    await client.put(
        "/api/v1/gateway/accounts/9020785644/character", json={"nickname": "Raven", "char_type": 30001}, headers=gateway_key
    )
    operator = await _operator(client)

    listed = await client.get("/api/v1/admin/players?q=raven", headers=operator)
    row = listed.json()["items"][0]
    assert (row["id"], row["nickname"], row["client"], row["char_type"]) == (account_id, "Raven", "game", 30001)
    assert (row["game_id"], row["rank_score"], row["online"]) == ("9020785644", 0, False)
    assert row["game_last_login_at"] is not None

    detail = await client.get(f"/api/v1/admin/players/{account_id}", headers=operator)
    assert detail.json()["gateway"] == {
        "external_uid": "9020785644",
        "char_type": 30001,
        "last_login_at": detail.json()["gateway"]["last_login_at"],
        "last_ip": "192.168.1.60",
        "portrait": "",
        "items": 0,
        "props": [],
        "outfit": {"body": [], "wear": []},
        "rank_score": 0,
        "credit_score": 100,
        "credit_status_last_week": 0,
        "credit_weeks": 0,
        "space_likes": 0,
        "national_flag": "",
        "head_frame": 0,
        "rank_tier": "bronze",
        "rank_logo_url": "",
        "lobby_theme": 0,
        "lobby_background_url": "",
        "current_season": detail.json()["gateway"]["current_season"],
        "records": [],
    }

    no_reason = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile", headers=operator, json={"nickname": "Falcon", "reason": ""}
    )
    assert no_reason.status_code == 422

    edited = await client.patch(
        f"/api/v1/admin/players/{account_id}/profile",
        headers=operator,
        json={"nickname": "Falcon", "char_type": 20001, "reason": "Player asked for a rename."},
    )
    assert edited.status_code == 200
    assert edited.json()["nickname"] == "Falcon"
    assert edited.json()["gateway"]["char_type"] == 20001
    assert edited.json()["audit"][0]["action"] == "player.profile"

    next_login = await client.post(
        "/api/v1/gateway/accounts/resolve", json={"external_uid": "9020785644"}, headers=gateway_key
    )
    assert (next_login.json()["nickname"], next_login.json()["char_type"]) == ("Falcon", 20001)


async def test_character_type_is_only_for_game_client_accounts(client):
    registered = await client.post("/api/v1/auth/register", json={"username": "web_player", "password": PASSWORD})
    operator = await _operator(client)
    response = await client.patch(
        f"/api/v1/admin/players/{registered.json()['id']}/profile",
        headers=operator,
        json={"char_type": 20001, "reason": "Should not apply."},
    )
    assert response.status_code == 422
    listed = await client.get("/api/v1/admin/players?q=web_player", headers=operator)
    assert listed.json()["items"][0]["client"] == "web"


async def test_admin_player_list_filters_by_client_and_created_date(client, gateway_key):
    from datetime import date, timedelta

    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "9111111111"}, headers=gateway_key)
    await client.post("/api/v1/auth/register", json={"username": "web_only", "password": PASSWORD})
    operator = await _operator(client)

    game = await client.get("/api/v1/admin/players?client=game", headers=operator)
    assert [row["username"] for row in game.json()["items"]] == ["gw_9111111111"]
    assert game.json()["total"] == 1
    web = await client.get("/api/v1/admin/players?client=web", headers=operator)
    assert [row["username"] for row in web.json()["items"]] == ["web_only"]

    today = date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()
    future = await client.get(f"/api/v1/admin/players?created_from={tomorrow}", headers=operator)
    assert future.json()["total"] == 0
    window = await client.get(
        f"/api/v1/admin/players?created_from={(today - timedelta(days=1)).isoformat()}&created_to={tomorrow}&limit=1",
        headers=operator,
    )
    assert window.json()["total"] == 2
    assert len(window.json()["items"]) == 1
    bad = await client.get("/api/v1/admin/players?client=phone", headers=operator)
    assert bad.status_code == 422


async def test_items_diamonds_and_outfit_survive_the_next_login(client, gateway_key):
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "666"}, headers=gateway_key)

    start = await client.get("/api/v1/gateway/accounts/666/state", headers=gateway_key)
    assert start.status_code == 200
    assert start.json() == {"yuanbao": 100000, "items": [], "outfit": {"body": [], "wear": [], "theme": 0}, "head_frame": 0}

    bought = await client.post(
        "/api/v1/gateway/accounts/666/purchase",
        json={"price": 100, "props": [2007], "reason": "buy:2007"},
        headers=gateway_key,
    )
    assert bought.json() == {"yuanbao": 99900, "added": [2007]}
    drawn = await client.post(
        "/api/v1/gateway/accounts/666/purchase",
        json={"price": 0, "props": [2007, 111897], "reason": "draw:105"},
        headers=gateway_key,
    )
    assert drawn.json() == {"yuanbao": 99900, "added": [111897]}

    worn = await client.put(
        "/api/v1/gateway/accounts/666/outfit", json={"body": [], "wear": [2007]}, headers=gateway_key
    )
    assert worn.status_code == 200

    again = (await client.get("/api/v1/gateway/accounts/666/state", headers=gateway_key)).json()
    assert again["yuanbao"] == 99900
    assert again["items"] == [{"prop_id": 2007, "number": 2}, {"prop_id": 111897, "number": 1}]
    assert again["outfit"] == {"body": [], "wear": [2007], "theme": 0}


async def test_a_purchase_above_the_balance_changes_nothing(client, gateway_key):
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "777"}, headers=gateway_key)
    refused = await client.post(
        "/api/v1/gateway/accounts/777/purchase",
        json={"price": 100001, "props": [2007], "reason": "buy:2007"},
        headers=gateway_key,
    )
    assert refused.status_code == 409
    state = (await client.get("/api/v1/gateway/accounts/777/state", headers=gateway_key)).json()
    assert state["yuanbao"] == 100000
    assert state["items"] == []

    unknown = await client.get("/api/v1/gateway/accounts/888/state", headers=gateway_key)
    assert unknown.status_code == 404
    keyless = await client.get("/api/v1/gateway/accounts/777/state")
    assert keyless.status_code == 401


async def test_head_frame_is_saved_and_sent_with_state_and_profile(client, gateway_key):
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "445"}, headers=gateway_key)
    assert (await client.get("/api/v1/gateway/accounts/445/state", headers=gateway_key)).json()["head_frame"] == 0

    saved = await client.put("/api/v1/gateway/accounts/445/head-frame", json={"head_frame": 2990236}, headers=gateway_key)
    assert saved.status_code == 200
    assert saved.json()["head_frame"] == 2990236

    again = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "445"}, headers=gateway_key)
    assert again.json()["head_frame"] == 2990236
    state = await client.get("/api/v1/gateway/accounts/445/state", headers=gateway_key)
    assert state.json()["head_frame"] == 2990236
    profile = await client.get("/api/v1/gateway/accounts/445/profile", headers=gateway_key)
    assert profile.json()["head_frame"] == 2990236

    cleared = await client.put("/api/v1/gateway/accounts/445/head-frame", json={"head_frame": 0}, headers=gateway_key)
    assert cleared.json()["head_frame"] == 0
    assert (await client.put("/api/v1/gateway/accounts/445/head-frame", json={"head_frame": -1}, headers=gateway_key)).status_code == 422
    assert (await client.put("/api/v1/gateway/accounts/999/head-frame", json={"head_frame": 5}, headers=gateway_key)).status_code == 404


async def test_profile_and_admin_detail_carry_rank_logo_and_lobby_background(client, gateway_key):
    from app.services.rank_tiers import rank_tier

    assert [rank_tier(s) for s in (0, 999, 1000, 4500, 99999)] == ["bronze", "bronze", "silver", "diamond", "king"]
    await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "446"}, headers=gateway_key)
    profile = (await client.get("/api/v1/gateway/accounts/446/profile", headers=gateway_key)).json()
    assert profile["rank_tier"] == "bronze"
    assert profile["rank_logo_url"] == "" and profile["lobby_background_url"] == "" and profile["lobby_theme"] == 0
