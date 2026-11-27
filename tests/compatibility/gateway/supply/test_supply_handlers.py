"""GateUDP Supply handlers (Athlete base calls decoded by athlete_requests):
queryAvailableSupplement, openSupplyBox, openMultipleSupplyBox, openSupplyBoxFree,
setHasAlreadyShowSupplyID. Built offline: no socket, no RoS_Server, temp saved_accounts.json."""

import json
import struct

import pytest

from supply_helpers import ADDR, open_box, open_free, open_multi, read_blob, read_py

YUANBAO = 2
ADV_TICKET = 91
LOOKS = 1            # NORMAL box, currencies [2, 202], once [5, 50], ten [50, 500]
DIAMOND_ONLY = 5     # currency 2, once 60
TICKET_BOX = 9728    # Supreme, currencies [214, 2], once [1, 20], ten [10, 190]
PREVIOUS_LOOKS = 9507   # Looks Previous, currencies [91, 2], once [5, 150], ten [48, 1440]
STAR_SUPPLY = 1         # Star Supply KIND 1, currencies [2, 202], once [5, 50], ten [50, 500]
ELITE_TICKET = 202
UNKNOWN = 424242


def names(calls):
    return [n for n, _ in calls]


def opened(calls, method):
    """(sid, prizes, rest) of the last `method` call."""
    args = [a for n, a in calls if n == method][-1]
    sid = struct.unpack_from("<i", args)[0]
    prizes, i = read_py(args, 4)
    return sid, prizes, args[i:]


# ---- request decoding -------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["queryAvailableSupplement", "openSupplyBox", "openMultipleSupplyBox",
                                  "openSupplyBoxFree", "setHasAlreadyShowSupplyID"])
def test_supply_requests_round_trip_by_name(reqs, name):
    msgid, payload = reqs.encode_call(name, b"\x05\x00\x00\x00")
    assert reqs.decode(msgid, payload) == (name, b"\x05\x00\x00\x00")


# ---- queryAvailableSupplement -----------------------------------------------------------------

def test_query_sends_full_catalogue_then_free_lottery_state(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    assert reply
    assert names(recorder) == ["onQueryAvailableSupplement", "onUpdateFreeLotteryTimeStampDict"]
    catalogue, end = read_py(recorder[0][1])
    assert end == len(recorder[0][1])
    assert catalogue == gw.athlete_requests.supplement_info()
    assert len(catalogue) == 264 and all(isinstance(k, int) for k in catalogue)
    ts, i = read_py(recorder[1][1])
    times, j = read_py(recorder[1][1], i)
    assert (ts, times, j) == ({}, {}, len(recorder[1][1]))


def test_query_catalogue_needs_the_long_blob_form(gw, udp, recorder):
    """The pickled catalogue is > 255 bytes, so it is sent with the 0xFF + u24 length."""
    udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    args = recorder[0][1]
    assert args[0] == 0xFF
    assert 255 < len(args) < 64 * 1024


# ---- openSupplyBox / openMultipleSupplyBox ----------------------------------------------------

def _appearance_prize(gw, sid):
    """A prize of box `sid` that is an appearance item (granted with onAddDtsAppearanceItem)."""
    appearance = set(gw._all_appearance_ids())
    return next(p for p in gw.athlete_requests.supplement_prizes(sid) if p in appearance)


def test_single_diamond_draw_charges_and_ends_with_on_open_supply_box(gw, udp, recorder, monkeypatch):
    """Reply order (GateUDP._athlete_request, openSupplyBox): onYBUpdated, the won item
    (onAddDtsAppearanceItem + onUpdateRecentGotPropIDList), then the result screen
    (onOpenSupplyBox) last, so the item is already in the package when the result shows it.
    The prize is pinned to an appearance item: a random non-appearance prize is display-only
    and sends no onAddDtsAppearanceItem / recent-got update."""
    prize = _appearance_prize(gw, LOOKS)
    monkeypatch.setattr(gw.athlete_requests, "draw", lambda sid, count, rng=None: [prize] * count)
    reply = open_box(udp, LOOKS, YUANBAO)
    assert reply
    assert names(recorder) == ["onYBUpdated", "onAddDtsAppearanceItem", "onUpdateRecentGotPropIDList",
                               "onOpenSupplyBox"]
    sid, prizes, rest = opened(recorder, "onOpenSupplyBox")
    assert sid == LOOKS and len(prizes) == 1
    assert set(prizes) <= set(gw.athlete_requests.supplement_prizes(LOOKS))
    assert rest == b"\x00"                                       # isWatchAd echoed
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 - 5


@pytest.mark.parametrize(("request_name", "reply_name"), [
    ("openSupplyBox", "onOpenSupplyBox"),
    ("openMultipleSupplyBox", "onMultiOpenSupplyBox"),
    ("openSupplyBoxFree", "onOpenFreeSupplyBox"),
])
def test_reply_bytes_end_with_the_on_open_method(gw, udp, monkeypatch, request_name, reply_name):
    """Wire check without the recorder: the reply ends with the encoded onOpen* call."""
    fixed = [15, 16]
    monkeypatch.setattr(gw.athlete_requests, "draw", lambda sid, count, rng=None: fixed[:1] * count)
    args = struct.pack("<i", TICKET_BOX)
    if request_name != "openSupplyBoxFree":
        args += struct.pack("<iI", YUANBAO, 0)
    reply = udp._athlete_request(ADDR, request_name, args)
    count = 10 if request_name == "openMultipleSupplyBox" else 1
    tail = struct.pack("<i", TICKET_BOX) + gw.athlete_requests.py([15] * count)
    if request_name == "openSupplyBox":
        tail += b"\x00"
    assert reply.endswith(gw.athlete_method(reply_name, tail, quiet=True))


def test_single_draw_echoes_watch_ad_flag(gw, udp, recorder):
    open_box(udp, LOOKS, YUANBAO, watch_ad=1)
    assert opened(recorder, "onOpenSupplyBox")[2] == b"\x01"


def test_single_draw_without_watch_ad_byte_is_accepted(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "openSupplyBox", struct.pack("<iiI", LOOKS, YUANBAO, 0))
    assert reply and names(recorder)[-1] == "onOpenSupplyBox"


def test_multi_diamond_draw_returns_multi_count_prizes(gw, udp, recorder):
    reply = open_multi(udp, TICKET_BOX, YUANBAO)
    assert reply and names(recorder)[-1] == "onMultiOpenSupplyBox"
    sid, prizes, rest = opened(recorder, "onMultiOpenSupplyBox")
    assert sid == TICKET_BOX and rest == b""
    assert len(prizes) == gw.athlete_requests.multi_count(TICKET_BOX) == 10
    assert set(prizes) <= set(gw.athlete_requests.supplement_prizes(TICKET_BOX))
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 - 190


def test_star_supply_elite_ticket_draw_charges_and_syncs(gw, udp, recorder):
    """Star Supply (box 1) paid in Elite Ticket (202) must deduct tickets and send onCurrencyUpdated."""
    open_box(udp, STAR_SUPPLY, ELITE_TICKET)
    assert "onYBUpdated" not in names(recorder)
    assert ("onCurrencyUpdated", struct.pack("<iqi", ELITE_TICKET, 999 - 50, 0)) in recorder
    assert names(recorder)[-1] == "onOpenSupplyBox"
    assert udp._session_wallet(ADDR).balances[ELITE_TICKET] == 999 - 50


def test_star_supply_diamond_draw_charges_and_completes(gw, udp, recorder, monkeypatch):
    prize = _appearance_prize(gw, STAR_SUPPLY)
    monkeypatch.setattr(gw.athlete_requests, "draw", lambda sid, count, rng=None: [prize] * count)
    reply = open_box(udp, STAR_SUPPLY, YUANBAO)
    assert reply
    assert names(recorder) == ["onYBUpdated", "onAddDtsAppearanceItem", "onUpdateRecentGotPropIDList",
                               "onOpenSupplyBox"]
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 - 5


def test_ticket_draw_charges_the_ticket_and_syncs_balance(gw, udp, recorder):
    """Non-diamond supply draws deduct the ticket currency and send onCurrencyUpdated."""
    open_box(udp, TICKET_BOX, 214)
    assert "onYBUpdated" not in names(recorder)
    assert ("onCurrencyUpdated", struct.pack("<iqi", 214, 999 - 1, 0)) in recorder
    assert names(recorder)[-1] == "onOpenSupplyBox"
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000
    assert udp._session_wallet(ADDR).balances[214] == 999 - 1


@pytest.mark.parametrize("currency", [ADV_TICKET, YUANBAO])
def test_previous_looks_multi_draw_settles(gw, udp, recorder, monkeypatch, currency):
    """Looks Supply > Previous (box 9507): 10x paid in Adv. Ticket or diamonds completes."""
    price = gw.athlete_requests.draw_price(PREVIOUS_LOOKS, currency, multi=True)
    if currency == YUANBAO:
        gw.LOGIN_STATE["yuanbao"] = price + 500
    prize = _appearance_prize(gw, PREVIOUS_LOOKS)
    monkeypatch.setattr(gw.athlete_requests, "draw", lambda sid, count, rng=None: [prize] * count)
    before = dict(udp._session_wallet(ADDR).balances)
    reply = open_multi(udp, PREVIOUS_LOOKS, currency)
    assert reply and names(recorder)[-1] == "onMultiOpenSupplyBox"
    assert udp._session_wallet(ADDR).balances[currency] == before[currency] - price


def test_won_prizes_are_recorded_for_the_session_and_saved_locally(gw, udp, recorder):
    open_multi(udp, TICKET_BOX, YUANBAO)
    _, prizes, _ = opened(recorder, "onMultiOpenSupplyBox")
    assert set(prizes) <= udp._owned(ADDR)
    assert sum(udp._counts(ADDR).values()) == 10
    saved = json.load(open(gw.ACCOUNTS_FILE, encoding="utf-8"))
    key = gw._inventory_key()
    assert set(prizes) <= set(saved[key]["items"])
    assert saved[key]["yuanbao"] == 1000 - 190


def test_draw_syncs_stale_session_wallet_from_login_state(gw, udp, recorder):
    """Lobby balance can be ahead of the lazy session Wallet (first Supreme Supply tap)."""
    gw.LOGIN_STATE["yuanbao"] = 68088
    udp._session_wallet(ADDR).balances[YUANBAO] = 0
    open_box(udp, TICKET_BOX, YUANBAO)
    assert "onOpenSupplyBox" in names(recorder)
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 68088 - 20


def test_rapid_duplicate_draws_are_each_settled(gw, udp, recorder):
    """Two identical requests in a row (double tap / retransmit at the entity layer) are two
    draws: there is no in-flight guard or request id for Supply, so both are charged."""
    open_box(udp, DIAMOND_ONLY, YUANBAO)
    open_box(udp, DIAMOND_ONLY, YUANBAO)
    assert names(recorder).count("onOpenSupplyBox") == 2
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000 - 2 * 60


def test_rapid_draws_stop_when_diamonds_run_out(gw, udp, recorder):
    gw.LOGIN_STATE["yuanbao"] = 100
    open_box(udp, DIAMOND_ONLY, YUANBAO)
    open_box(udp, DIAMOND_ONLY, YUANBAO)
    assert names(recorder)[-2:] == ["onOpenSupplyBoxFailed", "onYBUpdated"]
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 40


# ---- failure path -----------------------------------------------------------------------------

def _failed_args(sid, currency, price):
    return struct.pack("<i", sid) + b"\x00" + struct.pack("<ii", currency, price) + struct.pack("<I", 0)


def _yb_sync(amount):
    return ("onYBUpdated", struct.pack("<qqi", amount, 0, 0))


def _cur_sync(cid, amount):
    return ("onCurrencyUpdated", struct.pack("<iqi", cid, amount, 0))


def _failed_with_sync(fail_method, sid, currency, price, sync):
    return [(fail_method, _failed_args(sid, currency, price)), sync]


def test_single_draw_fails_when_local_wallet_is_short(gw, udp, recorder):
    gw.LOGIN_STATE["yuanbao"] = 59
    reply = open_box(udp, DIAMOND_ONLY, YUANBAO)
    assert reply
    assert recorder == _failed_with_sync(
        "onOpenSupplyBoxFailed", DIAMOND_ONLY, YUANBAO, 60, _yb_sync(59)
    )
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 59
    assert udp._owned(ADDR) == set()


def test_multi_draw_fails_when_local_wallet_is_short(gw, udp, recorder):
    gw.LOGIN_STATE["yuanbao"] = 189
    open_multi(udp, TICKET_BOX, YUANBAO)
    assert recorder == _failed_with_sync(
        "onMultiOpenSupplyBoxFailed", TICKET_BOX, YUANBAO, 190, _yb_sync(189)
    )
    assert udp._owned(ADDR) == set()


def _link(gw, monkeypatch, result):
    """Linked mode: account_link.purchase answers `result` (None = unreachable). Side calls
    (recent-got state/outfit) go through account_link._call, answered as "down"."""
    calls = []

    def purchase(price, props, reason, request_id=None):
        assert request_id                                       # every linked draw carries one
        calls.append((price, list(props), reason))
        return result

    gw.account_link._current = {"external_uid": "9000000001", "gid": 1}
    monkeypatch.setattr(gw.account_link, "purchase", purchase)
    monkeypatch.setattr(gw.account_link, "_call", lambda method, path, body: None)
    return calls


def test_linked_refusal_sends_failed_and_grants_nothing(gw, udp, recorder, monkeypatch):
    calls = _link(gw, monkeypatch, {"_error": 409})
    open_multi(udp, TICKET_BOX, YUANBAO)
    assert recorder == _failed_with_sync(
        "onMultiOpenSupplyBoxFailed", TICKET_BOX, YUANBAO, 190, _yb_sync(1000)
    )
    (price, props, reason), = calls
    assert price == 190 and len(props) == 10 and reason == f"draw:{TICKET_BOX}"
    assert udp._owned(ADDR) == set()


def test_linked_success_uses_ros_server_balance(gw, udp, recorder, monkeypatch):
    prize = _appearance_prize(gw, LOOKS)
    monkeypatch.setattr(gw.athlete_requests, "draw", lambda sid, count, rng=None: [prize] * count)
    _link(gw, monkeypatch, {"yuanbao": 777, "added": [prize]})
    open_box(udp, LOOKS, YUANBAO)
    assert names(recorder) == ["onYBUpdated", "onAddDtsAppearanceItem", "onUpdateRecentGotPropIDList",
                               "onOpenSupplyBox"]
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 777
    assert recorder[0] == ("onYBUpdated", struct.pack("<qqi", 777, 0, 0))


def test_linked_but_unreachable_refuses_the_draw(gw, udp, recorder, monkeypatch):
    """Same rule as the Store: linked and RoS_Server unreachable -> refused, nothing charged or
    granted locally (a local fallback would diverge from the RoS_Server account)."""
    calls = _link(gw, monkeypatch, None)
    open_box(udp, LOOKS, YUANBAO)
    assert len(calls) == 1
    assert recorder == _failed_with_sync(
        "onOpenSupplyBoxFailed", LOOKS, YUANBAO, 5, _yb_sync(1000)
    )
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000
    assert udp._owned(ADDR) == set()


def test_linked_unreachable_free_draw_sends_nothing(gw, udp, recorder, monkeypatch):
    _link(gw, monkeypatch, None)
    assert open_free(udp, TICKET_BOX) == b""
    assert recorder == []
    assert TICKET_BOX not in udp._supply[ADDR].free_ts


# ---- openSupplyBoxFree ------------------------------------------------------------------------

def test_free_draw_updates_free_state_then_ends_with_on_open_free_supply_box(gw, udp, recorder):
    reply = open_free(udp, TICKET_BOX)
    assert reply
    assert names(recorder)[0] == "onUpdateFreeLotteryTimeStampDict"
    assert names(recorder)[-1] == "onOpenFreeSupplyBox"
    sid, prizes, rest = opened(recorder, "onOpenFreeSupplyBox")
    assert sid == TICKET_BOX and len(prizes) == 1 and rest == b""
    ts, i = read_py(recorder[0][1])
    times, _ = read_py(recorder[0][1], i)
    assert set(ts) == {TICKET_BOX} and times == {TICKET_BOX: 1}
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000


def test_query_after_free_draw_reports_the_free_draw(gw, udp, recorder):
    open_free(udp, TICKET_BOX)
    open_free(udp, TICKET_BOX)
    recorder.clear()
    udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    ts, i = read_py(recorder[1][1])
    times, _ = read_py(recorder[1][1], i)
    assert set(ts) == {TICKET_BOX} and times == {TICKET_BOX: 2}


def test_free_draw_state_is_per_session(gw, udp, recorder):
    open_free(udp, TICKET_BOX)
    recorder.clear()
    udp._athlete_request(("10.0.0.4", 6000), "queryAvailableSupplement", b"")
    ts, i = read_py(recorder[1][1])
    assert ts == {} and read_py(recorder[1][1], i)[0] == {}


# ---- unknown box id ---------------------------------------------------------------------------

def test_unknown_box_has_no_prizes_and_no_price(reqs):
    assert reqs.supplement_prizes(UNKNOWN) == []
    assert reqs.draw(UNKNOWN, 10) == []
    assert reqs.draw_price(UNKNOWN, YUANBAO) == 0


def test_unknown_box_draw_is_refused(gw, udp, recorder):
    reply = open_box(udp, UNKNOWN, YUANBAO)
    assert reply
    assert recorder == _failed_with_sync(
        "onOpenSupplyBoxFailed", UNKNOWN, YUANBAO, 0, _yb_sync(1000)
    )
    assert udp._session_wallet(ADDR).balances[YUANBAO] == 1000
    assert udp._owned(ADDR) == set()


def test_unknown_box_multi_draw_is_refused(gw, udp, recorder):
    open_multi(udp, UNKNOWN, YUANBAO)
    assert recorder == _failed_with_sync(
        "onMultiOpenSupplyBoxFailed", UNKNOWN, YUANBAO, 0, _yb_sync(1000)
    )


def test_unknown_box_free_draw_is_refused(gw, udp, recorder):
    """Athlete.def has no free-draw failure method: nothing is sent and nothing recorded."""
    assert open_free(udp, UNKNOWN) == b""
    assert recorder == []
    assert UNKNOWN not in udp._supply[ADDR].free_ts
    assert udp._owned(ADDR) == set()


def test_draw_with_a_currency_the_box_does_not_accept_is_refused(gw, udp, recorder):
    open_box(udp, DIAMOND_ONLY, 214)
    assert recorder == _failed_with_sync(
        "onOpenSupplyBoxFailed", DIAMOND_ONLY, 214, 0, _cur_sync(214, 999)
    )
    assert udp._owned(ADDR) == set()


def test_multi_draw_with_a_currency_the_box_does_not_accept_is_refused(gw, udp, recorder):
    open_multi(udp, TICKET_BOX, 91)
    assert recorder == _failed_with_sync(
        "onMultiOpenSupplyBoxFailed", TICKET_BOX, 91, 0, _cur_sync(91, 999)
    )


def test_refused_currency_is_not_sent_to_ros_server(gw, udp, recorder, monkeypatch):
    calls = _link(gw, monkeypatch, {"yuanbao": 1000, "added": []})
    open_box(udp, DIAMOND_ONLY, 214)
    open_box(udp, UNKNOWN, YUANBAO)
    assert calls == []


def test_free_draw_refused_by_ros_server_is_not_granted(gw, udp, recorder, monkeypatch):
    calls = _link(gw, monkeypatch, {"_error": 409})
    assert open_free(udp, TICKET_BOX) == b""
    assert recorder == []
    assert len(calls) == 1 and calls[0][0] == 0 and calls[0][2] == f"free:{TICKET_BOX}"
    assert TICKET_BOX not in udp._supply[ADDR].free_ts
    assert udp._owned(ADDR) == set()


# ---- setHasAlreadyShowSupplyID / setHasAlreadyShowMonthSupply ---------------------------------

THIS_WEEK = 9778     # lowest of the IS_THIS_WEEK boxes (9778, 9779); needs device confirmation


def test_supplement_info_client_clears_is_this_week_when_env_set(reqs, monkeypatch):
    monkeypatch.setenv("SUPPLY_CLEAR_WEEKLY_FLAGS", "1")
    raw = reqs.supplement_info()
    client = reqs.supplement_info_client()
    assert any(v.get("IS_THIS_WEEK") for v in raw.values())
    assert not any(v.get("IS_THIS_WEEK") for v in client.values())
    assert len(client) == len(raw)


def test_current_looks_supply_id_is_the_open_kind3_box(reqs):
    assert reqs.current_looks_supply_id() == 9546


def test_this_week_supply_id_is_the_lowest_flagged_box(reqs):
    flagged = sorted(s for s, v in reqs.supplement_info().items() if v.get("IS_THIS_WEEK"))
    assert flagged == [9778, 9779]
    assert reqs.this_week_supply_id() == THIS_WEEK


def test_weekly_push_is_recorded_and_echoed_for_the_empty_def_call(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "setHasAlreadyShowSupplyID", b"")
    assert reply
    assert recorder == [("onUpdateAlreadyShowSupplyID", struct.pack("<i", THIS_WEEK))]
    assert gw.load_accounts()["supply_push"] == {"id": THIS_WEEK}


def test_weekly_push_ignores_an_unexpected_int32_payload(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "setHasAlreadyShowSupplyID", struct.pack("<i", 12345))
    assert reply
    assert recorder == [("onUpdateAlreadyShowSupplyID", struct.pack("<i", THIS_WEEK))]
    assert gw.load_accounts()["supply_push"] == {"id": THIS_WEEK}


def test_month_push_is_recorded_without_a_reply(gw, udp, recorder):
    assert udp._athlete_request(ADDR, "setHasAlreadyShowMonthSupply", b"") == b""
    assert recorder == []
    assert gw.load_accounts()["supply_month_push"] == {"shown": True}


# ---- cache and monitor ------------------------------------------------------------------------

def test_query_uses_the_cached_catalogue_blob(gw, udp, recorder):
    udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    assert gw.supply_cache.build_count() == 1
    blob = gw.athlete_requests.py(gw.athlete_requests.supplement_info_client())
    assert [a for n, a in recorder if n == "onQueryAvailableSupplement"] == [blob, blob]


def test_dispatch_records_latency_and_reply_bytes_per_method(gw, udp):
    gw.perf_monitor.MONITOR.reset()
    reply = udp._dispatch_athlete(ADDR, "queryAvailableSupplement", b"")
    assert reply == udp._athlete_request(ADDR, "queryAvailableSupplement", b"")
    stats = gw.perf_monitor.MONITOR.summary()["Athlete.queryAvailableSupplement"]
    assert stats["count"] == 1 and stats["mean_bytes"] == len(reply) > 17000
    gw.perf_monitor.MONITOR.reset()


def test_truncated_draw_request_is_dropped_without_a_reply(gw, udp, recorder):
    """A request too short to hold box id + currency is logged and answered with nothing."""
    assert udp._athlete_request(ADDR, "openSupplyBox", struct.pack("<i", LOOKS)) == b""
    assert recorder == []
    assert read_blob(b"\x00") == (b"", 1)
