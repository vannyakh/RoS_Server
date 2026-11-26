"""Two original clients behind one IP keep their own login key, account and sequence numbers."""

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def gw(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    module = importlib.import_module("ros_server")
    module = importlib.reload(module)
    module._SESSIONS.clear()
    module._ACTIVE = None
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


def _login(gw, uid, bf):
    """What the login handler does after a Mercury login for `uid`."""
    gw._stash()
    gw.account_link._login_uid = uid
    gw.account_link._current = {"external_uid": uid}
    return gw._new_session(bf, b"\x44\x33\x22\x11")


def _udp(gw):
    return gw.GateUDP(25000)


REQ = b"\x01\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b"


def test_second_login_does_not_replace_first_players_state(gw):
    a = _login(gw, "9000000001", b"\xaa\xaa\xaa\xaa")
    b = _login(gw, "9000000002", b"\xbb\xbb\xbb\xbb")
    udp = _udp(gw)

    udp._select_session(("1.1.1.1", 1111), REQ)       # first BaseApp login -> newest free login
    first = udp._sess[("1.1.1.1", 1111)]
    udp._select_session(("1.1.1.1", 2222), REQ)
    second = udp._sess[("1.1.1.1", 2222)]

    assert {first["login_uid"], second["login_uid"]} == {"9000000001", "9000000002"}
    assert first is not second

    udp._select_session(("1.1.1.1", 1111), b"\x00" * 16)
    assert gw.account_link._login_uid == first["login_uid"]
    assert gw.CURRENT_BF_KEY == first["bf"]
    udp._select_session(("1.1.1.1", 2222), b"\x00" * 16)
    assert gw.account_link._login_uid == second["login_uid"]
    assert gw.CURRENT_BF_KEY == second["bf"]
    assert {a["bf"], b["bf"]} == {first["bf"], second["bf"]}


def test_state_changes_follow_their_player(gw):
    _login(gw, "9000000001", b"\xaa\xaa\xaa\xaa")
    _login(gw, "9000000002", b"\xbb\xbb\xbb\xbb")
    udp = _udp(gw)
    udp._select_session(("h", 1), REQ)
    gw.LOGIN_STATE = {"yuanbao": 111}
    udp._select_session(("h", 2), REQ)
    gw.LOGIN_STATE = {"yuanbao": 222}
    udp._select_session(("h", 1), b"\x00" * 16)
    assert gw.LOGIN_STATE == {"yuanbao": 111}
    udp._select_session(("h", 2), b"\x00" * 16)
    assert gw.LOGIN_STATE == {"yuanbao": 222}


def test_single_player_retransmitted_login_keeps_its_session(gw):
    only = _login(gw, "9000000001", b"\xaa\xaa\xaa\xaa")
    udp = _udp(gw)
    udp._select_session(("h", 1), REQ)
    udp._select_session(("h", 1), REQ)                # no reply seen yet: the client repeats
    assert udp._sess[("h", 1)] is only


def test_server_sequence_numbers_are_per_player(gw):
    udp = _udp(gw)
    udp._seq[("h", 1)] = 7
    assert udp._seq.get(("h", 2), 0) == 0


def test_wrong_key_is_not_accepted_as_valid_plaintext(gw):
    import loginapp

    good = b"\x0c\x00" + b"\x00" * 5 + b"\x01"       # flags 0x000c, padded, wastage 1
    encrypted = loginapp.custom_bf_encrypt(b"\xaa\xaa\xaa\xaa", good)
    assert gw._bf_plain_ok(loginapp.custom_bf_decrypt(b"\xaa\xaa\xaa\xaa", encrypted))
    assert not gw._bf_plain_ok(loginapp.custom_bf_decrypt(b"\xbb\xbb\xbb\xbb", encrypted))
