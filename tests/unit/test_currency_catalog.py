"""The operator currency catalog: unique ledger-safe codes and the original client's ids."""

from app.services.currency_catalog import CURRENCIES, currency_list
from app.services.gateway_service import GOLD, YUANBAO
from app.services.store_service import CODE


def test_codes_are_unique_and_fit_the_ledger():
    codes = [row.code for row in CURRENCIES]
    assert len(codes) == len(set(codes))
    assert all(CODE.fullmatch(code) for code in codes)


def test_client_ids_are_unique_and_gateway_codes_match():
    ids = [row.client_id for row in CURRENCIES if row.client_id is not None]
    assert len(ids) == len(set(ids))
    by_code = {row.code: row for row in CURRENCIES}
    assert (by_code[GOLD].client_id, by_code[YUANBAO].client_id) == (1, 2)
    assert {row["code"] for row in currency_list() if row["scope"] == "web"} == {"coin", "diamond"}
