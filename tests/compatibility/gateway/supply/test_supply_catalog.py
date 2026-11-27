"""Every box in extract/supplement_info.json: price shape the client's supply UIs read, prize pool,
draw 1x / multi draw counts, and draw_price for each accepted currency.

Category. supplement_info.json has no category name; its only category field is KIND (int).
Each KIND maps to exactly one client SupplementKindEnum name in
data/reference/original_lobby.json (checked below). The Supply tab names used in the lobby
are tied to kinds only where repository evidence names them:
  Supreme  = MONTH_SUPPLEMENT (7)              LOBBY_FINDINGS "Supreme Supply (monthly box)";
                                               ros_server currencyList comment "Supreme: 214"
  Looks    = GUARANTEE_SUPPLEMENT (3)          ros_server comment "Looks Supply: currency 91"
  Vehicle  = GUARANTEE_SUPPLEMENT_VEHICLE (4)  enum name
  Firearms = WEAPON_SUPPLEMENT (5)             enum name
  Star     = not identifiable from the data (no KIND, enum name or currency names it).
Other kinds keep their enum name as the group.
"""

import collections
import random

import pytest

from supply_helpers import kind_names, raw_info

RAW = raw_info()
KIND_NAMES = kind_names()
TAB_BY_ENUM = {
    "MONTH_SUPPLEMENT": "Supreme",
    "GUARANTEE_SUPPLEMENT": "Looks",
    "GUARANTEE_SUPPLEMENT_VEHICLE": "Vehicle",
    "WEAPON_SUPPLEMENT": "Firearms",
}
YUANBAO = 2


def group(sid):
    enum = KIND_NAMES[sid]
    return TAB_BY_ENUM.get(enum, enum)


BOXES = sorted(RAW, key=lambda s: (group(s), s))
BOX_IDS = [f"{group(s)}-{s}" for s in BOXES]


def currencies(sid):
    c = RAW[sid]["CURRENCY_ID"]
    return list(c) if isinstance(c, list) else [c]


def prices(sid, field):
    p = RAW[sid][field]
    return list(p) if isinstance(p, list) else [p]


# ---- catalogue-wide facts ---------------------------------------------------------------------

def test_catalogue_and_prize_pools_cover_the_same_boxes(reqs):
    assert len(RAW) == 264
    assert set(reqs.supplement_info()) == set(RAW)
    for sid in RAW:
        assert reqs.supplement_prizes(sid), sid


def test_every_kind_maps_to_one_client_enum_name():
    by_kind = collections.defaultdict(set)
    for sid, info in RAW.items():
        by_kind[info["KIND"]].add(KIND_NAMES[sid])
    assert {k: sorted(v) for k, v in by_kind.items()} == {
        1: ["NORMAL_SUPPLEMENT"], 2: ["TIME_LIMIT_SUPPLEMENT"], 3: ["GUARANTEE_SUPPLEMENT"],
        4: ["GUARANTEE_SUPPLEMENT_VEHICLE"], 5: ["WEAPON_SUPPLEMENT"], 7: ["MONTH_SUPPLEMENT"],
        99: ["KOF_SUPPLEMENT"], 101: ["ANNIVERSARY_CLOTH"], 102: ["ANNIVERSARY_WEAPON"],
        103: ["ANNIVERSARY_VEHICLE"], 202: ["BLACK_FRIDAY_2020"],
    }


def test_box_count_per_group_snapshot():
    """Snapshot of how many boxes each group has; a re-dump that drops a category shows here."""
    assert dict(collections.Counter(group(s) for s in RAW)) == {
        "Supreme": 79, "Firearms": 75, "Looks": 48, "Vehicle": 32, "NORMAL_SUPPLEMENT": 7,
        "ANNIVERSARY_WEAPON": 6, "ANNIVERSARY_CLOTH": 6, "ANNIVERSARY_VEHICLE": 4,
        "BLACK_FRIDAY_2020": 4, "KOF_SUPPLEMENT": 2, "TIME_LIMIT_SUPPLEMENT": 1,
    }


def test_no_box_is_a_star_supply_box_by_any_field():
    """Star Supply cannot be found in the data: no field value or enum name mentions it."""
    assert not any("STAR" in name for name in KIND_NAMES.values())
    assert not any("STAR" in str(k).upper() for info in RAW.values() for k in info)


def test_ticket_currencies_are_every_non_diamond_box_currency(reqs):
    expected = sorted({c for s in RAW for c in currencies(s) if c != YUANBAO})
    assert reqs.supply_ticket_currencies() == expected == [6, 9, 11, 91, 202, 207, 214]


# ---- per box ----------------------------------------------------------------------------------

@pytest.mark.parametrize("sid", BOXES, ids=BOX_IDS)
def test_price_fields_follow_the_one_or_two_currency_shape(reqs, sid):
    """One-currency boxes: scalar CURRENCY_ID / BUY_TIMES_PRICE / BUY_MULTIPLE_TIMES_PRICE (a list
    crashed currency_utils.getCurrencyIcon). Two-currency boxes: 2-element lists for all three."""
    info = reqs.supplement_info()[sid]
    for field in ("CURRENCY_ID", "BUY_TIMES_PRICE", "BUY_MULTIPLE_TIMES_PRICE", "NEXT_BUY_TIMES_PRICE",
                  "KIND", "SORT_KEY", "CURRENT_DISCOUNT", "IS_IN_SALE"):
        assert field in info, field
    cur = info["CURRENCY_ID"]
    price_fields = ("BUY_TIMES_PRICE", "BUY_MULTIPLE_TIMES_PRICE", "NEXT_BUY_TIMES_PRICE")
    if isinstance(cur, list):
        assert len(cur) == 2 and all(isinstance(c, int) for c in cur) and len(set(cur)) == 2
        for field in price_fields:
            assert isinstance(info[field], list) and len(info[field]) == 2, field
            assert all(isinstance(p, int) and p >= 0 for p in info[field]), field
    else:
        assert isinstance(cur, int)
        for field in price_fields:
            assert isinstance(info[field], int) and info[field] >= 0, field
    # Result screens read NEXT_BUY_TIMES_PRICE; prices do not rise on this server.
    assert info["NEXT_BUY_TIMES_PRICE"] == info["BUY_TIMES_PRICE"]
    assert all(p > 0 for p in prices(sid, "BUY_TIMES_PRICE")), "a single draw is never free"


@pytest.mark.parametrize("sid", BOXES, ids=BOX_IDS)
def test_single_draw_returns_one_prize_from_the_pool(reqs, sid):
    pool = set(reqs.supplement_prizes(sid))
    prizes = reqs.draw(sid, 1, rng=random.Random(sid))
    assert len(prizes) == 1 and prizes[0] in pool


@pytest.mark.parametrize("sid", BOXES, ids=BOX_IDS)
def test_multi_draw_returns_multi_count_prizes_from_the_pool(reqs, sid):
    pool = set(reqs.supplement_prizes(sid))
    n = reqs.multi_count(sid)
    assert n == 10
    prizes = reqs.draw(sid, n, rng=random.Random(sid))
    assert len(prizes) == n and set(prizes) <= pool


@pytest.mark.parametrize("sid", BOXES, ids=BOX_IDS)
def test_draw_price_for_each_accepted_currency(reqs, sid):
    once, ten = prices(sid, "BUY_TIMES_PRICE"), prices(sid, "BUY_MULTIPLE_TIMES_PRICE")
    for cid, p1, p10 in zip(currencies(sid), once, ten):
        assert reqs.draw_price(sid, cid) == p1
        assert reqs.draw_price(sid, cid, multi=True) == p10
    # a currency the box does not list has no price
    assert reqs.draw_price(sid, 999999) == 0


# ---- group summaries (one assertion per category, so a broken category is named) --------------

@pytest.mark.parametrize("name", ["Supreme", "Looks", "Vehicle", "Firearms"])
def test_named_category_boxes_draw_1x_and_10x(reqs, name):
    boxes = [s for s in RAW if group(s) == name]
    assert boxes
    rng = random.Random(1)
    for sid in boxes:
        assert len(reqs.draw(sid, 1, rng=rng)) == 1
        assert len(reqs.draw(sid, reqs.multi_count(sid), rng=rng)) == 10


def test_category_currencies_snapshot():
    """Which currencies each category is paid in (Looks: ticket 91 or diamonds; Supreme: 214 or
    diamonds; Vehicle and Firearms: diamonds only)."""
    seen = collections.defaultdict(set)
    for sid in RAW:
        seen[group(sid)].add(str(RAW[sid]["CURRENCY_ID"]))
    assert seen["Supreme"] == {"[214, 2]", "2"}
    assert seen["Looks"] == {"[91, 2]", "9"}
    assert seen["Vehicle"] == {"2"}
    assert seen["Firearms"] == {"2"}


def test_box_without_a_multi_price_is_the_only_time_limit_box():
    """Box 2 (TIME_LIMIT_SUPPLEMENT, currencies 6/11) has BUY_MULTIPLE_TIMES_PRICE [0, 0]: no 10x."""
    zero_multi = [s for s in RAW if 0 in prices(s, "BUY_MULTIPLE_TIMES_PRICE")]
    assert zero_multi == [2]
