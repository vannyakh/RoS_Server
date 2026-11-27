"""Mail PYTHON argument builders (ros_server.mail_*): client dict keys, the extraInfo shape
(unverified in game: list of [propID, cnt]) and the protocol 2 pickle round trip."""

import pickle

import pytest

import ros_server as gw
import athlete_requests

MAIL = {"mail_id": 7, "type": 1, "title": "Welcome", "sender": "RoS", "abstract": "A gift",
        "sent_at": 1795000000, "deadline": 1796000000, "unread": True, "claimed": False,
        "attachments": [{"prop_id": 200027, "number": 2}, {"prop_id": 203011, "number": 1}], "gold": 0}


def _unblob(b):
    """Inverse of _bw_blob: (payload, rest)."""
    if b[0] == 0xFF:
        n = int.from_bytes(b[1:4], "little")
        return b[4:4 + n], b[4 + n:]
    return b[1:1 + b[0]], b[1 + b[0]:]


def test_mail_list_entry_has_the_client_keys():
    assert gw.mail_list_entry(MAIL) == {
        "mailID": 7, "type": 1, "unread": True, "title": "Welcome", "when": 1795000000,
        "deadline": 1796000000, "mail_abstract": "A gift", "sender": "RoS"}


def test_mail_list_entry_defaults():
    e = gw.mail_list_entry({"mail_id": "3"})
    assert e == {"mailID": 3, "type": 0, "unread": False, "title": "", "when": 0, "deadline": 0,
                 "mail_abstract": "", "sender": ""}


def test_extra_info_lists_prop_count_pairs_and_caps_at_six():
    assert gw.mail_extra_info(MAIL) == {"props": [[200027, 2], [203011, 1]], "unread": False}
    many = dict(MAIL, attachments=[{"prop_id": 100 + i, "number": 1} for i in range(9)])
    assert len(gw.mail_extra_info(many)["props"]) == 6


def test_extra_info_of_claimed_mail_has_no_props():
    assert gw.mail_extra_info(dict(MAIL, claimed=True)) == {"props": [], "unread": False}


def test_gold_is_named_in_content_not_in_props():
    d = dict(MAIL, attachments=[], gold=500, content="Thanks")
    assert gw.mail_extra_info(d)["props"] == []
    assert gw.mail_content(d) == "Thanks\n\nGold x500"
    assert gw.mail_content(dict(d, claimed=True)) == "Thanks"
    assert gw.mail_content(dict(d, content="")) == "Gold x500"


def test_award_ids_repeat_per_copy():
    assert gw.mail_award_ids([{"prop_id": 5, "number": 3}, {"prop_id": 6, "number": 1}]) == [5, 5, 5, 6]
    assert gw.mail_award_ids(None) == []


@pytest.mark.parametrize("obj", [
    [gw.mail_list_entry(MAIL)],
    gw.mail_extra_info(MAIL),
    [200027, 200027, 203011],
    [],
])
def test_pickle_protocol_2_round_trip(obj):
    blob = athlete_requests.py(obj)
    payload, rest = _unblob(blob)
    assert rest == b""
    assert payload[:2] == b"\x80\x02"           # protocol 2 header (Python 2 client)
    assert pickle.loads(payload) == obj
