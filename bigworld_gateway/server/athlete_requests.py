"""Client -> server Athlete base-method calls: decoding by name and lobby replies.

Message ids (fitted on logged traffic, every sample's argument sizes match its .def types):
the client's exposed base-method table has 1191 entries (extract/athlete_base_exposed.json,
read from client memory). Index i < 57 is sent as msg 0xC0 + i. Larger indices are sent as
msg 0xF9 + (k >> 8) followed by one sub byte k & 0xff, where k = i - 57.
"""
import json
import os
import pickle
import random
import struct
import time

import bwdefs

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXTRACT = os.path.join(_HERE, "extract")
DIRECT = 57
_names = None
_args = None
_supp_info = None
_supp_props = None
_prices = None
YUANBAO = 2   # const.MallCurrencyType.YUANBAO (diamonds)

# Requests the client repeats in the background; they are decoded but not logged.
QUIET = {"saLogFromClient", "saLogG89UIClickFromClient", "saLogUIEnterEventFromClient",
         "saLogUIClickFromClient", "saLogUITabEventFromClient", "doSaLogMallClick",
         "uploadGameNpkVersionInfo", "onResClientHeartbeat", "refreshMicroServiceToken"}


def _load_names():
    global _names, _args
    if _names is None:
        with open(os.path.join(_EXTRACT, "athlete_base_exposed.json"), encoding="utf-8") as f:
            _names = json.load(f)["names"]
        _args = {m[0]: m[1] for m in bwdefs.Defs().methods("Athlete", "BaseMethods")}
    return _names


def decode(msgid, payload):
    """(name, arg bytes) for one Athlete base call, or None if msgid is not one."""
    names = _load_names()
    if 0xC0 <= msgid < 0xC0 + DIRECT:
        idx, args = msgid - 0xC0, payload
    elif 0xC0 + DIRECT <= msgid <= 0xFD and payload:
        idx, args = DIRECT + ((msgid - (0xC0 + DIRECT)) << 8) + payload[0], payload[1:]
    else:
        return None
    if idx >= len(names):
        return None
    return names[idx], args


def encode_call(name, args=b""):
    """Inverse of decode (used by tests)."""
    idx = _load_names().index(name)
    if idx < DIRECT:
        return 0xC0 + idx, args
    k = idx - DIRECT
    return 0xC0 + DIRECT + (k >> 8), bytes([k & 0xFF]) + args


class Reader:
    """Read BigWorld-encoded arguments in order."""

    def __init__(self, data):
        self.b, self.i = data, 0

    def _fixed(self, fmt):
        v = struct.unpack_from(fmt, self.b, self.i)[0]
        self.i += struct.calcsize(fmt)
        return v

    def i8(self):
        return self._fixed("<b")

    def i32(self):
        return self._fixed("<i")

    def u32(self):
        return self._fixed("<I")

    def blob(self):
        n = self.b[self.i]
        self.i += 1
        if n == 0xFF:
            n = int.from_bytes(self.b[self.i:self.i + 3], "little")
            self.i += 3
        v = self.b[self.i:self.i + n]
        self.i += n
        return v

    def string(self):
        return self.blob().decode("utf-8", errors="replace")

    def i32_array(self):
        return [self.i32() for _ in range(self.u32())]


def blob(b):
    if isinstance(b, str):
        b = b.encode()
    if len(b) < 255:
        return bytes([len(b)]) + b
    return b"\xff" + struct.pack("<I", len(b))[:3] + b


def py(obj):
    return blob(pickle.dumps(obj, protocol=2))


def supplement_info():
    """{supplementID: {CURRENCY_ID, BUY_TIMES_PRICE, KIND, ...}} the client's supply UIs read."""
    global _supp_info
    if _supp_info is None:
        with open(os.path.join(_EXTRACT, "supplement_info.json"), encoding="utf-8") as f:
            _supp_info = {int(k): v for k, v in json.load(f).items()}
        # The draw result screens read the price of the next draw; prices do not rise here.
        for v in _supp_info.values():
            v.setdefault("NEXT_BUY_TIMES_PRICE", v.get("BUY_TIMES_PRICE"))
    return _supp_info


def supplement_prizes(sid):
    """Prop ids a supply box can award (client's getAllPossiblePropID)."""
    global _supp_props
    if _supp_props is None:
        with open(os.path.join(_EXTRACT, "supplement_props.json"), encoding="utf-8") as f:
            _supp_props = {int(k): v for k, v in json.load(f)["props"].items()}
    return _supp_props.get(int(sid), [])


def draw(sid, count, rng=random):
    """`count` prize prop ids from box `sid` (uniform; the real odds are server-side only)."""
    pool = supplement_prizes(sid)
    return [rng.choice(pool) for _ in range(count)] if pool else []


class SupplyState:
    """Per-session free-draw bookkeeping: {sid: last free draw ts}, {sid: free draws used}."""

    def __init__(self):
        self.free_ts = {}
        self.free_times = {}

    def note_free(self, sid):
        self.free_ts[sid] = int(time.time())
        self.free_times[sid] = self.free_times.get(sid, 0) + 1


def hallprop_price(pid):
    """(currency id, price) to buy hall prop `pid` (client mall_utils), or None if not for sale."""
    global _prices
    if _prices is None:
        with open(os.path.join(_EXTRACT, "hallprop_prices.json"), encoding="utf-8") as f:
            _prices = {int(k): tuple(v) for k, v in json.load(f)["prices"].items()}
    return _prices.get(int(pid))


class Wallet:
    """Per-session currency balances {currency id: amount}."""

    def __init__(self, balances):
        self.balances = dict(balances)

    def pay(self, currency, price):
        """Deduct `price`; False (and nothing deducted) if the balance is too low."""
        have = self.balances.get(currency, 0)
        if price > have:
            return False
        self.balances[currency] = have - price
        return True


def draw_price(sid, currency, multi=False):
    """Price of one draw (or a multi draw) of box `sid` paid in `currency`, from the box info
    (CURRENCY_ID is an int for one-currency boxes, a list for two-currency boxes)."""
    info = supplement_info().get(int(sid), {})
    ids = info.get("CURRENCY_ID")
    prices = info.get("BUY_MULTIPLE_TIMES_PRICE" if multi else "BUY_TIMES_PRICE")
    if not isinstance(ids, list):
        ids, prices = [ids], [prices]
    for cid, price in zip(ids, prices if isinstance(prices, list) else [prices]):
        if cid == currency:
            return int(price or 0)
    return 0


def multi_count(sid):
    """Draws in one multi draw (the client's CONTINUE_LOTTERY_TIMES is 10 for every multi box)."""
    return 10


_types = None


def appearance_type(pid):
    """Hall prop type name of `pid` (extract/hall_props.json by_type), or None."""
    global _types
    if _types is None:
        with open(os.path.join(_EXTRACT, "hall_props.json"), encoding="utf-8") as f:
            _types = {i: t for t, ids in json.load(f)["by_type"].items() for i in ids}
    return _types.get(int(pid))


class Outfit:
    """Per-session worn appearance: body parts (face, hair...) and wearables (clothes...).
    Without the client's slot table, equipping again the same id takes it off; other items stay."""

    def __init__(self):
        self.body = []
        self.wear = []

    def equip(self, pid):
        """Returns "body", "wear" or None (type the outfit lists do not track)."""
        kind = {"BobyAppearanceType": "body", "WearableApperanceType": "wear"}.get(appearance_type(pid))
        if kind:
            items = getattr(self, kind)
            if pid in items:
                items.remove(pid)
            else:
                items.append(pid)
        return kind
