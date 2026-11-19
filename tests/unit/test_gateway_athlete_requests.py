"""bigworld_gateway decodes original-client Athlete requests by name and answers supply draws."""

import importlib
import random
import struct
import sys
from pathlib import Path

import pytest


@pytest.fixture
def reqs(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    module = importlib.import_module("athlete_requests")
    yield importlib.reload(module)
    sys.modules.pop("athlete_requests", None)


# (msg id, payload hex, expected name) captured from the real client on LDPlayer.
CAPTURED = [
    (0xD0, "02", "getFriendList"),
    (0xF9, "bf00000000", "requestRoomListInfo"),
    (0xF9, "c0", "requestRoomCountInfo"),
    (0xF9, "f5", "queryAvailableSupplement"),
    (0xFA, "bbec43ae1902000000", "getAthleteRosMatchTeamBriefData"),
    (0xFD, "57", "refreshMicroServiceToken"),
]


@pytest.mark.parametrize(("msgid", "payload", "name"), CAPTURED)
def test_captured_requests_decode_to_their_names(reqs, msgid, payload, name):
    decoded = reqs.decode(msgid, bytes.fromhex(payload))
    assert decoded is not None
    assert decoded[0] == name


def test_encode_is_the_inverse_of_decode_for_every_exposed_method(reqs):
    names = reqs._load_names()
    assert len(names) == 1191
    for name in ("getFriendList", "createCharacter", "openSupplyBoxFree", "setPortrait", "requestFilePickerToken"):
        msgid, payload = reqs.encode_call(name, b"\x01\x02")
        assert reqs.decode(msgid, payload) == (name, b"\x01\x02")


def test_non_entity_messages_are_not_decoded(reqs):
    assert reqs.decode(0x08, b"") is None
    assert reqs.decode(0xF9, b"") is None
    assert reqs.decode(0xFE, b"\x00") is None


def test_create_character_arguments_are_read_in_def_order(reqs):
    args = struct.pack("<i", 20001) + bytes([5]) + b"Raven" + struct.pack("<I", 0)
    reader = reqs.Reader(args)
    assert reader.i32() == 20001
    assert reader.string() == "Raven"
    assert reader.i32_array() == []


def test_draws_come_from_the_box_prize_pool(reqs):
    pool = set(reqs.supplement_prizes(1))
    assert pool
    prizes = reqs.draw(1, 10, rng=random.Random(7))
    assert len(prizes) == 10
    assert set(prizes) <= pool
    assert reqs.draw(424242, 3) == []


def test_draw_price_follows_the_chosen_currency(reqs):
    # Box 9728 takes a ticket (214) or diamonds (2); box 5 only diamonds.
    assert reqs.draw_price(9728, 214) == 1
    assert reqs.draw_price(9728, 2) == 20
    assert reqs.draw_price(9728, 2, multi=True) == 190
    assert reqs.draw_price(5, 2) == 60
    assert reqs.draw_price(5, 999) == 0


def test_wallet_refuses_a_price_above_the_balance(reqs):
    wallet = reqs.Wallet({2: 100})
    assert wallet.pay(2, 60) is True
    assert wallet.pay(2, 60) is False
    assert wallet.balances[2] == 40


def test_hall_prop_prices_come_from_the_client_table(reqs):
    assert reqs.hallprop_price(120901) == (2, 2280)
    assert reqs.hallprop_price(1) is None


def test_outfit_tracks_body_and_wearable_items_separately(reqs):
    outfit = reqs.Outfit()
    assert outfit.equip(2007) == "wear"          # Leather Coat
    assert outfit.wear == [2007]
    assert outfit.equip(2007) == "wear"          # same id again: taken off
    assert outfit.wear == []
    assert reqs.appearance_type(2007) == "WearableApperanceType"
