"""Liveness stays small. Readiness reports the database."""


async def test_health_stays_ok_and_ready_checks_the_database(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = await client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"
    assert body["version"] == "2.0.0"
