"""athlete_requests.plan_cultivate_compound against the real client extract
(extract/appearance_cultivate.json)."""

import athlete_requests as ar

THUNDER, THUNDER_LV1, THUNDER_LV2 = 142091, 142091, 142092
HOVER, HOVER_LV1, HOVER_LV2, HOVER_MAX = 140059, 140056, 140057, 140059


def plan(cid, rid, counts, gold, ctype=0):
    return ar.plan_cultivate_compound(cid, rid, ctype, counts, gold)


def test_thunder_lv2_success_with_two_copies_and_1000_coins():
    p = plan(THUNDER, THUNDER_LV2, {THUNDER_LV1: 2}, 1000)
    assert p["ok"] is True
    assert p["target"] == THUNDER_LV2
    assert p["consume"] == [(THUNDER_LV1, 1)]
    assert p["consume_currency"] == [(1, 1000)]
    assert p["add"] == [(THUNDER_LV2, 1)]
    # One entry per prop with the largest count: RoS_Server sums repeated ids, so the earlier
    # level (own 1) and the unlock count (own 2) must not become "own 3".
    assert p["require"] == [(THUNDER_LV1, 2)]


def test_thunder_lv2_fails_with_one_copy():
    p = plan(THUNDER, THUNDER_LV2, {THUNDER_LV1: 1}, 5000)
    assert p["ok"] is False and p["reason"] == "unlock"
    assert (p["currency_type"], p["price"]) == (0, 0)


def test_thunder_lv2_fails_with_999_coins_and_reports_the_price():
    p = plan(THUNDER, THUNDER_LV2, {THUNDER_LV1: 2}, 999)
    assert p["ok"] is False and p["reason"] == "currency"
    assert (p["currency_type"], p["price"]) == (1, 1000)
    assert p["tips"] == ar.CULTIVATE_TIPS["currency"]


def test_thunder_lv2_fails_when_already_owned():
    p = plan(THUNDER, THUNDER_LV2, {THUNDER_LV1: 2, THUNDER_LV2: 1}, 1000)
    assert p["ok"] is False and p["reason"] == "completed"


def test_wrong_chain_or_rule_fails():
    assert plan(999999, THUNDER_LV2, {THUNDER_LV1: 2}, 1000)["reason"] == "unknown"
    assert plan(THUNDER, HOVER_LV2, {THUNDER_LV1: 2, HOVER_LV1: 2}, 9000)["reason"] == "unknown"
    assert plan(HOVER, THUNDER_LV2, {THUNDER_LV1: 2}, 9000)["reason"] == "unknown"


def test_compound_type_1_is_unsupported():
    p = plan(THUNDER, THUNDER_LV2, {THUNDER_LV1: 2}, 1000, ctype=1)
    assert p["ok"] is False and p["reason"] == "compound_type"


def test_hovering_car_max_fails_when_lv2_not_owned():
    p = plan(HOVER, HOVER_MAX, {HOVER_LV1: 3}, 10000)
    assert p["ok"] is False and p["reason"] == "preceding"


def test_hovering_car_max_succeeds_after_lv2():
    p = plan(HOVER, HOVER_MAX, {HOVER_LV1: 2, HOVER_LV2: 1}, 2000)
    assert p["ok"] is True and p["target"] == HOVER_MAX
    assert p["consume"] == [(HOVER_LV1, 1)] and p["consume_currency"] == [(1, 2000)]


def test_lv1_base_skin_is_not_free():
    p = plan(THUNDER, THUNDER_LV1, {}, 100000)
    assert p["ok"] is False and p["reason"] == "not_craftable"
