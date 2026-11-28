"""Original-client gateway servers: heartbeat, server-select list, operator controls."""

from datetime import timedelta

import pytest

from app.core.config import settings

PASSWORD = "StrongTestPassword123!"
BEAT = {"server_key": "main", "name": "Private-Server", "host": "192.0.2.10", "port": 25000,
        "version": "gw-test", "players_online": 3, "players_in_match": 1}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", "test-gateway-key")
    return {"X-Gateway-Key": "test-gateway-key"}


async def _operator(client, roles, name=None):
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    name = name or f"gs_{roles[0]}"[:32]
    async with SessionLocal() as session:
        await OperatorService(session).create_operator(name, PASSWORD, roles, audit=False)
    token = (await client.post("/api/v1/admin/auth/login", json={"username": name, "password": PASSWORD})).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


async def _age(server_key, seconds):
    """Move a server's last heartbeat into the past."""
    from sqlalchemy import update

    from app.infrastructure.database import SessionLocal
    from app.models.gateway import GatewayServer
    from app.models.types import utc_now

    async with SessionLocal() as session:
        await session.execute(update(GatewayServer).where(GatewayServer.server_key == server_key)
                              .values(last_seen_at=utc_now() - timedelta(seconds=seconds)))
        await session.commit()


async def test_heartbeat_registers_and_lists_the_server(client, key):
    beat = await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)
    assert beat.status_code == 200, beat.text
    assert beat.json() == {"server_key": "main", "name": "Private-Server", "host": "192.0.2.10", "port": 25000,
                           "zone": 1, "group_id": 10001, "status": "smooth", "listed": True}
    listed = (await client.get("/api/v1/gateway/servers", headers=key)).json()["servers"]
    assert [s["server_key"] for s in listed] == ["main"]


async def test_heartbeat_needs_the_gateway_key(client, key):
    assert (await client.post("/api/v1/gateway/servers/heartbeat", json=BEAT)).status_code == 401
    assert (await client.get("/api/v1/gateway/servers", headers={"X-Gateway-Key": "wrong"})).status_code == 401


@pytest.mark.parametrize("bad", [{"name": "Private Server"}, {"server_key": "Main!"}, {"port": 0},
                                 {"players_online": -1}, {"host": "a b"}])
async def test_heartbeat_rejects_values_the_client_list_cannot_carry(client, key, bad):
    assert (await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json={**BEAT, **bad})).status_code == 422


async def test_auto_status_follows_load_and_goes_to_maintenance_when_silent(client, key):
    admin = await _operator(client, ["support"])
    base = "/api/v1/gateway/servers/heartbeat"
    await client.post(base, headers=key, json=BEAT)
    await client.patch("/api/v1/admin/game-servers/main", headers=admin, json={"capacity": 10, "reason": "test cap"})
    assert (await client.post(base, headers=key, json={**BEAT, "players_online": 5})).json()["status"] == "smooth"
    assert (await client.post(base, headers=key, json={**BEAT, "players_online": 6})).json()["status"] == "busy"
    assert (await client.post(base, headers=key, json={**BEAT, "players_online": 10})).json()["status"] == "full"
    await _age("main", 31)
    shown = (await client.get("/api/v1/admin/game-servers", headers=admin)).json()
    assert shown["servers"][0]["live"] is False and shown["servers"][0]["status"] == "maintenance"
    assert shown["servers"][0]["players_online"] == 0 and shown["players_online"] == 0


async def test_operator_controls_win_over_the_gateway_and_are_audited(client, key):
    admin = await _operator(client, ["support"])
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)
    body = {"name": "Asia-1", "status": "maintenance", "zone": 5, "reason": "planned update"}
    changed = await client.patch("/api/v1/admin/game-servers/main", headers=admin, json=body)
    assert changed.status_code == 200, changed.text
    assert (changed.json()["name"], changed.json()["status"], changed.json()["configured_status"]) == \
        ("Asia-1", "maintenance", "maintenance")
    # The gateway's own name is used only on first registration.
    again = (await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)).json()
    assert (again["name"], again["status"], again["zone"]) == ("Asia-1", "maintenance", 5)
    audit = (await client.get("/api/v1/admin/audit", headers=admin)).json()
    row = next(r for r in audit if r["action"] == "server.update")
    assert row["target_id"] == "main" and "planned update" in (row.get("reason") or "")


async def test_unlisted_server_is_left_out_of_the_client_list(client, key):
    admin = await _operator(client, ["support"])
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json={**BEAT, "server_key": "test", "name": "Test"})
    await client.patch("/api/v1/admin/game-servers/test", headers=admin, json={"listed": False, "reason": "hidden"})
    listed = (await client.get("/api/v1/gateway/servers", headers=key)).json()["servers"]
    assert [s["server_key"] for s in listed] == ["main"]
    every = (await client.get("/api/v1/admin/game-servers", headers=admin)).json()["servers"]
    assert sorted(s["server_key"] for s in every) == ["main", "test"]


async def test_admin_totals_and_permissions(client, key):
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key,
                      json={**BEAT, "server_key": "two", "players_online": 4, "players_in_match": 2})
    admin = await _operator(client, ["support"])
    totals = (await client.get("/api/v1/admin/game-servers", headers=admin)).json()
    assert (totals["players_online"], totals["players_in_match"]) == (7, 3)

    observer = await _operator(client, ["observer"])          # no servers.* permission
    assert (await client.get("/api/v1/admin/game-servers", headers=observer)).status_code == 403
    patch = {"status": "busy", "reason": "nope"}
    assert (await client.patch("/api/v1/admin/game-servers/main", headers=observer, json=patch)).status_code == 403
    assert (await client.patch("/api/v1/admin/game-servers/none", headers=admin, json=patch)).status_code == 404
    bad = {"name": "has space", "reason": "bad name"}
    assert (await client.patch("/api/v1/admin/game-servers/main", headers=admin, json=bad)).status_code == 422


async def test_metrics_report_gateway_players(client, key):
    await client.post("/api/v1/gateway/servers/heartbeat", headers=key, json=BEAT)
    text = (await client.get("/metrics")).text
    assert "ros_gateway_players_online 3.0" in text and "ros_gateway_servers_live 1.0" in text
