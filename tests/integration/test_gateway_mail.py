"""System mail: operator send, gateway list / detail / claim / delete (RO-115, RO-116, RO-117)."""

from datetime import timedelta

import pytest

KEY = "test-gateway-key"
UID = "9000000888"
OTHER_UID = "9000000889"
BASE = f"/api/v1/gateway/accounts/{UID}"
PASSWORD = "StrongTestPassword123!"
PROP_A, PROP_B = 142091, 142092


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    monkeypatch.setattr(settings, "gateway_start_gold", 1000)
    return {"X-Gateway-Key": KEY}


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def _resolve(client, headers, uid=UID) -> str:
    resolved = await client.post("/api/v1/gateway/accounts/resolve", json={"external_uid": uid}, headers=headers)
    assert resolved.status_code == 200, resolved.text
    return resolved.json()["account_id"]


def _mail(account_ids, **extra) -> dict:
    body = {
        "account_ids": account_ids,
        "title": "Season reward",
        "content": "Thank you for playing. " * 4,
        "attachments": [{"prop_id": PROP_A, "number": 2}, {"prop_id": PROP_B, "number": 1}],
        "gold": 500,
        "reason": "Season 3 compensation",
    }
    return {**body, **extra}


async def _state(client, headers):
    state = (await client.get(f"{BASE}/state", headers=headers)).json()
    return {i["prop_id"]: i["number"] for i in state["items"]}, state["currencies"]["1"]


async def _send(client, gateway_key, **extra):
    account_id = await _resolve(client, gateway_key)
    operator = await _operator(client, "mail_lead", ["support"])
    sent = await client.post("/api/v1/admin/mails", json=_mail([account_id], **extra), headers=operator)
    assert sent.status_code == 201, sent.text
    return account_id, operator, sent.json()


async def test_operator_mail_is_listed_and_detail_marks_it_read(client, gateway_key):
    account_id, operator, sent = await _send(client, gateway_key)
    assert sent == {"sent": [{"account_id": account_id, "mail_id": 1}], "skipped": []}

    listed = await client.get(f"{BASE}/mails", headers=gateway_key)
    assert listed.status_code == 200
    (mail,) = listed.json()["mails"]
    assert mail["mail_id"] == 1 and mail["type"] == 1 and mail["sender"] == "System"
    assert mail["title"] == "Season reward"
    assert mail["abstract"] == ("Thank you for playing. " * 4)[:40]
    assert mail["unread"] is True and mail["claimed"] is False
    assert mail["attachments"] == [{"prop_id": PROP_A, "number": 2}, {"prop_id": PROP_B, "number": 1}]
    assert mail["gold"] == 500
    assert mail["deadline"] - mail["sent_at"] == 30 * 86400
    assert "content" not in mail

    detail = await client.get(f"{BASE}/mails/1", headers=gateway_key)
    assert detail.status_code == 200
    assert detail.json()["content"] == "Thank you for playing. " * 4
    assert (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"][0]["unread"] is False

    admin = await client.get(f"/api/v1/admin/mails?account_id={account_id}", headers=operator)
    assert admin.status_code == 200
    row = admin.json()["mails"][0]
    assert (row["sent_by"], row["deleted"], row["claimed"], row["unread"]) == ("mail_lead", False, False, False)
    audit = {r["action"] for r in (await client.get("/api/v1/admin/audit", headers=operator)).json()}
    assert "player.mail" in audit


async def test_claim_adds_items_and_gold_once(client, gateway_key):
    await _send(client, gateway_key)
    assert await _state(client, gateway_key) == ({}, 1000)

    first = await client.post(f"{BASE}/mails/1/claim", headers=gateway_key)
    assert first.status_code == 200, first.text
    assert first.json() == {
        "props": [{"prop_id": PROP_A, "number": 2}, {"prop_id": PROP_B, "number": 1}],
        "gold": 500,
        "items": [{"prop_id": PROP_A, "number": 2}, {"prop_id": PROP_B, "number": 1}],
        "currencies": {"1": 1500},
        "replayed": False,
    }
    assert await _state(client, gateway_key) == ({PROP_A: 2, PROP_B: 1}, 1500)

    second = await client.post(f"{BASE}/mails/1/claim", headers=gateway_key)
    assert second.status_code == 200
    assert second.json() == {**first.json(), "replayed": True}
    assert await _state(client, gateway_key) == ({PROP_A: 2, PROP_B: 1}, 1500)

    (mail,) = (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"]
    assert mail["claimed"] is True and mail["unread"] is False

    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.inventory import CurrencyTransaction

    async with SessionLocal() as session:
        reasons = (await session.scalars(select(CurrencyTransaction.reason).where(CurrencyTransaction.reason.like("gateway:mail:%")))).all()
    assert reasons == ["gateway:mail:1"]


async def test_deleted_mail_is_hidden_and_unclaimable(client, gateway_key):
    await _send(client, gateway_key)
    deleted = await client.delete(f"{BASE}/mails/1", headers=gateway_key)
    assert deleted.status_code == 204
    assert (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"] == []
    assert (await client.post(f"{BASE}/mails/1/claim", headers=gateway_key)).status_code == 404
    assert (await client.get(f"{BASE}/mails/1", headers=gateway_key)).status_code == 404
    assert (await client.delete(f"{BASE}/mails/1", headers=gateway_key)).status_code == 404
    assert (await client.post(f"{BASE}/mails/99/claim", headers=gateway_key)).status_code == 404
    assert await _state(client, gateway_key) == ({}, 1000)


async def test_expired_mail_is_hidden_and_unclaimable(client, gateway_key):
    account_id, operator, _sent = await _send(client, gateway_key)
    from sqlalchemy import update

    from app.infrastructure.database import SessionLocal
    from app.models.gateway import GatewayMail
    from app.models.types import utc_now

    async with SessionLocal() as session:
        await session.execute(update(GatewayMail).values(deadline=utc_now() - timedelta(minutes=1)))
        await session.commit()
    assert (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"] == []
    assert (await client.get(f"{BASE}/mails/1", headers=gateway_key)).status_code == 404
    assert (await client.post(f"{BASE}/mails/1/claim", headers=gateway_key)).status_code == 404
    assert await _state(client, gateway_key) == ({}, 1000)
    admin = (await client.get(f"/api/v1/admin/mails?account_id={account_id}", headers=operator)).json()["mails"]
    assert admin[0]["expired"] is True


async def test_send_validation_and_skips(client, gateway_key):
    account_id = await _resolve(client, gateway_key)
    operator = await _operator(client, "mail_lead", ["support"])
    seven = [{"prop_id": PROP_A + i, "number": 1} for i in range(7)]
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id], attachments=seven), headers=operator)).status_code == 422
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id], attachments=[{"prop_id": PROP_A, "number": 1000}]), headers=operator)).status_code == 422
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id], gold=10_000_001), headers=operator)).status_code == 422
    assert (await client.post("/api/v1/admin/mails", json=_mail([]), headers=operator)).status_code == 422

    web = await client.post("/api/v1/auth/register", json={"username": "web_only", "password": PASSWORD})
    text_only = _mail([account_id, web.json()["id"]], attachments=[], gold=0)
    sent = await client.post("/api/v1/admin/mails", json=text_only, headers=operator)
    assert sent.status_code == 201
    assert sent.json() == {"sent": [{"account_id": account_id, "mail_id": 1}], "skipped": [web.json()["id"]]}
    assert (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"][0]["type"] == 0


async def test_mail_ids_are_a_sequence_per_identity(client, gateway_key):
    first = await _resolve(client, gateway_key)
    second = await _resolve(client, gateway_key, OTHER_UID)
    operator = await _operator(client, "mail_lead", ["support"])
    one = await client.post("/api/v1/admin/mails", json=_mail([first]), headers=operator)
    both = await client.post("/api/v1/admin/mails", json=_mail([first, second, first]), headers=operator)
    assert one.json()["sent"] == [{"account_id": first, "mail_id": 1}]
    assert both.json()["sent"] == [{"account_id": first, "mail_id": 2}, {"account_id": second, "mail_id": 1}]
    ids = [m["mail_id"] for m in (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"]]
    assert ids == [2, 1]


async def test_non_operators_cannot_send(client, gateway_key):
    account_id = await _resolve(client, gateway_key)
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id]))).status_code == 401
    observer = await _operator(client, "mail_observer", ["observer"])
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id]), headers=observer)).status_code == 403
    await client.post("/api/v1/auth/register", json={"username": "plain_player", "password": PASSWORD})
    token = (await client.post("/api/v1/auth/login", json={"username": "plain_player", "password": PASSWORD})).json()["access_token"]
    player = {"Authorization": f"Bearer {token}"}
    assert (await client.post("/api/v1/admin/mails", json=_mail([account_id]), headers=player)).status_code == 401
    assert (await client.get(f"{BASE}/mails", headers=gateway_key)).json()["mails"] == []


async def test_mail_routes_need_the_gateway_key(client, gateway_key):
    await _send(client, gateway_key)
    assert (await client.get(f"{BASE}/mails")).status_code == 401
    assert (await client.get(f"{BASE}/mails/1", headers={"X-Gateway-Key": "nope"})).status_code == 401
    assert (await client.post(f"{BASE}/mails/1/claim")).status_code == 401
    assert (await client.delete(f"{BASE}/mails/1")).status_code == 401
    assert await _state(client, gateway_key) == ({}, 1000)
    assert (await client.get("/api/v1/gateway/accounts/123456/mails", headers=gateway_key)).status_code == 404
