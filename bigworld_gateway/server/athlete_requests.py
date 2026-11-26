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

# Game clock. The client's date-gated data ends in 2022 (season 21: 2022.03.16-05.24, last
# monthly Supreme box until 2022.12.30), so a real 2026 clock shows "LEFT -1640 days" and blank
# boxes. Every timestamp sent to the client uses this clock: GAME_DATE (UTC), advancing in real
# time from server start. GAME_DATE=real uses the real clock.
_START = time.time()


def game_now():
    spec = os.environ.get("GAME_DATE", "2022-04-20 12:00:00")
    if spec == "real":
        return time.time()
    import calendar
    base = calendar.timegm(time.strptime(spec, "%Y-%m-%d %H:%M:%S"))
    return base + (time.time() - _START)
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

    def i16(self):
        return self._fixed("<h")

    def i32(self):
        return self._fixed("<i")

    def u64(self):
        return self._fixed("<Q")

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


def supply_ticket_currencies():
    """Sorted non-diamond currency ids any supply box accepts (the ticket currencies)."""
    ids = set()
    for v in supplement_info().values():
        c = v.get("CURRENCY_ID")
        for cid in (c if isinstance(c, list) else [c]):
            if isinstance(cid, int) and cid != YUANBAO:
                ids.add(cid)
    return sorted(ids)


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
        self.free_ts[sid] = int(game_now())
        self.free_times[sid] = self.free_times.get(sid, 0) + 1


def hallprop_price(pid):
    """(currency id, price) to buy hall prop `pid` (client mall_utils), or None if not for sale."""
    global _prices
    if _prices is None:
        with open(os.path.join(_EXTRACT, "hallprop_prices.json"), encoding="utf-8") as f:
            _prices = {int(k): tuple(v) for k, v in json.load(f)["prices"].items()}
    return _prices.get(int(pid))


_mall = None


def _mall_table():
    """extract/mall_goods.json: the client's own mall_utils tables (createMallGoodsInfo of the
    available goods, per-location id lists, mall good -> hall prop id)."""
    global _mall
    if _mall is None:
        with open(os.path.join(_EXTRACT, "mall_goods.json"), encoding="utf-8") as f:
            raw = json.load(f)
        _mall = {"info": {int(k): v for k, v in raw["info"].items()},
                 "appearance": {int(k): v for k, v in raw["appearance_info"].items()},
                 "by_type": {int(k): set(v) for k, v in raw["ids_by_type"].items()},
                 "props": {int(k): int(v) for k, v in raw["props"].items()}}
    return _mall


def mall_goods(types=0):
    """onQueryAvailableMallGoods* dict {mallGoodID: {NAME, CURRENCY_ID, PRICE, DISCOUNT, BUY_TIMES}}
    for a GoodsLocationType bit mask (0 = ALL; bits without a display field also get all)."""
    t = _mall_table()
    if not types:
        return dict(t["info"])
    ids, known = set(), False
    for bit, members in t["by_type"].items():
        if types & bit:
            ids |= members
            known = True
    if not known:
        return dict(t["info"])
    return {k: v for k, v in t["info"].items() if k in ids}


def appearance_mall_goods():
    return dict(_mall_table()["appearance"])


def mall_good_price(gid, num=1):
    """(currency id, total price after the good's DISCOUNT %) or None if not for sale."""
    t = _mall_table()
    g = t["info"].get(int(gid)) or t["appearance"].get(int(gid))
    if not g:
        return None
    return int(g["CURRENCY_ID"]), int(g["PRICE"]) * int(g.get("DISCOUNT", 100)) // 100 * max(int(num), 1)


def mall_good_prop(gid):
    """Hall prop the mall good gives (None for suit goods)."""
    return _mall_table()["props"].get(int(gid))


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


_slots = None


def _slot_table():
    global _slots
    if _slots is None:
        with open(os.path.join(_EXTRACT, "appearance_slots.json"), encoding="utf-8") as f:
            raw = json.load(f)
        _slots = {"items": {int(k): (v[0], v[1], int(v[2] or 0)) for k, v in raw["items"].items()},
                  "suits": {int(k): v for k, v in raw["suits"].items()}}
    return _slots


def appearance_slot(pid):
    """(list "body"/"wear"/"weapon"/"vehicle"/"theme", slot key, gender 0/1/2) or None."""
    return _slot_table()["items"].get(int(pid))


def appearance_suit(sid):
    """{"name", "gender", "items"} of a clothes suit (SET page), or None."""
    return _slot_table()["suits"].get(int(sid))


class Outfit:
    """Per-session equipped appearance lists and the shown lists (equipped + tried on), as the
    client's DtsAppearance types keep them: an item replaces whatever sits in the same slot of
    its list (clothes slot, body/decoration category, the same gun, the same vehicle);
    equipping an equipped item again takes it off. The lobby theme is a single id."""

    LISTS = ("body", "wear", "weapon", "vehicle")

    def __init__(self):
        for k in self.LISTS:
            setattr(self, k, [])
            setattr(self, "show_" + k, None)     # None: same as equipped
        self.theme = 0

    @staticmethod
    def kind(pid):
        s = appearance_slot(pid)
        return s[0] if s else None

    @staticmethod
    def _same_slot(a, b):
        sa, sb = appearance_slot(a), appearance_slot(b)
        return bool(sa and sb and sa[0] == sb[0] and sa[1] == sb[1])

    @classmethod
    def _swap(cls, items, pid):
        return [i for i in items if i != pid and not cls._same_slot(i, pid)] + [pid]

    def shown(self, kind):
        v = getattr(self, "show_" + kind)
        return list(getattr(self, kind) if v is None else v)

    def equip(self, pid):
        """Returns the list kind changed ("theme" too), or None for untracked types."""
        kind = self.kind(pid)
        if kind == "theme":
            self.theme = int(pid)
        elif kind:
            items = getattr(self, kind)
            setattr(self, kind, [i for i in items if i != pid] if pid in items else self._swap(items, pid))
            setattr(self, "show_" + kind, None)
        return kind

    def try_on(self, pid):
        """Show `pid` without equipping it. Returns the kind or None."""
        kind = self.kind(pid)
        if kind and kind != "theme":
            setattr(self, "show_" + kind, self._swap(self.shown(kind), pid))
        return kind

    def try_off(self, pid):
        """Take a shown item off; the equipped item of that slot (if any) comes back."""
        kind = self.kind(pid)
        if kind and kind != "theme":
            shown = [i for i in self.shown(kind) if i != pid]
            back = [i for i in getattr(self, kind) if i != pid and self._same_slot(i, pid)]
            setattr(self, "show_" + kind, shown + [i for i in back if i not in shown])
        return kind

    def cancel_try_on(self):
        for k in self.LISTS:
            setattr(self, "show_" + k, None)

    def to_dict(self):
        return {**{k: list(getattr(self, k)) for k in self.LISTS}, "theme": self.theme}

    @classmethod
    def from_dict(cls, d):
        o = cls()
        for k in cls.LISTS:
            setattr(o, k, [int(i) for i in (d or {}).get(k, [])])
        o.theme = int((d or {}).get("theme") or 0)
        return o
