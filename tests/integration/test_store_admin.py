"""Store admin reads the currency ledger; top-ups and refunds are audited credits."""

PASSWORD = "StrongTestPassword123!"


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def _buyer(client) -> tuple[str, dict[str, str]]:
    created = await client.post("/api/v1/auth/register", json={"username": "store_buyer", "password": PASSWORD})
    token = (await client.post("/api/v1/auth/login", json={"username": "store_buyer", "password": PASSWORD})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    bought = await client.post("/api/v1/cosmetics/skins/field_jacket/purchase", headers=headers)
    assert bought.status_code == 200, bought.text
    return created.json()["id"], headers


async def test_ledger_summary_catalog_topup_and_refund(client):
    account_id, player = await _buyer(client)
    headers = await _operator(client, "store_lead", ["support"])

    ledger = (await client.get("/api/v1/admin/store/ledger?kind=purchase", headers=headers)).json()
    purchase = ledger["items"][0]
    assert (purchase["kind"], purchase["amount"], purchase["item"], purchase["account_id"]) == ("purchase", -200, "skin field_jacket", account_id)

    summary = (await client.get("/api/v1/admin/store/summary?days=7", headers=headers)).json()
    assert summary["spent"]["coin"] == 200
    assert (summary["purchases"], summary["buyers"]) == (1, 1)
    assert summary["top_items"][0]["item"] == "skin field_jacket"
    assert summary["daily"][-1]["coin"] == 200

    currencies = (await client.get("/api/v1/admin/store/currencies", headers=headers)).json()
    assert {"coin", "diamond", "gold", "yuanbao", "colour_diamond"} <= {row["code"] for row in currencies}
    assert (await client.get("/api/v1/admin/store/currencies")).status_code == 401

    catalog = (await client.get("/api/v1/admin/store/catalog", headers=headers)).json()
    assert next(row for row in catalog if row["code"] == "field_jacket")["sold"] == 1

    topped = await client.post(
        "/api/v1/admin/store/topup",
        headers=headers,
        json={"account_id": account_id, "currency": "diamond", "amount": 60, "reference": "ORD-1001", "reason": "Paid by bank transfer."},
    )
    assert topped.status_code == 201, topped.text
    assert topped.json()["kind"] == "topup"
    again = await client.post(
        "/api/v1/admin/store/topup",
        headers=headers,
        json={"account_id": account_id, "currency": "diamond", "amount": 60, "reference": "ORD-1001", "reason": "Duplicate."},
    )
    assert again.status_code == 409

    refunded = await client.post("/api/v1/admin/store/refund", headers=headers, json={"transaction_id": purchase["id"], "reason": "Bought by mistake."})
    assert refunded.status_code == 201
    assert refunded.json()["amount"] == 200
    assert (await client.post("/api/v1/admin/store/refund", headers=headers, json={"transaction_id": purchase["id"], "reason": "Twice."})).status_code == 409
    assert (await client.post("/api/v1/admin/store/refund", headers=headers, json={"transaction_id": topped.json()["id"], "reason": "Not a buy."})).status_code == 422

    wallet = (await client.get("/api/v1/cosmetics/wallet", headers=player)).json()
    assert (wallet["coin"], wallet["diamond"]) == (500, 80)
    marked = (await client.get("/api/v1/admin/store/ledger?kind=purchase", headers=headers)).json()["items"][0]
    assert marked["refunded"] is True
    audit = {row["action"] for row in (await client.get("/api/v1/admin/audit", headers=headers)).json()}
    assert {"store.topup", "store.refund"} <= audit


async def test_store_needs_permissions(client):
    account_id, _player = await _buyer(client)
    viewer = await _operator(client, "store_viewer", ["game_admin"])
    assert (await client.get("/api/v1/admin/store/ledger", headers=viewer)).status_code == 403
    denied = await client.post(
        "/api/v1/admin/store/topup",
        headers=viewer,
        json={"account_id": account_id, "currency": "coin", "amount": 5, "reference": "X", "reason": "Try it."},
    )
    assert denied.status_code == 403
