"""Workshop compound, stored gold and the development grant on the gateway API (RO-096)."""

import pytest

KEY = "test-gateway-key"
UID = "9000000777"
BASE = f"/api/v1/gateway/accounts/{UID}"
THUNDER_1, THUNDER_2 = 142091, 142092


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    monkeypatch.setattr(settings, "gateway_start_gold", 10000)
    monkeypatch.setattr(settings, "app_env", "development")
    return {"X-Gateway-Key": KEY}


async def _player(client, headers, props=((THUNDER_1, 2),), gold=0):
    resolved = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": UID}, headers=headers)
    assert resolved.status_code == 200
    if props or gold:
        granted = await client.post(
            f"{BASE}/dev/grant",
            json={
                "props": [{"prop_id": p, "number": n} for p, n in props],
                "currencies": [{"currency_id": 1, "amount": gold}] if gold else [],
            },
            headers=headers,
        )
        assert granted.status_code == 200, granted.text


def _thunder(request_id="req-1", gold=1000):
    return {
        "request_id": request_id,
        "require": [{"prop_id": THUNDER_1, "number": 2}],
        "consume": [{"prop_id": THUNDER_1, "number": 1}],
        "consume_currency": [{"currency_id": 1, "amount": gold}],
        "add": [{"prop_id": THUNDER_2, "number": 1}],
        "reason": "workshop:thunder:2",
    }


async def _state(client, headers):
    state = await client.get(f"{BASE}/state", headers=headers)
    assert state.status_code == 200
    body = state.json()
    return {i["prop_id"]: i["number"] for i in body["items"]}, body["currencies"]["1"]


async def test_state_includes_the_starting_gold(client, gateway_key):
    await _player(client, gateway_key, props=())
    state = await client.get(f"{BASE}/state", headers=gateway_key)
    assert state.status_code == 200
    assert state.json()["currencies"] == {"1": 10000}
    assert state.json()["items"] == []


async def test_compound_consumes_props_and_gold_and_adds_the_target(client, gateway_key):
    await _player(client, gateway_key)
    done = await client.post(f"{BASE}/workshop/compound", json=_thunder(), headers=gateway_key)
    assert done.status_code == 200, done.text
    assert done.json() == {
        "items": [{"prop_id": THUNDER_1, "number": 1}, {"prop_id": THUNDER_2, "number": 1}],
        "currencies": {"1": 9000},
        "replayed": False,
    }
    items, gold = await _state(client, gateway_key)
    assert items == {THUNDER_1: 1, THUNDER_2: 1}
    assert gold == 9000


async def test_consumed_to_zero_is_not_listed_in_state(client, gateway_key):
    await _player(client, gateway_key, props=((THUNDER_1, 1),))
    body = {**_thunder(gold=0), "require": [{"prop_id": THUNDER_1, "number": 1}]}
    done = await client.post(f"{BASE}/workshop/compound", json=body, headers=gateway_key)
    assert done.status_code == 200, done.text
    assert {"prop_id": THUNDER_1, "number": 0} in done.json()["items"]
    items, gold = await _state(client, gateway_key)
    assert items == {THUNDER_2: 1}
    assert gold == 10000


async def test_missing_items_refuse_with_409_and_change_nothing(client, gateway_key):
    await _player(client, gateway_key, props=((THUNDER_1, 1),))
    refused = await client.post(f"{BASE}/workshop/compound", json=_thunder(), headers=gateway_key)
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["code"] == "insufficient"
    assert {"kind": "require", "prop_id": THUNDER_1, "need": 2, "have": 1} in detail["missing"]
    assert await _state(client, gateway_key) == ({THUNDER_1: 1}, 10000)


async def test_missing_gold_refuses_with_409_and_changes_nothing(client, gateway_key):
    await _player(client, gateway_key)
    refused = await client.post(f"{BASE}/workshop/compound", json=_thunder(gold=10001), headers=gateway_key)
    assert refused.status_code == 409
    assert refused.json()["detail"]["missing"] == [
        {"kind": "currency", "currency_id": 1, "need": 10001, "have": 10000}
    ]
    assert await _state(client, gateway_key) == ({THUNDER_1: 2}, 10000)
    # The refused request_id was not used up: it applies once the player can pay.
    retried = await client.post(f"{BASE}/workshop/compound", json=_thunder(gold=1000), headers=gateway_key)
    assert retried.status_code == 200 and retried.json()["replayed"] is False


async def test_the_same_request_id_applies_once(client, gateway_key):
    await _player(client, gateway_key, props=((THUNDER_1, 3),))
    first = await client.post(f"{BASE}/workshop/compound", json=_thunder("same-id"), headers=gateway_key)
    second = await client.post(f"{BASE}/workshop/compound", json=_thunder("same-id"), headers=gateway_key)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["replayed"] is False
    assert second.json() == {**first.json(), "replayed": True}
    assert await _state(client, gateway_key) == ({THUNDER_1: 2, THUNDER_2: 1}, 9000)

    third = await client.post(f"{BASE}/workshop/compound", json=_thunder("other-id"), headers=gateway_key)
    assert third.status_code == 200 and third.json()["replayed"] is False
    assert await _state(client, gateway_key) == ({THUNDER_1: 1, THUNDER_2: 2}, 8000)


async def test_only_gold_currency_is_accepted(client, gateway_key):
    await _player(client, gateway_key)
    body = _thunder()
    body["consume_currency"] = [{"currency_id": 2, "amount": 10}]
    refused = await client.post(f"{BASE}/workshop/compound", json=body, headers=gateway_key)
    assert refused.status_code == 422
    bad_id = await client.post(f"{BASE}/workshop/compound", json={**_thunder(), "request_id": "bad id!"}, headers=gateway_key)
    assert bad_id.status_code == 422
    assert await _state(client, gateway_key) == ({THUNDER_1: 2}, 10000)


async def test_dev_grant_is_404_outside_development(client, gateway_key, monkeypatch):
    from app.core.config import settings

    await _player(client, gateway_key, props=())
    monkeypatch.setattr(settings, "app_env", "production")
    hidden = await client.post(
        f"{BASE}/dev/grant", json={"props": [{"prop_id": THUNDER_1, "number": 1}]}, headers=gateway_key
    )
    assert hidden.status_code == 404
    monkeypatch.setattr(settings, "app_env", "development")
    assert await _state(client, gateway_key) == ({}, 10000)


async def test_dev_grant_adds_props_and_gold_in_development(client, gateway_key):
    await _player(client, gateway_key, props=())
    granted = await client.post(
        f"{BASE}/dev/grant",
        json={
            "props": [{"prop_id": THUNDER_1, "number": 2}, {"prop_id": THUNDER_1, "number": 1}],
            "currencies": [{"currency_id": 1, "amount": 5000}],
        },
        headers=gateway_key,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["items"] == [{"prop_id": THUNDER_1, "number": 3}]
    assert granted.json()["currencies"] == {"1": 15000}


async def test_workshop_routes_need_the_gateway_key(client, gateway_key):
    await _player(client, gateway_key)
    no_key = await client.post(f"{BASE}/workshop/compound", json=_thunder())
    assert no_key.status_code == 401
    wrong = await client.post(f"{BASE}/workshop/compound", json=_thunder(), headers={"X-Gateway-Key": "nope"})
    assert wrong.status_code == 401
    grant = await client.post(f"{BASE}/dev/grant", json={"props": []})
    assert grant.status_code == 401
    assert await _state(client, gateway_key) == ({THUNDER_1: 2}, 10000)


async def test_unknown_uid_is_404(client, gateway_key):
    missing = await client.post(
        "/api/v1/gateway/accounts/123456/workshop/compound", json=_thunder(), headers=gateway_key
    )
    assert missing.status_code == 404
