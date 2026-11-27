"""Idempotent gateway purchase with request_id (RO-122)."""

import asyncio

import pytest
from sqlalchemy import func, select

KEY = "test-gateway-key"
UID = "9000000123"
BASE = f"/api/v1/gateway/accounts/{UID}"
START = 100000


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    monkeypatch.setattr(settings, "gateway_starting_yuanbao", START)
    return {"X-Gateway-Key": KEY}


async def _resolve(client, headers):
    resolved = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": UID}, headers=headers)
    assert resolved.status_code == 200, resolved.text


async def _buy(client, headers, price=100, props=(2007,), reason="buy:2007", request_id="req-00001"):
    body = {"price": price, "props": list(props), "reason": reason}
    if request_id is not None:
        body["request_id"] = request_id
    return await client.post(f"{BASE}/purchase", json=body, headers=headers)


async def _state(client, headers):
    state = await client.get(f"{BASE}/state", headers=headers)
    assert state.status_code == 200
    body = state.json()
    return body["yuanbao"], {i["prop_id"]: i["number"] for i in body["items"]}


async def _ledger_rows(note_prefix="purchase:"):
    from app.infrastructure.database import SessionLocal
    from app.models.inventory import CurrencyTransaction

    async with SessionLocal() as session:
        return await session.scalar(
            select(func.count()).select_from(CurrencyTransaction).where(CurrencyTransaction.note.like(f"{note_prefix}%"))
        )


async def _diamond_rows():
    from app.infrastructure.database import SessionLocal
    from app.models.inventory import CurrencyTransaction

    async with SessionLocal() as session:
        return await session.scalar(
            select(func.count()).select_from(CurrencyTransaction).where(CurrencyTransaction.currency_code == "yuanbao")
        )


async def test_repeat_request_id_charges_once_and_replays(client, gateway_key):
    await _resolve(client, gateway_key)
    first = await _buy(client, gateway_key)
    assert first.status_code == 200, first.text
    assert first.json() == {"yuanbao": START - 100, "added": [2007], "recent_got": [2007], "replayed": False}
    rows = await _diamond_rows()

    again = await _buy(client, gateway_key)
    assert again.status_code == 200, again.text
    assert again.json() == {"yuanbao": START - 100, "added": [2007], "recent_got": [2007], "replayed": True}
    assert await _state(client, gateway_key) == (START - 100, {2007: 1})
    assert await _diamond_rows() == rows
    assert await _ledger_rows() == 1


async def test_different_request_id_charges_again(client, gateway_key):
    await _resolve(client, gateway_key)
    assert (await _buy(client, gateway_key, request_id="req-00001")).status_code == 200
    second = await _buy(client, gateway_key, request_id="req-00002")
    assert second.status_code == 200
    assert second.json() == {"yuanbao": START - 200, "added": [], "recent_got": [2007], "replayed": False}
    assert await _state(client, gateway_key) == (START - 200, {2007: 2})
    assert await _ledger_rows() == 2


async def test_same_request_id_with_a_different_body_is_refused(client, gateway_key):
    await _resolve(client, gateway_key)
    assert (await _buy(client, gateway_key)).status_code == 200
    for changed in ({"price": 200}, {"props": (2007, 111897)}):
        refused = await _buy(client, gateway_key, **changed)
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["code"] == "request_id_reused"
    assert await _state(client, gateway_key) == (START - 100, {2007: 1})
    assert await _ledger_rows() == 1


async def test_without_request_id_every_call_charges(client, gateway_key):
    await _resolve(client, gateway_key)
    for expected in (START - 100, START - 200):
        bought = await _buy(client, gateway_key, request_id=None)
        assert bought.status_code == 200
        assert "replayed" not in bought.json()
        assert bought.json()["yuanbao"] == expected
    assert await _state(client, gateway_key) == (START - 200, {2007: 2})
    assert await _ledger_rows() == 0


async def test_free_draw_with_request_id_is_recorded_once(client, gateway_key):
    await _resolve(client, gateway_key)
    draw = dict(price=0, props=(2007, 111897), reason="draw:105", request_id="draw-0001")
    first = await _buy(client, gateway_key, **draw)
    assert first.json() == {"yuanbao": START, "added": [2007, 111897], "recent_got": [2007, 111897], "replayed": False}
    again = await _buy(client, gateway_key, **draw)
    assert again.json()["replayed"] is True
    assert await _state(client, gateway_key) == (START, {2007: 1, 111897: 1})
    assert await _ledger_rows() == 1


async def test_refusal_is_not_recorded_and_can_be_retried_after_top_up(client, gateway_key):
    from app.infrastructure.database import SessionLocal
    from app.models.gateway import GatewayIdentity
    from app.models.player import Player
    from app.services.inventory_service import InventoryService

    await _resolve(client, gateway_key)
    price = START + 50
    refused = await _buy(client, gateway_key, price=price, request_id="big-00001")
    assert refused.status_code == 409
    assert await _state(client, gateway_key) == (START, {})
    assert await _ledger_rows() == 0

    async with SessionLocal() as session:
        account_id = await session.scalar(select(GatewayIdentity.account_id).where(GatewayIdentity.external_uid == UID))
        player_id = await session.scalar(select(Player.id).where(Player.account_id == account_id))
        await InventoryService(session).apply_currency(player_id, "yuanbao", 100, "topup:test")

    retried = await _buy(client, gateway_key, price=price, request_id="big-00001")
    assert retried.status_code == 200, retried.text
    assert retried.json() == {"yuanbao": 50, "added": [2007], "recent_got": [2007], "replayed": False}
    replay = await _buy(client, gateway_key, price=price, request_id="big-00001")
    assert replay.json()["replayed"] is True
    assert await _state(client, gateway_key) == (50, {2007: 1})


async def test_concurrent_requests_with_the_same_id_apply_once(client, gateway_key):
    await _resolve(client, gateway_key)
    answers = await asyncio.gather(*(_buy(client, gateway_key, request_id="race-0001") for _ in range(5)))
    assert [a.status_code for a in answers] == [200] * 5
    assert sorted(a.json()["replayed"] for a in answers) == [False, True, True, True, True]
    assert await _state(client, gateway_key) == (START - 100, {2007: 1})
    assert await _ledger_rows() == 1


@pytest.mark.parametrize("bad", ["short", "x" * 65, "has space1", "semi;colon", ""])
async def test_invalid_request_id_is_422(client, gateway_key, bad):
    await _resolve(client, gateway_key)
    answer = await _buy(client, gateway_key, request_id=bad)
    assert answer.status_code == 422
    assert await _state(client, gateway_key) == (START, {})
