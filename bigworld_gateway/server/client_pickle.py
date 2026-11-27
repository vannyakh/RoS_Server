"""Decode PYTHON-typed method arguments sent by the client, without running code.

The client encodes PYTHON arguments with pickle (protocol 2). pickle.loads on bytes from the
network runs any callable the sender names, so a crafted packet to the gate could execute code
on this server. loads_plain only accepts plain data (None, bool, int, float, str, bytes, list,
tuple, dict, set): every class or function reference is refused.
"""

from __future__ import annotations

import io
import pickle

MAX_BYTES = 64 * 1024


class _PlainUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"refused global {module}.{name} in client data")


def loads_plain(data: bytes):
    """Plain Python value from client pickle bytes. Raises pickle.UnpicklingError when the data
    names a class or function, is too large, or is not a valid pickle."""
    if len(data) > MAX_BYTES:
        raise pickle.UnpicklingError(f"client pickle too large ({len(data)} bytes)")
    try:
        return _PlainUnpickler(io.BytesIO(data)).load()
    except pickle.UnpicklingError:
        raise
    except Exception as e:  # truncated / malformed data
        raise pickle.UnpicklingError(f"bad client pickle: {e!r}") from e


def int_list(data: bytes) -> list[int]:
    """Client list/tuple/set of ints (e.g. delMails mail ids). Non-int entries are dropped."""
    value = loads_plain(data)
    if not isinstance(value, (list, tuple, set)):
        return []
    return [v for v in value if isinstance(v, int) and not isinstance(v, bool)]
