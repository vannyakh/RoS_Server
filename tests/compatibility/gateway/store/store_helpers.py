"""Shared request builders and reply readers for the in-game Store (mall) gateway tests
(imported by conftest.py and the test modules; basename kept unique for pytest's prepend
import mode)."""

import pickle
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATEWAY_SERVER = REPO / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

ADDR = ("10.0.0.4", 5000)
ADDR_B = ("10.0.0.5", 5001)

YUANBAO, GP = 2, 1

# Goods from extract/mall_goods.json (the client's own mall tables).
BRIGADE = 10000001       # diamonds 209, DISCOUNT 100, gives a hall prop
GOBI = 10000002          # diamonds 209
HAWK = 10000003          # diamonds 1280 (more than the 1000 test balance)
LIONHEART_X10 = 1030     # diamonds 400 at DISCOUNT 48 -> 192
TRAINING_GIFT = 3003     # coins (GP) 100
JAWS_3D = 9100544        # currency 208 (not diamonds, not coins), 150
SUIT = 9999901           # suit good: no hall prop -> not buyable here
APPEARANCE = 9901        # appearance mall good, diamonds 9999
UNKNOWN = 424242
HALL_PROP = 120901       # extract/hallprop_prices.json: diamonds 2280
NOT_A_HALL_PROP = 999999  # not in hallprop_prices.json


def read_blob(buf, i=0):
    """BigWorld STRING/BLOB at buf[i:] -> (bytes, next index)."""
    n = buf[i]
    i += 1
    if n == 0xFF:
        n = int.from_bytes(buf[i:i + 3], "little")
        i += 3
    return buf[i:i + n], i + n


def read_py(buf, i=0):
    data, j = read_blob(buf, i)
    return pickle.loads(data), j


def int_array(ids):
    return struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", int(i)) for i in ids)


def read_int_array(buf, i=0):
    n = struct.unpack_from("<I", buf, i)[0]
    i += 4
    return [struct.unpack_from("<i", buf, i + 4 * k)[0] for k in range(n)], i + 4 * n


def blob(text):
    data = text.encode()
    return bytes([len(data)]) + data


def buy(udp, good, num=1, addr=ADDR, name="buyMallGood", coupons=()):
    """buyMallGood / buyMallGoodInAppearanceMall(goodID, num, coupons[], logStr)."""
    return udp._athlete_request(addr, name, struct.pack("<ii", good, num) + int_array(coupons) + blob("mall"))


def buy_multi(udp, goods, nums, addr=ADDR):
    """buyMultipleMallGood(goods[], nums[], coupons[], logStr)."""
    return udp._athlete_request(addr, "buyMultipleMallGood",
                                int_array(goods) + int_array(nums) + int_array([]) + blob("mall"))


def buy_hall_prop(udp, prop, addr=ADDR):
    """buyDtsHallProp(propID, coupons[], logStr)."""
    return udp._athlete_request(addr, "buyDtsHallProp", struct.pack("<i", prop) + int_array([]) + blob("mall"))


def names(calls):
    return [n for n, _ in calls]


def last(calls, method):
    return [a for n, a in calls if n == method][-1]


def bought_props(calls):
    """Prop ids of the last onBuyMallGood(ARRAY of INT32)."""
    props, end = read_int_array(last(calls, "onBuyMallGood"))
    assert end == len(last(calls, "onBuyMallGood"))
    return props


def failed_args(calls):
    """onBuyMallGoodFailed(tips, goodID, num, currency, price, array, str) -> (tips, good, num, cur, price, arr, s)."""
    args = last(calls, "onBuyMallGoodFailed")
    tips, i = read_blob(args)
    good, num, cur, price = struct.unpack_from("<iiii", args, i)
    arr, j = read_int_array(args, i + 16)
    text, k = read_blob(args, j)
    assert k == len(args)
    return tips, good, num, cur, price, arr, text


def yb_updates(calls):
    """(free, pay, src) of every onYBUpdated."""
    return [struct.unpack("<qqi", a) for n, a in calls if n == "onYBUpdated"]


def added_items(calls):
    """Item ids of every onAddDtsAppearanceItem, in order."""
    return [struct.unpack_from("<i", a)[0] for n, a in calls if n == "onAddDtsAppearanceItem"]
