"""client/patch_tools/patch_month_supplement.py on a hand-built NeoX-marshalled module (no game files)."""

import importlib.util
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "client" / "patch_tools"


def _load():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("patch_month", TOOLS / "patch_month_supplement.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_bytes(xs):
    def string(value):
        return b"s" + struct.pack("<i", len(value)) + xs(value)

    def tup(*items):
        return b"(" + struct.pack("<i", len(items)) + b"".join(items)

    def code(co, consts, names, varnames, name):
        return (b"c" + struct.pack("<4i", 0, len(varnames), 4, 0x43) + string(co) + tup(*consts)
                + tup(*map(string, names)) + tup(*map(string, varnames)) + tup() + tup()
                + string(b"common/supplement_utils.py") + string(name)
                + struct.pack("<i", 1) + string(b""))

    body = bytes.fromhex("9b0000" "600000" "830000" "680000" "650000" "4a")
    func = code(body, [b"N", string(b"%Y")], [b"time"], [b"curTime"], b"getCurrentMonthSupplementID")
    # a twin with the same bytecode comes first, as in the real module
    twin = code(body, [b"N", string(b"%Y")], [b"time"], [b"curTime"], b"getOtherSupplementID")
    return code(b"N", [twin, func], [], [], b"<module>"), body


def test_time_call_becomes_a_constant_of_the_same_length():
    patch = _load()
    from neox_marshal import Reader, xs

    data, body = _module_bytes(xs)
    out = patch.patch_module(data, 1650456000.0)
    fn = [c for c in Reader(out).obj().walk() if c.name == b"getCurrentMonthSupplementID"][0]
    assert fn.consts[:2] == (None, b"%Y") and len(fn.consts) == 3
    assert patch.decode_float(fn.consts[2]) == 1650456000.0
    assert len(fn.code) == len(body)
    # LOAD_CONST 2, two JUMP_FORWARD 0, then the untouched rest (STORE_FAST curTime ...)
    assert fn.code[:9] == bytes.fromhex("650200" "840000" "840000")
    assert fn.code[9:] == body[9:]
    assert fn.names == (b"time",) and fn.varnames == (b"curTime",)
    twin = [c for c in Reader(out).obj().walk() if c.name == b"getOtherSupplementID"][0]
    assert twin.code == body and len(twin.consts) == 2           # only the named function changes


def test_float_encoding_matches_what_the_client_loaded():
    """Device: the unscrambled bytes of 1650456000.0 were loaded as 1717041616.0784929."""
    patch = _load()
    import struct as st

    assert abs(patch.decode_float(1650456000.0) - 1717041616.0784929) < 1e-3
    assert patch.encode_float(1650456000.0) != b"g" + st.pack("<d", 1650456000.0)
