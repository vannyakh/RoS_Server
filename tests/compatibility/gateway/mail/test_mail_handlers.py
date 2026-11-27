"""GateUDP mail requests (requestMails, requestMailDetail, getAwardFromMail, deleteMail) and the
avatar frame (equipAppearance / unloadAppearance of a HeadFrameAppearanceType prop) with a fake
account_link."""

import importlib
import json
import struct
import sys

import pytest

ADDR = ("10.0.0.3", 5001)
FRAME = 2990236          # HeadFrameAppearanceType (extract/hall_props.json)
PROP_A, PROP_B = 200027, 203011


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.reload(importlib.import_module("ros_server"))
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = None
    module.account_link._current = None
    monkeypatch.setattr(module.os, "urandom", lambda n: b"\x00" * n)   # deterministic package uuids
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


class Recorder:
    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


def _link(gw, monkeypatch, gold=1000, **fns):
    gw.account_link._current = {"external_uid": "9879120763", "gid": 1}
    gw.LOGIN_STATE = {"yuanbao": 0, "items": [{"prop_id": PROP_A, "number": 1}],
                      "currencies": {"1": gold}, "outfit": {}}
    for name, fn in fns.items():
        monkeypatch.setattr(gw.account_link, name, fn, raising=False)


def _award(gw, ids):
    return gw.athlete_method("onGetAwardFromMail", gw.athlete_requests.py(ids))


def _mail(mid, when, unread=True):
    return {"mail_id": mid, "type": 1, "title": f"t{mid}", "sender": "RoS", "abstract": "a",
            "sent_at": when, "deadline": 0, "unread": unread, "claimed": False, "attachments": [], "gold": 0}


# ---- list / detail / delete -------------------------------------------------------------

def test_request_mails_sends_entries_oldest_first_and_empty_top_mails(gw, monkeypatch):
    _link(gw, monkeypatch, list_mails=Recorder([_mail(2, 200), _mail(1, 100, unread=False)]))
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "requestMails", b"")
    entries = [gw.mail_list_entry(_mail(1, 100, unread=False)), gw.mail_list_entry(_mail(2, 200))]
    py = gw.athlete_requests.py
    assert reply == gw.athlete_method("onMailUpdate", py(entries) + py([]))


def test_request_mails_not_linked_sends_empty_list(gw):
    udp = gw.GateUDP(25000)
    py = gw.athlete_requests.py
    assert udp._athlete_request(ADDR, "requestMails", b"") == gw.athlete_method("onMailUpdate", py([]) + py([]))


def test_mail_detail_ok_and_failed(gw, monkeypatch):
    detail = dict(_mail(7, 100), content="Hello", attachments=[{"prop_id": PROP_B, "number": 2}])
    rec = Recorder(detail)
    _link(gw, monkeypatch, mail_detail=rec)
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "requestMailDetail", struct.pack("<i", 7))
    assert rec.calls == [(7,)]
    assert reply == gw.athlete_method("onLoadMailDetail", struct.pack("<i", 7) + gw._bw_blob(b"Hello")
                                      + gw.athlete_requests.py({"props": [[PROP_B, 2]], "unread": False}))
    rec.result = {"_error": 404}
    assert udp._athlete_request(ADDR, "requestMailDetail", struct.pack("<i", 8)) == \
        gw.athlete_method("onLoadMailDetailFailed", struct.pack("<i", 8))


def test_delete_mail_sends_fresh_list(gw, monkeypatch):
    deleted = Recorder(True)
    _link(gw, monkeypatch, delete_mail=deleted, list_mails=Recorder([]))
    udp = gw.GateUDP(25000)
    py = gw.athlete_requests.py
    reply = udp._athlete_request(ADDR, "deleteMail", struct.pack("<i", 9))
    assert deleted.calls == [(9,)]
    assert reply == gw.athlete_method("onMailUpdate", py([]) + py([]))


# ---- claim ------------------------------------------------------------------------------

def test_claim_success_applies_counts_gold_and_pushes_copies(gw, monkeypatch):
    claim = Recorder({"props": [{"prop_id": PROP_A, "number": 2}, {"prop_id": PROP_B, "number": 1}],
                      "gold": 250, "items": [{"prop_id": PROP_A, "number": 3}, {"prop_id": PROP_B, "number": 1}],
                      "currencies": {"1": 1250}, "replayed": False})
    _link(gw, monkeypatch, claim_mail=claim)
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 11))
    assert claim.calls == [(11,)]
    copies = [PROP_A, PROP_A, PROP_B]
    # one onAddDtsAppearanceItem per copy (force=True), then the Recent tab update
    assert reply.startswith(udp._grant_props(copies, force=True, addr=None))
    assert udp._recent_got[ADDR][:2] == [PROP_A, PROP_B]
    assert gw.athlete_method("onCurrencyUpdated", struct.pack("<iqi", 1, 1250, 0)) in reply
    assert reply.endswith(_award(gw, copies))
    assert udp._counts(ADDR) == {PROP_A: 3, PROP_B: 1}
    assert udp._session_wallet(ADDR).balances[1] == 1250
    assert {PROP_A, PROP_B} <= udp._owned(ADDR)


def test_claim_without_gold_sends_no_currency_update(gw, monkeypatch):
    claim = Recorder({"props": [{"prop_id": PROP_B, "number": 1}], "gold": 0,
                      "items": [{"prop_id": PROP_B, "number": 1}], "currencies": {"1": 1000}, "replayed": False})
    _link(gw, monkeypatch, claim_mail=claim)
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 12))
    assert gw.athlete_method("onCurrencyUpdated", struct.pack("<iqi", 1, 1000, 0)) not in reply
    assert reply.endswith(_award(gw, [PROP_B]))


@pytest.mark.parametrize("result", [
    {"props": [{"prop_id": PROP_B, "number": 1}], "gold": 0, "items": [{"prop_id": PROP_B, "number": 1}],
     "currencies": {"1": 1000}, "replayed": True},
    {"_error": 404},
    {"_error": 409},
    None,                                     # RoS_Server down
])
def test_claim_replay_refusal_or_down_sends_empty_and_changes_nothing(gw, monkeypatch, result):
    _link(gw, monkeypatch, claim_mail=Recorder(result))
    udp = gw.GateUDP(25000)
    assert udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 13)) == _award(gw, [])
    assert udp._counts(ADDR) == {PROP_A: 1}
    assert udp._session_wallet(ADDR).balances[1] == 1000


def test_claim_not_linked_or_unsupported_sends_empty(gw, monkeypatch):
    udp = gw.GateUDP(25000)
    assert udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 14)) == _award(gw, [])
    gw.account_link._current = {"external_uid": "x", "gid": 1}
    monkeypatch.delattr(gw.account_link, "claim_mail", raising=False)
    assert udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 14)) == _award(gw, [])


def test_claim_in_flight_guard(gw, monkeypatch):
    claim = Recorder({"props": [], "gold": 0, "items": [], "currencies": {}, "replayed": False})
    _link(gw, monkeypatch, claim_mail=claim)
    udp = gw.GateUDP(25000)
    udp.__dict__.setdefault("_mail_busy", set()).add(ADDR)
    assert udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 15)) == _award(gw, [])
    assert claim.calls == []
    udp._mail_busy.discard(ADDR)
    udp._athlete_request(ADDR, "getAwardFromMail", struct.pack("<i", 15))
    assert claim.calls == [(15,)] and ADDR not in udp._mail_busy


# ---- avatar frame -----------------------------------------------------------------------

def test_frame_type_is_head_frame():
    import athlete_requests
    assert athlete_requests.appearance_type(FRAME) == "HeadFrameAppearanceType"


def test_equip_frame_linked_saves_and_replies(gw, monkeypatch):
    setter = Recorder({"external_uid": "9879120763", "gid": 1})
    _link(gw, monkeypatch, set_head_frame=setter)
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "equipAppearance", struct.pack("<i", FRAME))
    assert setter.calls == [(FRAME,)]
    assert reply == (gw.athlete_method("onUpdateHeadFrameTag", struct.pack("<i", FRAME)) +
                     gw.athlete_method("onNotifyEquipedAppearance", struct.pack("<i", FRAME)))
    assert gw.LOGIN_STATE["head_frame"] == FRAME
    # unload of the worn frame -> 0
    reply = udp._athlete_request(ADDR, "unloadAppearance", struct.pack("<i", FRAME))
    assert setter.calls[-1] == (0,)
    assert reply == (gw.athlete_method("onUpdateHeadFrameTag", struct.pack("<i", 0)) +
                     gw.athlete_method("onNotifyUnloadAppearance", struct.pack("<i", FRAME)))
    assert gw.LOGIN_STATE["head_frame"] == 0


def test_unload_of_another_frame_keeps_the_worn_one(gw, monkeypatch):
    setter = Recorder({"external_uid": "9879120763"})
    _link(gw, monkeypatch, set_head_frame=setter)
    gw.LOGIN_STATE["head_frame"] = FRAME
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "unloadAppearance", struct.pack("<i", 2990238))
    assert setter.calls == []
    assert reply == gw.athlete_method("onNotifyUnloadAppearance", struct.pack("<i", 2990238))


def test_equip_frame_local_mode_kept_for_relog(gw, monkeypatch):
    gw.LOGIN_STATE = gw.local_state()
    udp = gw.GateUDP(25000)
    udp._athlete_request(ADDR, "equipAppearance", struct.pack("<i", FRAME))
    assert gw.LOGIN_STATE["head_frame"] == FRAME
    with open(gw.ACCOUNTS_FILE, encoding="utf-8") as f:
        assert json.load(f)[gw._local_head_frame_key()] == FRAME
    assert gw.get_local_head_frame() == FRAME


def test_equip_frame_ros_server_down_still_replies(gw, monkeypatch):
    _link(gw, monkeypatch, set_head_frame=Recorder(None))
    udp = gw.GateUDP(25000)
    reply = udp._athlete_request(ADDR, "equipAppearance", struct.pack("<i", FRAME))
    assert reply.startswith(gw.athlete_method("onUpdateHeadFrameTag", struct.pack("<i", FRAME)))
    assert gw.get_local_head_frame() == FRAME
