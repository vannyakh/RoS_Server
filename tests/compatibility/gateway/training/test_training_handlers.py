"""Brave Book + Spec Train (Special Distinction) Athlete handlers."""

import pickle
import struct

from supply_helpers import ADDR, read_py


def names(calls):
    return [n for n, _ in calls]


def test_open_spec_train_main_replies(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "openSpecTrainRewardMain", b"")
    assert reply
    assert "onSyncSpecTrainRewardMain" in names(recorder)


def test_brave_book_update_tasks(gw, udp, recorder):
    reply = udp._athlete_request(ADDR, "requestUpdatingBraveBookTask", b"")
    assert reply
    assert recorder[-1][0] == "_OnBraveBookTaskDataChanged"
    tasks, i = read_py(recorder[-1][1])
    assert isinstance(tasks, list) and len(tasks) >= 1


def test_buy_special_pass_unlocks(gw, udp, recorder):
    pass_special = gw.training_event.PASS_SPECIAL
    reply = udp._athlete_request(
        ADDR,
        "requestBuyingBraveBookPass",
        struct.pack("<ii", pass_special, 0),
    )
    assert reply
    assert "_OnRequestBuyingBraveBookPassFinished" in names(recorder)
    finished = next(args for name, args in recorder if name == "_OnRequestBuyingBraveBookPassFinished")
    code, pass_type, _extra = struct.unpack_from("<iii", finished)
    assert code == 0 and pass_type == pass_special
    data_args = next(args for name, args in recorder if name == "_OnBraveBookDataChanged")
    season, level, exp = struct.unpack_from("<iii", data_args)
    assert season == 21 and level == 1
    _tail = data_args[12:]
    n = _tail[0]
    i = 1
    if n == 0xFF:
        n = int.from_bytes(_tail[i : i + 3], "little")
        i += 3
    pass_states = pickle.loads(_tail[i : i + n])
    assert pass_states.get(pass_special) is True


def test_brave_book_encode_roundtrip(gw):
    encode = gw.training_event.encode_brave_book_data
    raw = encode(
        {"seasonID": 21, "level": 2, "experience": 50, "passStates": {0: True, 1: False}, "receivedRewards": {}}
    )
    season, level, exp = struct.unpack_from("<iii", raw)
    assert (season, level, exp) == (21, 2, 50)