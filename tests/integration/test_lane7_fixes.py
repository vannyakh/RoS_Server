"""Revoked props, operator sign-in limit, per-player mail, and database backup and restore."""

import sqlite3
from contextlib import closing

import pytest

from app.core.config import settings
from app.infrastructure import backup

PASSWORD = "StrongTestPassword123!"
UID = "9000000777"


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", "test-gateway-key")
    return {"X-Gateway-Key": "test-gateway-key"}


async def _operator(client, roles):
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    name = f"l7_{roles[0]}"[:32]
    async with SessionLocal() as session:
        await OperatorService(session).create_operator(name, PASSWORD, roles, audit=False)
    token = (await client.post("/api/v1/admin/auth/login", json={"username": name, "password": PASSWORD})).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


async def _player(client, key):
    made = await client.post("/api/v1/gateway/accounts/resolve", headers=key, json={"external_uid": UID})
    return made.json()["account_id"]


async def test_a_revoked_prop_is_not_owned_and_can_be_bought_again(client, key):
    account = await _player(client, key)
    admin = await _operator(client, ["support"])
    base = f"/api/v1/gateway/accounts/{UID}"
    for delta in (1, -1):
        body = {"kind": "prop", "key": "9183", "delta": delta, "reason": "test"}
        assert (await client.post(f"/api/v1/admin/players/{account}/adjustments", headers=admin, json=body)).status_code == 200
    assert (await client.get(f"{base}/state", headers=key)).json()["items"] == []
    bought = await client.post(f"{base}/purchase", headers=key, json={"price": 0, "props": [9183], "reason": "mall"})
    assert bought.json()["added"] == [9183]


async def test_operator_sign_in_is_rate_limited_without_locking_players(client):
    wrong = {"username": "nobody", "password": "x" * 14}
    codes = [(await client.post("/api/v1/admin/auth/login", json=wrong)).status_code for _ in range(7)]
    assert codes == [401] * 5 + [429] * 2
    assert (await client.post("/api/v1/auth/login", json=wrong)).status_code == 401


async def test_mail_goes_to_one_player_and_is_claimed_once(client, key):
    account = await _player(client, key)
    admin = await _operator(client, ["support"])
    other = "9000000778"
    await client.post("/api/v1/gateway/accounts/resolve", headers=key, json={"external_uid": other})
    body = {"title": "Gift", "content": "For you", "props": [[120901, 2]], "reason": "test mail"}
    sent = await client.post(f"/api/v1/admin/players/{account}/mail", headers=admin, json=body)
    assert sent.status_code == 201, sent.text
    number = sent.json()["id"]
    assert number == 1 and sent.json()["type"] == 1          # the player's game mail id

    base = f"/api/v1/gateway/accounts/{UID}"
    assert [m["id"] for m in (await client.get(f"{base}/mail", headers=key)).json()] == [number]
    assert (await client.get(f"/api/v1/gateway/accounts/{other}/mail", headers=key)).json() == []
    stolen = await client.post(f"/api/v1/gateway/accounts/{other}/mail/{number}/claim", headers=key)
    assert stolen.status_code == 404

    first = await client.post(f"{base}/mail/{number}/claim", headers=key)
    second = await client.post(f"{base}/mail/{number}/claim", headers=key)
    assert (first.json()["props"], second.json()["props"]) == ([[120901, 2]], [])
    assert (await client.get(f"{base}/state", headers=key)).json()["items"] == [{"prop_id": 120901, "number": 2}]
    audit = (await client.get("/api/v1/admin/audit", headers=admin)).json()
    assert any(row["action"] == "player.mail" and row["target_id"] == account for row in audit)


async def test_support_page_mail_reaches_the_game_mailbox(client, key):
    """Regression: mail sent from the support page must be on the route the game reads
    (`/gateway/accounts/{uid}/mails`, account_link.list_mails) and claimable there, once."""
    account = await _player(client, key)
    admin = await _operator(client, ["support"])
    body = {"title": "Support gift", "content": "Sorry for the trouble", "props": [[200027, 2], [203011, 1]],
            "reason": "support ticket"}
    sent = await client.post(f"/api/v1/admin/players/{account}/mail", headers=admin, json=body)
    assert sent.status_code == 201, sent.text
    number = sent.json()["id"]

    base = f"/api/v1/gateway/accounts/{UID}"
    listed = (await client.get(f"{base}/mails", headers=key)).json()["mails"]
    mine = [m for m in listed if m["mail_id"] == number]
    assert mine and mine[0]["title"] == "Support gift" and not mine[0]["claimed"]
    assert sorted((a["prop_id"], a["number"]) for a in mine[0]["attachments"]) == [(200027, 2), (203011, 1)]
    detail = (await client.get(f"{base}/mails/{number}", headers=key)).json()
    assert detail["content"] == "Sorry for the trouble"

    first = (await client.post(f"{base}/mails/{number}/claim", headers=key, json={})).json()
    second = (await client.post(f"{base}/mails/{number}/claim", headers=key, json={})).json()
    assert first["replayed"] is False and second["replayed"] is True
    items = {i["prop_id"]: i["number"] for i in (await client.get(f"{base}/state", headers=key)).json()["items"]}
    assert items == {200027: 2, 203011: 1}

    shown = (await client.get(f"/api/v1/admin/players/{account}/mail", headers=admin)).json()
    assert [(m["id"], m["claimed"]) for m in shown] == [(number, True)]
    in_admin_mails = (await client.get(f"/api/v1/admin/mails?account_id={account}", headers=admin)).json()["mails"]
    assert [m["mail_id"] for m in in_admin_mails] == [number]


async def test_support_page_mail_that_does_not_fit_the_game_mailbox_is_refused(client, key):
    account = await _player(client, key)
    admin = await _operator(client, ["support"])
    body = {"title": "T" * 70, "content": "x", "reason": "too long title"}   # support page allows 80, game 64
    refused = await client.post(f"/api/v1/admin/players/{account}/mail", headers=admin, json=body)
    assert refused.status_code == 422, refused.text


async def test_mail_needs_the_economy_permission(client, key):
    account = await _player(client, key)
    observer = await _operator(client, ["observer"])
    body = {"title": "Gift", "content": "For you", "reason": "test mail"}
    assert (await client.post(f"/api/v1/admin/players/{account}/mail", headers=observer, json=body)).status_code == 403


async def test_backup_restores_deleted_rows(client, key, tmp_path):
    await _player(client, key)
    live = backup.database_path(settings.database_url)
    saved = backup.backup(live, tmp_path / "saved.db")
    before = backup.verify(saved)
    copy = tmp_path / "damaged.db"
    backup.restore(saved, copy)
    with closing(sqlite3.connect(copy)) as db:
        db.execute("DELETE FROM gateway_identities")
        db.commit()
    kept = backup.restore(saved, copy)
    assert backup.verify(copy) == before
    assert backup.verify(kept)["gateway_identities"] == 0


def test_restore_refuses_a_file_that_is_not_a_database(tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database" * 100)
    target = tmp_path / "target.db"
    with pytest.raises(SystemExit):
        backup.restore(junk, target)
    assert not target.exists()


async def test_an_unhandled_error_reaches_the_operations_log(client, monkeypatch, caplog):
    from app.services.operator_service import OperatorService

    admin = await _operator(client, ["support"])

    async def broken(self):
        raise RuntimeError("lane7 boom")

    monkeypatch.setattr(OperatorService, "permissions", broken)
    with pytest.raises(RuntimeError):
        await client.get("/api/v1/admin/permissions", headers=admin)
    assert any(record.levelname == "ERROR" and record.name == "ros.error" for record in caplog.records)
