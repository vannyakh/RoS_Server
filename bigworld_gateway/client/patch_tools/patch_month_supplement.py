"""Make the monthly Supreme Supply page work on a device whose clock is after 2022.

    python patch_month_supplement.py <script.npk> <out dir> [--key neox_rotor_key.txt] [--date "2022-04-20 12:00:00"]

common/supplement_utils.getCurrentMonthSupplementID starts with ``curTime = time.time()`` and picks the
monthly box whose dates contain it. The client's boxes end 2022-12-30, so on a later device clock it
returns None and UIMonthlySupplyPackage.Awake crashes (AttributeError ExtraGiftParam, black page).
The server cannot change this: the function reads the device clock, not the server time.

Patch: the 9 bytes of ``time.time()`` become LOAD_CONST <date> followed by two ``JUMP_FORWARD 0``
(no-ops), so the length and every jump target stay the same. NeoX-remapped opcodes: LOAD_CONST 0x65,
JUMP_FORWARD 0x84, STORE_FAST 0x68. The date should match the gateway's GAME_DATE.
Output: <out dir>/common/supplement_utils.nxs, a loose override for the device's
files/netease/h45na/script/ folder. Undo: delete that file. No game files go into the repository.
"""
import argparse
import calendar
import os
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neox_marshal import Reader, xs  # noqa: E402

FUNC = b"getCurrentMonthSupplementID"
MODULE = "common/supplement_utils.py"
LOAD_CONST, JUMP_FORWARD, STORE_FAST = 0x65, 0x84, 0x68
NOP = bytes([JUMP_FORWARD, 0, 0])


def encode_float(value):
    """NeoX marshal scrambles a binary float's 8 bytes like its strings (seen on device: a plain
    1650456000.0 was loaded as 1717041616.08)."""
    return b"g" + xs(struct.pack("<d", value))


def decode_float(value):
    """The real value of a float that the plain Reader returned still scrambled."""
    return struct.unpack("<d", xs(struct.pack("<d", value)))[0]


def patch_module(code, stamp):
    """The marshalled module with FUNC's ``time.time()`` replaced by the constant `stamp`."""
    reader = Reader(code)
    top = reader.obj()
    found = [c for c in top.walk() if c.name == FUNC]
    assert len(found) == 1, "function %s: %d matches" % (FUNC.decode(), len(found))
    fn = found[0]
    co = fn.code
    # LOAD_GLOBAL time / LOAD_ATTR time / CALL_FUNCTION 0 / STORE_FAST curTime
    assert fn.names[0] == b"time" and fn.varnames[0] == b"curTime", (fn.names, fn.varnames)
    assert co[1:3] == b"\x00\x00" and co[4:6] == b"\x00\x00" and co[6:9] == b"\x83\x00\x00", co[:12].hex()
    assert co[9:12] == bytes([STORE_FAST, 0, 0]), co[:12].hex()
    spans = [(o, n) for o, n, _t in reader.spans if n == len(co) and xs(code[o:o + n]) == co]
    # Other functions can have identical bytecode. walk() visits code objects in the order their
    # co_code is marshalled, so the n-th such function owns the n-th matching span.
    twins = [c for c in top.walk() if c.code == co]
    assert len(spans) == len(twins), "co_code: %d spans, %d functions" % (len(spans), len(twins))
    off, length = spans[next(i for i, c in enumerate(twins) if c is fn)]

    # The consts tuple follows co_code in a marshalled code object: "(" + count + items.
    tup = off + length
    assert code[tup:tup + 1] == b"(", code[tup:tup + 1]
    count = struct.unpack_from("<i", code, tup + 1)[0]
    assert count == len(fn.consts)
    end_reader = Reader(code)
    end_reader.p, end_reader.refs = tup, [b""] * 100000
    end_reader.obj()
    end = end_reader.p

    new_co = bytes([LOAD_CONST]) + struct.pack("<H", count) + NOP + NOP + co[9:]
    assert len(new_co) == len(co)
    return (code[:off] + xs(new_co) + b"(" + struct.pack("<i", count + 1)
            + code[tup + 5:end] + encode_float(stamp) + code[end:])


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("npk")
    ap.add_argument("out")
    ap.add_argument("--key", default=os.path.join(here, "neox_rotor_key.txt"))
    ap.add_argument("--date", default="2022-04-20 12:00:00", help="UTC; match the gateway's GAME_DATE")
    args = ap.parse_args()
    from npk_decrypt import FastRotor, read_index, reverse_string, unreverse_string

    stamp = float(calendar.timegm(time.strptime(args.date, "%Y-%m-%d %H:%M:%S")))
    data = open(args.npk, "rb").read()
    entries = read_index(data)
    rotor = FastRotor(open(args.key, encoding="latin-1").read(), max(e[2] for e in entries) + 65536)
    for entry in entries:
        try:
            code = reverse_string(zlib.decompress(rotor.decrypt(data[entry[1]:entry[1] + entry[2]])))
            if Reader(code).obj().filename.replace(b"\\", b"/") != MODULE.encode():
                continue
        except Exception:
            continue
        new = patch_module(code, stamp)
        check = [c for c in Reader(new).obj().walk() if c.name == FUNC][0]
        assert decode_float(check.consts[-1]) == stamp
        encoded = rotor.encrypt(zlib.compress(unreverse_string(new), 9))
        assert reverse_string(zlib.decompress(rotor.decrypt(encoded))) == new
        dst = os.path.join(args.out, MODULE[:-3] + ".nxs")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(encoded)
        print("patched %s -> %s (date %s UTC)" % (MODULE, dst, args.date))
        return
    sys.exit("module %s not found in %s" % (MODULE, args.npk))


if __name__ == "__main__":
    main()
