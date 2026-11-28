"""server/social.py: search, request, accept, refuse, remove and lists between two online players."""

import pickle
import struct
import time

import pytest

import athlete_requests
import social

A, B = 111, 222
ADDR = {A: ("10.0.0.1", 1), B: ("10.0.0.1", 2)}


class Gate:
    def __init__(self):
        now = time.time()
        self._last_recv = {a: now for a in ADDR.values()}
        self._last_bf = {a: b"k" for a in ADDR.values()}
        self._last_client_seq, self._in_battle, self.sent = {}, {}, []

    def _send_bundle(self, addr, body, seq, bf_key):
        self.sent.append((addr, body))


def call(method, args):
    return b"<%s>" % method.encode() + args


@pytest.fixture
def gate(tmp_path, monkeypatch):
    monkeypatch.setattr(social, "STORE", str(tmp_path / "social.json"))
    social.ONLINE.clear()
    return Gate()


def ask(gate, gid, name, args=b""):
    me = {"gid": gid, "nickname": {A: "Alpha", B: "Bravo"}[gid], "characterType": 20001,
          "nationalFlag": "", "portrait": ""}
    return social.handle(gate, ADDR[gid], name, athlete_requests.Reader(args), me, call)


def gid_arg(gid):
    return struct.pack("<Q", gid)


def friend_list(gate, gid, kind=2):
    return ask(gate, gid, "getFriendList", struct.pack("<b", kind))


def request_a_to_b(gate):
    friend_list(gate, A), friend_list(gate, B)
    return ask(gate, A, "requestFriend", gid_arg(B) + struct.pack("<ib", 10001, 3))


def test_abstract_has_the_alias_fields_in_order(gate):
    """FIXED_DICT FRIEND_ABSTRACT from the client's alias.xml, decoded field by field."""
    import bwdefs

    friend_list(gate, A)
    data = social.abstract(A)
    fields = bwdefs.Defs().resolve("FRIEND_ABSTRACT")[1]
    pos, values = 0, {}
    sizes = {"INT32": "<i", "UINT32": "<I", "UINT64": "<Q", "INT8": "<b"}
    for name, kind, _default in fields:
        if kind[0] == "STRING":
            n = data[pos]
            values[name] = data[pos + 1:pos + 1 + n].decode()
            pos += 1 + n
        else:
            values[name] = struct.unpack_from(sizes[kind[0]], data, pos)[0]
            pos += struct.calcsize(sizes[kind[0]])
    assert pos == len(data)
    assert (values["gid"], values["nickname"], values["serverID"], values["characterType"]) == (A, "Alpha", 10001, 20001)


def test_search_finds_the_other_player_but_not_yourself(gate):
    friend_list(gate, A), friend_list(gate, B)
    reply = ask(gate, A, "searchPlayerByName", athlete_requests.blob("a"))     # "a" is in both names
    assert reply.startswith(b"<onSearchPlayerByName>" + struct.pack("<I", 1))
    assert b"Bravo" in reply and b"Alpha" not in reply


def test_request_reaches_the_online_player_and_is_listed(gate):
    reply = request_a_to_b(gate)
    assert reply == b"<onRequestFriendAck>" + bytes([3]) + gid_arg(B)
    assert gate.sent == [(ADDR[B], b"<onGetRequest>" + social.abstract(A))]
    listed = friend_list(gate, B, 5)
    assert listed.startswith(b"<onGetFriendList>" + bytes([5]) + struct.pack("<I", 1))


def test_accept_makes_both_friends_and_tells_both(gate):
    request_a_to_b(gate)
    gate.sent.clear()
    reply = ask(gate, B, "acceptFriend", gid_arg(A))
    assert reply.startswith(b"<onRemoveRequest>" + gid_arg(A)) and b"<onUpdateFriend>" in reply
    assert gate.sent == [(ADDR[A], b"<onUpdateFriend>" + social.abstract(B) + b"\x01")]
    for me, other in ((A, B), (B, A)):
        listed = friend_list(gate, me)
        assert listed.startswith(b"<onGetFriendList>\x02" + struct.pack("<I", 1) + social.abstract(other))
        assert pickle.loads(listed[listed.index(b"\x80\x02"):]) == {other: (social.IDLE, False)}
    assert friend_list(gate, B, 5).startswith(b"<onGetFriendList>\x05" + struct.pack("<I", 0))


def test_accept_without_a_request_does_nothing(gate):
    friend_list(gate, A), friend_list(gate, B)
    assert ask(gate, B, "acceptFriend", gid_arg(A)) == b""
    assert friend_list(gate, B).startswith(b"<onGetFriendList>\x02" + struct.pack("<I", 0))


def test_refuse_and_remove(gate):
    request_a_to_b(gate)
    assert ask(gate, B, "refuseFriend", gid_arg(A)) == b"<onRemoveRequest>" + gid_arg(A)
    request_a_to_b(gate)
    ask(gate, B, "acceptFriend", gid_arg(A))
    gate.sent.clear()
    assert ask(gate, A, "removeFriend", gid_arg(B)) == b"<onRemoveFriend>" + gid_arg(B)
    assert gate.sent == [(ADDR[B], b"<onRemoveFriend>" + gid_arg(A))]
    assert friend_list(gate, B).startswith(b"<onGetFriendList>\x02" + struct.pack("<I", 0))


def test_nothing_is_pushed_into_a_match_and_status_shows_it(gate):
    request_a_to_b(gate)
    ask(gate, B, "acceptFriend", gid_arg(A))
    gate._in_battle[ADDR[B]] = True
    gate.sent.clear()
    reply = ask(gate, A, "requestFriendOnlineStatus", struct.pack("<i", 2))
    assert pickle.loads(reply[reply.index(b"\x80\x02"):]) == {B: (social.GAMING, False)}
    assert social.push(gate, B, b"x") is False and gate.sent == []
    gate._last_recv[ADDR[B]] = time.time() - social.ONLINE_SECS - 1
    assert social.status(gate, B) == social.OFFLINE


def test_adding_yourself_or_a_stranger_gid_is_ignored(gate):
    friend_list(gate, A)
    assert ask(gate, A, "requestFriend", gid_arg(A) + struct.pack("<ib", 10001, 3)) == b""
    ask(gate, A, "requestFriend", gid_arg(999) + struct.pack("<ib", 10001, 3))
    assert gate.sent == []


def test_every_friend_has_a_status_pair_even_when_offline(gate):
    """UIMainBattleGroundInvite._filter_friend does statuses[gid] and unpacks (status, inTeam)."""
    request_a_to_b(gate)
    ask(gate, B, "acceptFriend", gid_arg(A))
    gate._last_recv[ADDR[B]] = time.time() - social.ONLINE_SECS - 1
    listed = friend_list(gate, A)
    assert pickle.loads(listed[listed.index(b"\x80\x02"):]) == {B: (social.OFFLINE, False)}


def test_online_players_tab(gate):
    friend_list(gate, A), friend_list(gate, B)
    reply = ask(gate, A, "requestRandomOnlinePlayers")
    assert reply.startswith(b"<onGetRandomOnlinePlayers>" + struct.pack("<I", 1) + social.abstract(B))
    assert pickle.loads(reply[reply.rindex(b"\x80\x02"):]) == {B: (social.IDLE, False)}
