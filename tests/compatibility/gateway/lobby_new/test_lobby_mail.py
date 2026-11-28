"""Lobby mailbox: server/lobby_mail.py (Mailbox) and GateUDP._mail_reply, plus the delMails
client-pickle decode (server/client_pickle.py).

Wire shapes from extract Athlete.def (bwdefs): requestMails() -> onMailUpdate(PYTHON, PYTHON);
requestMailDetail(INT32) -> onLoadMailDetail(INT32, STRING, PYTHON) / onLoadMailDetailFailed(INT32);
getAwardFromMail(INT32) -> onGetAwardFromMail(PYTHON); deleteMail(INT32); delMails(PYTHON)."""

import os
import pickle
import struct

import pytest

from lobby_new_helpers import ADDR, args_of, blob, i32, names, read_blob, read_py

DAY = 86400


def _reply(udp, gw, name, args=b""):
    """GateUDP._mail_reply, the lobby_mail handler (see test_dispatch_* for what the client reaches)."""
    return udp._mail_reply(ADDR, name, gw.athlete_requests.Reader(args))


def _mail_list(recorder):
    mails, i = read_py(args_of(recorder, "onMailUpdate")[-1])
    top, j = read_py(args_of(recorder, "onMailUpdate")[-1], i)
    assert j == len(args_of(recorder, "onMailUpdate")[-1])
    return mails, top


# ---- Mailbox (module) --------------------------------------------------------------------------

def _box(gw, store, now=1_650_000_000):
    lm = gw.lobby_mail
    return lm.Mailbox(lambda: store.get("st"), lambda st: store.__setitem__("st", st), now)


def test_mailbox_list_newest_first_with_client_keys(gw):
    store = {}
    box = _box(gw, store)
    rows = box.mail_list()
    assert [r["mailID"] for r in rows] == [3, 2, 1]
    for r in rows:
        assert {"mailID", "type", "title", "sender", "when", "unread"} <= set(r)
        assert r["unread"] is True
    # "deadline" only on the expiring mail (the client shows "LEFT ..." whenever the key exists)
    assert "deadline" not in rows[1] and "deadline" not in rows[2]
    assert rows[0]["deadline"] == box.first_seen + 7 * DAY
    assert box.unread_count() == 3
    assert store["st"]["first_seen"] == box.first_seen          # first visit persisted


def test_mailbox_detail_marks_read_and_lists_props(gw):
    store = {}
    box = _box(gw, store)
    content, extra = box.detail(2)
    assert content == "gift" and extra == {"props": [[120901, 1], [250175, 2]]}
    assert 2 in store["st"]["read"]
    assert box.unread_count() == 2
    assert box.detail(99) is None


def test_mailbox_claim_once_second_claim_grants_nothing(gw):
    store = {}
    box = _box(gw, store)
    assert box.claim(2) == [[120901, 1], [250175, 2]]
    assert box.detail(2)[1] == {"props": []}                    # Get button hidden after the claim
    assert box.claim(2) == []                                   # 28.10: no second grant
    # a claim on a mail with nothing left removes it (Claim is the client's only button)
    assert 2 not in [r["mailID"] for r in box.mail_list()]
    # state survives a new Mailbox (relog) through the save/load callables
    again = _box(gw, store)
    assert again.claim(2) == []
    assert 2 in store["st"]["claimed"]


def test_mailbox_claim_of_text_mail_removes_it(gw):
    store = {}
    box = _box(gw, store)
    assert box.claim(1) == []
    assert [r["mailID"] for r in box.mail_list()] == [3, 2]


def test_mailbox_delete_keeps_unclaimed_props(gw):
    store = {}
    box = _box(gw, store)
    box.delete([1, 2])
    assert [r["mailID"] for r in box.mail_list()] == [3, 2]     # 2 still has props
    box.claim(2)
    box.delete([2])
    assert [r["mailID"] for r in box.mail_list()] == [3]


def test_mailbox_expired_mail_is_hidden(gw):
    store = {}
    _box(gw, store, now=1_650_000_000)                           # first_seen saved
    later = _box(gw, store, now=1_650_000_000 + 8 * DAY)        # 28.07: past deadline_days 7
    assert [r["mailID"] for r in later.mail_list()] == [2, 1]
    assert later.claim(3) == [] and later.detail(3) is None


def test_award_result_merges_counts_into_a_dict(gw):
    assert gw.lobby_mail.award_result([[5, 1], [5, 2], [7, 1]]) == {5: 3, 7: 1}


# ---- GateUDP._mail_reply (lobby_mail handler) ---------------------------------------------------

def test_mail_reply_list_detail_claim_delete(gw, udp, recorder):
    assert _reply(udp, gw, "requestMails")
    mails, top = _mail_list(recorder)
    assert [m["mailID"] for m in mails] == [3, 2, 1] and top == []

    recorder.clear()
    _reply(udp, gw, "requestMailDetail", i32(2))
    (args,) = args_of(recorder, "onLoadMailDetail")
    assert struct.unpack_from("<i", args)[0] == 2
    content, j = read_blob(args, 4)
    extra, k = read_py(args, j)
    assert content == b"gift" and extra == {"props": [[120901, 1], [250175, 2]]} and k == len(args)

    recorder.clear()
    _reply(udp, gw, "requestMailDetail", i32(42))
    assert recorder == [("onLoadMailDetailFailed", i32(42))]

    recorder.clear()
    reply = _reply(udp, gw, "getAwardFromMail", i32(2))
    assert reply
    (award,) = args_of(recorder, "onGetAwardFromMail")
    assert read_py(award)[0] == {120901: 1, 250175: 2}
    granted = [struct.unpack_from("<i", a)[0] for a in args_of(recorder, "onAddDtsAppearanceItem")]
    assert granted == [120901, 250175]

    recorder.clear()
    assert _reply(udp, gw, "getAwardFromMail", i32(2)) == b""   # second claim: nothing sent, nothing granted
    assert recorder == []

    recorder.clear()
    _reply(udp, gw, "deleteMail", i32(1))
    mails, _top = _mail_list(recorder)
    assert [m["mailID"] for m in mails] == [3]                  # 2 was emptied by the second claim


def test_mail_claim_saves_per_account_state(gw, udp, recorder):
    _reply(udp, gw, "getAwardFromMail", i32(2))
    key = "mail:" + str(gw.account_link.current_gid())
    assert 2 in gw.load_accounts()[key]["claimed"]


def test_del_mails_decodes_a_plain_id_list(gw, udp, recorder):
    _reply(udp, gw, "getAwardFromMail", i32(2))                 # claimed -> deletable
    recorder.clear()
    ids = blob(pickle.dumps([1, 2], protocol=2))
    _reply(udp, gw, "delMails", ids)
    mails, _top = _mail_list(recorder)
    assert [m["mailID"] for m in mails] == [3]


class _Boom:
    """Pickles to a call of os.system (REDUCE): pickle.loads would run it."""

    def __reduce__(self):
        return (os.system, ("echo pwned",))


@pytest.mark.parametrize("protocol", [0, 2])
def test_del_mails_refuses_a_malicious_pickle_and_runs_nothing(gw, udp, recorder, monkeypatch, protocol):
    payload = blob(pickle.dumps(_Boom(), protocol=protocol))     # built before os.system is replaced
    assert b"system" in payload                                 # the payload names a callable
    ran = []
    monkeypatch.setattr(os, "system", lambda *a: ran.append(a) or 0)
    _reply(udp, gw, "requestMails")                             # mailbox state exists (first_seen)
    recorder.clear()
    store_before = gw.load_accounts()
    assert _reply(udp, gw, "delMails", payload) == b""
    assert ran == []                                            # nothing executed
    assert recorder == []                                       # no reply sent
    assert gw.load_accounts() == store_before                   # no mail state written


def test_del_mails_refusal_through_athlete_request(gw, udp, recorder, monkeypatch):
    """Same payload through the real dispatcher (delMails reaches _mail_reply)."""
    payload = blob(pickle.dumps(_Boom(), protocol=2))
    ran = []
    monkeypatch.setattr(os, "system", lambda *a: ran.append(a) or 0)
    assert udp._athlete_request(ADDR, "delMails", payload) == b""
    assert ran == [] and recorder == []


def test_del_mails_ignores_non_int_entries(gw, udp, recorder):
    _reply(udp, gw, "delMails", blob(pickle.dumps(["1", None, True, 1.0, {"x": 1}], protocol=2)))
    mails, _top = _mail_list(recorder)
    assert [m["mailID"] for m in mails] == [3, 2, 1]            # nothing deleted


def test_client_pickle_refuses_oversize(gw):
    cp = gw.client_pickle
    with pytest.raises(pickle.UnpicklingError):
        cp.loads_plain(b"\x80\x02" + b"N" * (cp.MAX_BYTES + 1))


# ---- what the client actually reaches -----------------------------------------------------------

def test_dispatch_not_linked_uses_the_local_lobby_mail_box(gw, udp, recorder):
    """Not linked: requestMails is answered by lobby_mail (lobby_mail.json), newest first."""
    udp._athlete_request(ADDR, "requestMails", b"")
    mails, top = _mail_list(recorder)
    assert [m["mailID"] for m in mails] == [3, 2, 1] and top == []


def test_dispatch_local_mail_off_keeps_an_empty_mailbox(gw, udp, recorder, monkeypatch):
    monkeypatch.setenv("LOCAL_MAIL", "off")
    udp._athlete_request(ADDR, "requestMails", b"")
    mails, top = _mail_list(recorder)
    assert mails == [] and top == []


def test_dispatch_linked_uses_ros_server_for_every_mail_request(gw, udp, recorder, monkeypatch):
    """Linked: all five mail requests, delMails included, go to RoS_Server; lobby_mail is not used."""
    calls = []
    gw.account_link._current = {"external_uid": "9879120763", "gid": 1}
    monkeypatch.setattr(gw.account_link, "list_mails", lambda: calls.append("list") or [], raising=False)
    monkeypatch.setattr(gw.account_link, "delete_mail", lambda mid: calls.append(("delete", mid)) or True,
                        raising=False)
    monkeypatch.setattr(gw.lobby_mail, "Mailbox", None)               # any lobby_mail use would raise
    udp._athlete_request(ADDR, "requestMails", b"")
    udp._athlete_request(ADDR, "delMails", blob(pickle.dumps([4, 9], protocol=2)))
    assert calls == ["list", ("delete", 4), ("delete", 9), "list"]
    evil = blob(pickle.dumps(_Boom(), protocol=2))                  # built before os.system is replaced
    ran = []
    monkeypatch.setattr(os, "system", lambda cmd: ran.append(cmd) or 0)
    assert udp._athlete_request(ADDR, "delMails", evil) == b""
    assert ran == [] and calls == ["list", ("delete", 4), ("delete", 9), "list"]


def test_dispatch_del_mails_reply_matches_request_mails(gw, udp, recorder):
    udp._athlete_request(ADDR, "requestMails", b"")
    listed, _ = _mail_list(recorder)
    recorder.clear()
    udp._athlete_request(ADDR, "delMails", blob(pickle.dumps([], protocol=2)))   # deletes nothing
    after, _ = _mail_list(recorder)
    assert [m["mailID"] for m in after] == [m["mailID"] for m in listed]
