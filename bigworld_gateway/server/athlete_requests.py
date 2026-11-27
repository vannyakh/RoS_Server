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
GP = 1        # const.MallCurrencyType.GP (coins; extract/hallprop_prices.json currency_types)
CLOTHING_CHIPS = 4       # universal clothing shards (blue puzzle icon in Convert UI)
COLOUR_DIAMOND = 9       # colour diamonds (purple puzzle icon)
CONVERT_APPEARANCE_CLASSIFY = 1907  # queryAvailableConvertItem arg from Depot > Convert repeats

# Requests the client repeats in the background; they are decoded but not logged.
QUIET = {"saLogFromClient", "saLogG89UIClickFromClient", "saLogUIEnterEventFromClient",
         "saLogUIClickFromClient", "saLogUITabEventFromClient", "doSaLogMallClick",
         "uploadGameNpkVersionInfo", "onResClientHeartbeat", "refreshMicroServiceToken"}

# Lobby START chain (athlete_base_exposed.json); used by compatibility tests.
HALL_START_SEQUENCE = (
    "getOpenMaintenanceFightTipFlag",
    "createHallTeam",
    "getReadyForBattleGround",
    "changeOccupation",
    "reqPayedPartnerRel",
    "matchBattleGround",
)


def _load_names():
    global _names, _args
    if _names is None:
        with open(os.path.join(_EXTRACT, "athlete_base_exposed.json"), encoding="utf-8") as f:
            _names = json.load(f)["names"]
        _args = {m[0]: m[1] for m in bwdefs.shared().methods("Athlete", "BaseMethods")}
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


def _env_on(name):
    return os.environ.get(name, "").strip().lower() in ("1", "on", "yes", "true")


def supplement_info_client():
    """Pickled catalogue for onQueryAvailableSupplement (may differ from supplement_info())."""
    info = supplement_info()
    if not _env_on("SUPPLY_CLEAR_WEEKLY_FLAGS"):
        return info
    # IS_THIS_WEEK on KIND 7 monthly boxes (9778/9779) makes the Supply UI prefer Supreme/Helios
    # art even when the Looks tab is selected on first open.
    return {sid: {**v, "IS_THIS_WEEK": False} for sid, v in info.items()}


def current_looks_supply_id():
    """Open Looks (KIND 3) box: in sale, not archived as IS_PREVIOUS_BOX only when possible."""
    cands = [(v.get("SORT_KEY", 0), sid) for sid, v in supplement_info().items()
             if v.get("KIND") == 3 and v.get("IS_IN_SALE") and not v.get("IS_PREVIOUS_BOX")]
    return min(cands)[1] if cands else 0


def supply_ticket_currencies():
    """Sorted non-diamond currency ids any supply box accepts (the ticket currencies)."""
    ids = set()
    for v in supplement_info().values():
        c = v.get("CURRENCY_ID")
        for cid in (c if isinstance(c, list) else [c]):
            if isinstance(cid, int) and cid != YUANBAO:
                ids.add(cid)
    return sorted(ids)


def box_currencies(sid):
    """Currency ids box `sid` accepts (CURRENCY_ID: int or list); [] for an unknown box."""
    info = supplement_info().get(int(sid))
    if info is None:
        return []
    c = info.get("CURRENCY_ID")
    return [cid for cid in (c if isinstance(c, list) else [c]) if isinstance(cid, int)]


def this_week_supply_id():
    """Box id the weekly Supply push (UIMgr.gotoThisWeekSupplyPackage) is stored as shown for.

    Athlete.def declares setHasAlreadyShowSupplyID with no arguments, so the server picks the
    id. Rule: the boxes flagged IS_THIS_WEEK in extract/supplement_info.json (the client's own
    supplement data; today 9778 and 9779, both KIND 7 with the same SORT_KEY 45, ONLINE_TIME
    and OFFLINE_TIME), on sale first, lowest id first; 0 when no box is flagged. Nothing in the
    repo shows which of two flagged boxes the client compares hasAlreadyShowSupplyID with, so
    the lowest id is a deterministic choice that needs device confirmation."""
    flagged = [(not v.get("IS_IN_SALE"), sid) for sid, v in supplement_info().items() if v.get("IS_THIS_WEEK")]
    return min(flagged)[1] if flagged else 0


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


# Operator store listings (RoS_Server /api/v1/gateway/store/listings, today lobby themes):
# [{"item_id", "goods_id", "on_sale", "currency": "diamond"|"coin", "price"}]. ros_server sets
# the source to account_link.store_listings; no source or no rows = the client's own table.
_LISTING_CURRENCY = {"diamond": YUANBAO, "coin": GP}
_listing_source = None


def set_listing_source(fn):
    global _listing_source
    _listing_source = fn


def _listings():
    """({goods_id: listing}, {item_id: listing}); empty when RoS_Server has none or is down."""
    try:
        rows = (_listing_source() if _listing_source else None) or []
    except Exception as e:      # a broken source must never break the store
        print(f"      [STORE] listings unavailable ({e}); using client prices")
        rows = []
    by_good, by_item = {}, {}
    for r in rows:
        if r.get("currency") not in _LISTING_CURRENCY:
            continue
        if r.get("goods_id") is not None:
            by_good[int(r["goods_id"])] = r
        if r.get("item_id") is not None:
            by_item[int(r["item_id"])] = r
    return by_good, by_item


def _listed(goods):
    """Copy of a goods dict with the operator listings applied: off-sale goods removed,
    overridden goods at their operator currency and price (DISCOUNT 100)."""
    by_good = _listings()[0]
    if not by_good:
        return dict(goods)
    out = {}
    for gid, g in goods.items():
        r = by_good.get(int(gid))
        if r is None:
            out[gid] = g
        elif r.get("on_sale"):
            out[gid] = {**g, "CURRENCY_ID": _LISTING_CURRENCY[r["currency"]], "PRICE": int(r["price"]), "DISCOUNT": 100}
    return out


def item_off_sale(pid):
    """True when an operator took hall prop `pid` off sale."""
    r = _listings()[1].get(int(pid))
    return r is not None and not r.get("on_sale")


def hallprop_price(pid):
    """(currency id, price) to buy hall prop `pid` (client mall_utils), or None if not for sale."""
    global _prices
    r = _listings()[1].get(int(pid))
    if r is not None:
        return (_LISTING_CURRENCY[r["currency"]], int(r["price"])) if r.get("on_sale") else None
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
        return _listed(t["info"])
    ids, known = set(), False
    for bit, members in t["by_type"].items():
        if types & bit:
            ids |= members
            known = True
    if not known:
        return _listed(t["info"])
    return _listed({k: v for k, v in t["info"].items() if k in ids})


def appearance_mall_goods():
    return _listed(_mall_table()["appearance"])


def mall_good_price(gid, num=1):
    """(currency id, total price after the good's DISCOUNT %) or None if not for sale.
    An operator listing replaces the client's price, or makes the good unbuyable."""
    t = _mall_table()
    g = t["info"].get(int(gid)) or t["appearance"].get(int(gid))
    if not g:
        return None
    g = _listed({int(gid): g}).get(int(gid))
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


# Depot > Workshop (vehicle skin chains). Data read from the client by
# client/frida/payloads/cultivate_rule_fields.py into extract/appearance_cultivate.json.
CULTIVATE_USE_APPEARANCE = 0    # const.CultivateCompoundWay.USE_APPEARANCE (the only way served)

# Failure tips sent in onAppearanceCultivateCompoundFailed. The client's own string keys for
# these cases are not in any extract, so these are plain-English texts (the client shows them).
CULTIVATE_TIPS = {
    "unknown": "This upgrade is not available.",
    "compound_type": "This upgrade method is not supported.",
    "not_craftable": "This skin cannot be crafted in the Workshop.",
    "completed": "You already own this upgrade.",
    "preceding": "Complete the previous level first.",
    "unlock": "Upgrade requirements not met.",
    "props": "Not enough materials.",
    "currency": "Not enough coins.",
    "busy": "An upgrade is already in progress.",
    "server": "Upgrade failed. Please try again later.",
}

_cultivate = None


def _cultivate_table():
    """{cultivateID: {"name", "rules": [...]}} with int keys (cached)."""
    global _cultivate
    if _cultivate is None:
        with open(os.path.join(_EXTRACT, "appearance_cultivate.json"), encoding="utf-8") as f:
            raw = json.load(f)
        _cultivate = {int(k): v for k, v in raw.get("chains", {}).items()}
    return _cultivate


def cultivate_chain(cultivate_id):
    return _cultivate_table().get(int(cultivate_id))


def _cultivate_fail(key, currency_type=0, price=0):
    return {"ok": False, "reason": key, "tips": CULTIVATE_TIPS[key],
            "currency_type": int(currency_type), "price": int(price)}


def plan_cultivate_compound(cultivate_id, rule_id, compound_type, counts, gold):
    """Server-side check of Athlete.appearanceCultivateCompound, in the client's order:
    chain and rule exist -> compound way -> rule not yet completed (target owned) -> every
    earlier rule of the chain completed -> unlock conditions -> prop consumptions -> currency.
    counts: {prop_id: owned count}; gold: currency 1 balance.

    Returns {"ok": True, "target", "require", "consume", "consume_currency", "add"} where
    require/consume/add are [(prop_id, num)] and consume_currency [(currency_id, amount)], or
    {"ok": False, "reason", "tips", "currency_type", "price"}.

    Limits: only compoundType 0 (USE_APPEARANCE) is served; SECOND_CONSUMPTION is not used.
    A rule with no consumption and no unlock condition (every chain's Lv.1 base skin) is
    refused: the base skin comes from supply boxes or the store, never free from the Workshop.
    Only currency 1 (coins) is known as a Workshop cost; another currency id is checked
    against 0 and so refused."""
    have = lambda pid: int(counts.get(int(pid), 0) or 0)
    chain = cultivate_chain(cultivate_id)
    if not chain:
        return _cultivate_fail("unknown")
    rules = chain["rules"]
    idx = next((i for i, r in enumerate(rules) if int(r["rule_id"]) == int(rule_id)), None)
    if idx is None:
        return _cultivate_fail("unknown")
    if int(compound_type) != CULTIVATE_USE_APPEARANCE:
        return _cultivate_fail("compound_type")
    rule = rules[idx]
    if not rule["consume"] and not rule["unlock"]:
        return _cultivate_fail("not_craftable")
    target = int(rule["target"])
    if have(target) > 0:                                       # isDtsAppearanceCultivateRuleCompletedServer
        return _cultivate_fail("completed")
    require = []
    for earlier in rules[:idx]:                                # checkIfPrecedingRuleCompletedServer
        if have(earlier["target"]) <= 0:
            return _cultivate_fail("preceding")
        require.append((int(earlier["target"]), 1))
    for cond in rule["unlock"]:                                # UNLOCK_CONDITION_LIST
        if have(cond["appearance_id"]) < int(cond["num"]):
            return _cultivate_fail("unlock")
        require.append((int(cond["appearance_id"]), int(cond["num"])))
    consume, consume_currency = [], []
    for c in rule["consume"]:
        if "prop_id" in c:
            consume.append((int(c["prop_id"]), int(c["num"])))
        else:
            consume_currency.append((int(c["currency_id"]), int(c["num"])))
    need = {}
    for pid, n in consume:                                     # checkIfMeetAppearanceCultivateRuleConsumptions
        need[pid] = need.get(pid, 0) + n
    for pid, n in need.items():
        if have(pid) < n:
            return _cultivate_fail("props")
    for cid, amount in consume_currency:
        balance = int(gold) if cid == GP else 0
        if balance < amount:
            return _cultivate_fail("currency", cid, amount)
    # Each condition is "own at least N": one prop named by two conditions (an earlier level
    # and an unlock count) needs the larger N, not the sum. RoS_Server sums repeated ids.
    most = {}
    for pid, n in require:
        most[pid] = max(most.get(pid, 0), n)
    require = sorted(most.items())
    return {"ok": True, "target": target, "require": require, "consume": consume,
            "consume_currency": consume_currency, "add": [(target, 1)]}


class Outfit:
    """Per-session equipped appearance lists and the shown lists (equipped + tried on), as the
    client's DtsAppearance types keep them: an item replaces whatever sits in the same slot of
    its list (clothes slot, body/decoration category, the same gun, the same vehicle);
    equipping an equipped item again takes it off. The lobby theme is a single id.
    hall_vehicle: vehicle skins ticked "Display" in Depot > Vehicles, shown in the lobby
    (Athlete.dtsHallVehicleAppearanceList)."""

    LISTS = ("body", "wear", "weapon", "vehicle")

    def __init__(self):
        for k in self.LISTS:
            setattr(self, k, [])
            setattr(self, "show_" + k, None)     # None: same as equipped
        self.theme = 0
        self.hall_vehicle = []
        self.out_weapon = {}      # Depot > Firearms > Display Firearm: {gender 1/2: (weapon skin, pose)}

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

    def set_hall_vehicle(self, pid):
        """Display a vehicle skin in the lobby (setDtsHallVehicleAppearance). False if not a vehicle.
        One skin per vehicle, like equipping: a new skin replaces the displayed skin of the same
        vehicle (the lobby shows the first entry, and Depot ticks every entry)."""
        if self.kind(pid) != "vehicle":
            return False
        pid = int(pid)
        self.hall_vehicle = [pid] + [i for i in self._swap(self.hall_vehicle, pid) if i != pid]   # newest first
        return True

    def cancel_hall_vehicle(self, pid):
        """Stop displaying a vehicle skin in the lobby (cancelDtsHallVehicleAppearance)."""
        self.hall_vehicle = [i for i in self.hall_vehicle if i != int(pid)]

    def sync_hall_vehicle_show(self):
        """Lobby vehicle models read dtsShowVehicleAppearanceList as well as hall_vehicle."""
        if self.hall_vehicle:
            self.show_vehicle = list(self.hall_vehicle)

    def set_out_weapon(self, gender, weapon, pose):
        """Athlete.setOutGameWeapon(charType, weapon, pose): the firearm skin the lobby hero holds
        (dtsOutGameWeapon / ...Male / ...Female). weapon 0 clears it. False if not a weapon skin."""
        weapon, pose = int(weapon), int(pose)
        if weapon and self.kind(weapon) != "weapon":
            return False
        if weapon:
            self.out_weapon[int(gender)] = (weapon, pose)
        else:
            self.out_weapon.pop(int(gender), None)
        return True

    def get_out_weapon(self, gender):
        """(weapon skin, pose) displayed for this gender, or (0, 0)."""
        return self.out_weapon.get(int(gender), (0, 0))

    def cancel_try_on(self):
        for k in self.LISTS:
            setattr(self, "show_" + k, None)

    def to_dict(self):
        d = {**{k: list(getattr(self, k)) for k in self.LISTS}, "theme": self.theme,
             "hall_vehicle": list(self.hall_vehicle),
             "out_weapon": {str(g): list(v) for g, v in self.out_weapon.items()}}
        for k in self.LISTS:
            show = getattr(self, "show_" + k)
            if show is not None:
                d["show_" + k] = list(show)
        return d

    @classmethod
    def from_dict(cls, d):
        o = cls()
        for k in cls.LISTS:
            setattr(o, k, [int(i) for i in (d or {}).get(k, [])])
        o.theme = int((d or {}).get("theme") or 0)
        for i in (d or {}).get("hall_vehicle", []):      # older saves may hold two skins of one vehicle:
            o.hall_vehicle = o._swap(o.hall_vehicle, int(i))   # keep the last one set
        for g, v in ((d or {}).get("out_weapon") or {}).items():
            o.out_weapon[int(g)] = (int(v[0]), int(v[1]))

        for k in cls.LISTS:
            sk = "show_" + k
            if sk in (d or {}):
                setattr(o, sk, [int(i) for i in d[sk]])
        if o.hall_vehicle and o.show_vehicle is None:
            o.sync_hall_vehicle_show()
        return o


# Depot > Convert repeats (iItemConvert on Athlete). Classify id 1907 is what the client sends for
# appearance duplicate conversion (logs: queryAvailableConvertItem args=73070000 -> LE i32 1907).
_CONVERT_QUALITY = None
_CONVERT_REWARD = {
    2: [(CLOTHING_CHIPS, 50)],
    3: [(CLOTHING_CHIPS, 100)],
    4: [(CLOTHING_CHIPS, 250)],
    5: [(CLOTHING_CHIPS, 250), (COLOUR_DIAMOND, 1)],
}


def _convert_quality_table():
    global _CONVERT_QUALITY
    if _CONVERT_QUALITY is None:
        lobby = os.path.join(os.path.dirname(_HERE), "..", "..", "data", "reference", "original_lobby.json")
        if os.path.isfile(lobby):
            with open(lobby, encoding="utf-8") as f:
                data = json.load(f)
            _CONVERT_QUALITY = {int(row["id"]): int(row.get("quality") or 0) for row in data.get("items", [])}
        else:
            _CONVERT_QUALITY = {}
    return _CONVERT_QUALITY


def hallprop_quality(pid):
    """Lobby item quality (2 uncommon .. 5 legendary) for shard rewards."""
    return int(_convert_quality_table().get(int(pid), 3))


def convert_currency_rewards(quality):
    """Per duplicate converted, shard grants by item quality."""
    return list(_CONVERT_REWARD.get(int(quality) or 3, [(CLOTHING_CHIPS, 100)]))


def convert_entry(pid, owned_count):
    """One row in classifiedAvailableConvertItem[classify][convertItemID]."""
    repeats = max(int(owned_count) - 1, 0)
    if repeats <= 0:
        return None
    quality = hallprop_quality(pid)
    return {
        "CONVERT_ITEM_ID": int(pid),
        "PROP_ID": int(pid),
        "QUALITY": quality,
        "CAN_CONVERT_TIMES": repeats,
        "CURRENCY_ITEM_LIST": [{"id": cid, "num": amount} for cid, amount in convert_currency_rewards(quality)],
    }


def build_classified_convert_catalog(counts, classify=CONVERT_APPEARANCE_CLASSIFY):
    """Duplicates the client can turn into shards: one kept copy, the rest convertible."""
    bucket = {}
    for pid, n in counts.items():
        if not appearance_slot(pid):
            continue
        if hallprop_quality(pid) < 2:
            continue
        row = convert_entry(pid, n)
        if row:
            bucket[int(pid)] = row
    return {int(classify): bucket}


def plan_item_convert(convert_id, times, counts, used_times):
    """Validate convertItem(convertItemID, times). used_times: prior conversions for this id."""
    convert_id, times = int(convert_id), max(int(times), 0)
    if times <= 0:
        return {"ok": False, "reason": "times"}
    owned = int(counts.get(convert_id, 0) or 0)
    repeats = max(owned - 1, 0)
    if repeats <= 0:
        return {"ok": False, "reason": "none"}
    if times > repeats:
        return {"ok": False, "reason": "times"}
    entry = convert_entry(convert_id, owned)
    if not entry:
        return {"ok": False, "reason": "none"}
    grants = []
    for row in entry["CURRENCY_ITEM_LIST"]:
        cid, each = int(row["id"]), int(row["num"])
        grants.append((cid, each * times))
    return {
        "ok": True,
        "prop_id": convert_id,
        "times": times,
        "consume": (convert_id, times),
        "grants": grants,
        "used_times": int(used_times or 0) + times,
    }
