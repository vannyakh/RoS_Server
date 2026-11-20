"""Original-client sessions show as online in the admin console while the gateway reports them."""

import pytest

PASSWORD = "StrongTestPassword123!"
KEY = "test-gateway-key"


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings
    from app.networking.admin_hub import admin_hub

    admin_hub.reset()
    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    yield {"X-Gateway-Key": KEY}
    admin_hub.reset()


async def _operator(client) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator("presence_support", PASSWORD, ["support"], audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": "presence_support", "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def test_gateway_presence_lease_drives_the_admin_online_flag(client, gateway_key, monkeypatch):
    from app.networking import admin_hub as hub_module

    resolved = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": "9300000001"}, headers=gateway_key)
    account_id = resolved.json()["account_id"]
    operator = await _operator(client)
    url = "/api/v1/gateway/accounts/9300000001/presence"

    online = await client.post(url, json={"online": True}, headers=gateway_key)
    assert online.status_code == 200
    assert online.json() == {"online": True}
    row = (await client.get("/api/v1/admin/players?q=9300000001", headers=operator)).json()["items"][0]
    assert row["online"] is True
    assert (await client.get(f"/api/v1/admin/players/{account_id}", headers=operator)).json()["online"] is True

    # A lease that is not renewed runs out on its own.
    clock = hub_module.admin_hub._clock
    monkeypatch.setattr(hub_module.admin_hub, "_clock", lambda: clock() + hub_module.GATEWAY_TTL + 1)
    assert (await client.get(f"/api/v1/admin/players/{account_id}", headers=operator)).json()["online"] is False
    monkeypatch.setattr(hub_module.admin_hub, "_clock", clock)

    await client.post(url, json={"online": True}, headers=gateway_key)
    offline = await client.post(url, json={"online": False}, headers=gateway_key)
    assert offline.json() == {"online": False}

    missing = await client.post("/api/v1/gateway/accounts/9399999999/presence", json={"online": True}, headers=gateway_key)
    assert missing.status_code == 404
    unkeyed = await client.post(url, json={"online": True})
    assert unkeyed.status_code == 401


def test_sweep_announces_expired_gateway_sessions():
    import asyncio

    from app.networking.admin_hub import GATEWAY_TTL, AdminHub

    now = [1000.0]
    hub = AdminHub(clock=lambda: now[0])
    watcher = hub.subscribe("op", {"players.read"})
    hub.gateway_presence("acc-1", True)
    assert watcher.queue.get_nowait()["payload"] == {"account_id": "acc-1", "online": True, "online_players": 1, "source": "gateway"}
    hub.gateway_presence("acc-1", True)
    assert watcher.queue.empty()  # a renewal is not a change

    now[0] += GATEWAY_TTL + 1
    hub.sweep()
    assert watcher.queue.get_nowait()["payload"]["online"] is False
    assert hub.online_players == 0
    assert isinstance(watcher.queue, asyncio.Queue)


async def test_logins_record_device_and_show_as_sessions(client, gateway_key):
    resolved = await client.post(
        "/api/v1/gateway/accounts/resolve",
        json={
            "external_uid": "9300000002",
            "ip_address": "192.168.1.50",
            "device": {"model": "V2266A", "os_name": "Android 9", "client_version": "1227927", "time_zone": "Asia/Phnom_Penh", "language": "en-US"},
        },
        headers=gateway_key,
    )
    account_id = resolved.json()["account_id"]
    await client.post("/api/v1/auth/register", json={"username": "web_session_player", "password": PASSWORD})
    await client.post(
        "/api/v1/auth/login",
        json={"username": "web_session_player", "password": PASSWORD},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/131.0"},
    )
    operator = await _operator(client)

    detail = (await client.get(f"/api/v1/admin/players/{account_id}", headers=operator)).json()
    session = detail["sessions"][0]
    assert session["source"] == "game"
    assert session["network"] == "private"
    assert session["country"] is None
    assert (session["device_model"], session["os_name"], session["time_zone"]) == ("V2266A", "Android 9", "Asia/Phnom_Penh")

    rows = (await client.get("/api/v1/admin/players?limit=50", headers=operator)).json()["items"]
    by_name = {row["username"]: row for row in rows}
    assert by_name["gw_9300000002"]["last_session"]["device_model"] == "V2266A"
    web = by_name["web_session_player"]["last_session"]
    assert web["source"] == "web"
    assert web["user_agent"].startswith("Mozilla/5.0 (Windows NT 10.0)")
