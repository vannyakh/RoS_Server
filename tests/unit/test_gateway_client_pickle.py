"""bigworld_gateway/server/client_pickle.py: client PYTHON args decode without running code."""

import os
import pickle
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[2] / "bigworld_gateway" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import client_pickle  # noqa: E402


class _Boom:
    def __reduce__(self):
        return (os.system, ("echo pwned",))


def test_plain_list_of_ids_decodes():
    assert client_pickle.int_list(pickle.dumps([3, 5, 9], protocol=2)) == [3, 5, 9]
    assert client_pickle.int_list(pickle.dumps((1, "x", True, 2), protocol=2)) == [1, 2]
    assert client_pickle.int_list(pickle.dumps({"a": 1}, protocol=2)) == []


def test_plain_values_round_trip():
    # No bytes: Python 3 pickles bytes at protocol 2 through _codecs.encode (a global, refused).
    # The client (Python 2) sends str as SHORT_BINSTRING, which needs no global.
    value = {"ids": [1, 2], "name": "Raven", "ok": True, "f": 1.5, "n": None}
    assert client_pickle.loads_plain(pickle.dumps(value, protocol=2)) == value


@pytest.mark.parametrize("protocol", [0, 2, pickle.HIGHEST_PROTOCOL])
def test_callable_payload_is_refused(protocol):
    data = pickle.dumps(_Boom(), protocol=protocol)
    with pytest.raises(pickle.UnpicklingError, match="refused global"):
        client_pickle.loads_plain(data)


def test_garbage_and_oversize_are_refused():
    with pytest.raises(pickle.UnpicklingError):
        client_pickle.loads_plain(b"\x80\x02]q\x00(K\x01")        # truncated
    with pytest.raises(pickle.UnpicklingError, match="too large"):
        client_pickle.loads_plain(b"\x00" * (client_pickle.MAX_BYTES + 1))
