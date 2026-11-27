"""Offline trace of the gateway login -> lobby stream and the Supply catalogue (RO-101).

Run from the repo root:

    .venv\\Scripts\\python.exe bigworld_gateway/tools/startup_trace.py [--logs] [--no-supply]

What it does, without sockets, the RoS_Server API or saved_accounts.json:

1. Builds the real BaseApp bodies ros_server.py sends to an existing account after
   Account.handshake: resetEntities + createBasePlayer(Athlete), the login bundle from
   GateUDP._send_enter_hall_calls (onLogin ... _lobby_data_calls()), and the delayed enterHall
   bundle. _send_bundle and the asyncio timers are replaced by recorders, so the code path is the
   gateway's own. Every Athlete client method is recorded with its encoded size and build time.
2. Builds the queryAvailableSupplement reply through GateUDP._athlete_request (cold and warm) and
   times py(athlete_requests.supplement_info()) on its own.
3. Checks extract/supplement_info.json, supplement_props.json and supplement_ids.json.
4. With --logs, scans bigworld_gateway/logs/server*.log for login and Supply request timing.

Environment defaults copy bigworld_gateway/config.cmd (LDPlayer, 2022 clock). Override any of
them in the shell before running. No secrets or tokens are printed.
"""
import argparse
import collections
import contextlib
import io
import json
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GW = os.path.join(ROOT, "bigworld_gateway")
SERVER = os.path.join(GW, "server")
EXTRACT = os.path.join(SERVER, "extract")
LOGS = os.path.join(GW, "logs")
sys.path.insert(0, SERVER)

# Same values as config.cmd (the LDPlayer route). setdefault: the caller's environment wins.
CONFIG_DEFAULTS = {
    "SWITCH_TO": "athlete", "ATHLETE_CELL": "off", "TRANSITION_RESET": "off",
    "LEAVE_OLD_AVATAR": "off", "METHOD_BASE": "0x80", "METHOD_EXT": "byte",
    "UNLOCK_ALL": "off", "FRAG_BODY": "700", "GAME_DATE": "2022-04-20 12:00:00",
    "LOBBY_SWITCHES_OFF": "SysEnableHuiliuRecallSystem,EnableRecallPlayer,EnableNewRecallPlayer",
    "HALL_POPUPS": "off", "TEST_ACCOUNT_NAME": "TraceUser",
}
for _k, _v in CONFIG_DEFAULTS.items():
    os.environ.setdefault(_k, _v)
os.environ["GATEWAY_API_KEY"] = ""          # account link off for this process

with contextlib.redirect_stdout(io.StringIO()):
    import account_link
    import athlete_requests
    import ros_server

# No network: every RoS_Server call reports "not reachable", as when the API is down.
account_link._call = lambda method, path, body: None
account_link._current = None

# No saved_accounts.json: a fixed existing account (normal male hero), writes dropped.
FAKE_ACCOUNTS = {"default": {"name": os.environ["TEST_ACCOUNT_NAME"], "char_type": 20001}}
ros_server.load_accounts = lambda: json.loads(json.dumps(FAKE_ACCOUNTS))
ros_server.save_account = lambda key, data: None

FRAG = int(os.environ["FRAG_BODY"])


class Recorder:
    """Wraps ros_server.athlete_method; one row per emitted Athlete client method."""

    def __init__(self):
        self.rows = []
        self.stage = "?"
        self._mark = time.perf_counter()
        self._orig = ros_server.athlete_method

    def mark(self):
        self._mark = time.perf_counter()

    def __call__(self, name, args, quiet=False):
        t0 = time.perf_counter()
        out = self._orig(name, args, quiet)
        t1 = time.perf_counter()
        # build = time since the previous method (includes argument building), encode = this call
        self.rows.append({"stage": self.stage, "name": name, "bytes": len(out),
                          "build_ms": (t1 - self._mark) * 1000, "encode_ms": (t1 - t0) * 1000})
        self._mark = t1
        return out


class FakeLoop:
    def __init__(self):
        self.timers = []

    def call_later(self, delay, fn, *args):
        self.timers.append((delay, fn, args))


def frags(n):
    return 1 if n <= FRAG else math.ceil(n / FRAG)


def build_login_stream(rec):
    """Bodies the gateway sends for one existing-account login (no network)."""
    gate = ros_server.GateUDP.__new__(ros_server.GateUDP)
    ros_server.GateUDP.__init__(gate, 0)
    addr = ("trace", 1)
    sent = []
    gate._send_bundle = lambda a, body, seq, key: sent.append((rec.stage, body))
    loop = FakeLoop()
    real_get_loop = ros_server.asyncio.get_event_loop
    ros_server.asyncio.get_event_loop = lambda: loop
    bundles = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ros_server.athlete_method = rec
            # 1. Account.handshake reply (ros_server.py, SWITCH_TO=athlete branch)
            rec.stage = "createBasePlayer"
            rec.mark()
            t0 = time.perf_counter()
            body = b"\x04\x00" + ros_server.athlete_create_message()
            bundles.append(("resetEntities + createBasePlayer(Athlete)", len(body),
                            (time.perf_counter() - t0) * 1000))
            # 2. _send_enter_hall_calls (HALL_DELAY later): login bundle + scheduled enterHall
            rec.stage = "login bundle"
            rec.mark()
            t0 = time.perf_counter()
            gate._send_enter_hall_calls(addr, b"\x00" * 16)
            t_login = (time.perf_counter() - t0) * 1000
            login_body = [b for s, b in sent if s == "login bundle"]
            bundles.append(("onLogin .. _lobby_data_calls()", sum(map(len, login_body)), t_login))
            # 3. timers it scheduled: enterHall bundle (0.2 s), unlock/appearance pushes if enabled
            rec.stage = "enterHall"
            for delay, fn, args in loop.timers:
                if getattr(fn, "__name__", "") == "<lambda>" or fn is gate._send_bundle:
                    rec.mark()
                    t0 = time.perf_counter()
                    fn(*args)
                    bundles.append((f"timer +{delay}s: enterHall bundle", len(sent[-1][1]),
                                    (time.perf_counter() - t0) * 1000))
                else:
                    bundles.append((f"timer +{delay}s: {getattr(fn, '__name__', fn)} (not built)", 0, 0.0))
    finally:
        ros_server.athlete_method = rec._orig
        ros_server.asyncio.get_event_loop = real_get_loop
    for r in rec.rows:              # enterHall is encoded in _send_enter_hall_calls, sent by the timer
        if r["name"] == "enterHall":
            r["stage"] = "enterHall"
    return gate, addr, bundles


def build_supply_reply(rec, gate, addr):
    out = []
    py = athlete_requests.py
    with contextlib.redirect_stdout(io.StringIO()):
        ros_server.athlete_method = rec
        try:
            for label in ("queryAvailableSupplement reply (cold)", "queryAvailableSupplement reply (warm)"):
                rec.stage = label
                rec.mark()
                t0 = time.perf_counter()
                body = gate._athlete_request(addr, "queryAvailableSupplement", b"")
                out.append((label, len(body), (time.perf_counter() - t0) * 1000))
        finally:
            ros_server.athlete_method = rec._orig
    info = athlete_requests.supplement_info()
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        blob = py(info)
        times.append((time.perf_counter() - t0) * 1000)
    out.append(("py(supplement_info()) x20, median", len(blob), sorted(times)[len(times) // 2]))
    return out


def print_table(rows, bundles, supply):
    print("== Athlete client methods, login -> lobby (existing account, config.cmd env) ==")
    print(f"{'#':>3} {'stage':<18} {'method':<42} {'bytes':>7} {'build ms':>9} {'enc ms':>7}")
    stage_tot = collections.OrderedDict()
    for i, r in enumerate(rows, 1):
        print(f"{i:>3} {r['stage'][:18]:<18} {r['name'][:42]:<42} {r['bytes']:>7} "
              f"{r['build_ms']:>9.3f} {r['encode_ms']:>7.3f}")
        t = stage_tot.setdefault(r["stage"], [0, 0, 0.0])
        t[0] += 1
        t[1] += r["bytes"]
        t[2] += r["build_ms"]
    print("\n== Per stage (Athlete methods only) ==")
    for s, (n, b, ms) in stage_tot.items():
        print(f"  {s:<40} {n:>3} methods {b:>7} B {ms:>9.3f} ms")
    print("\n== Bundles (body bytes; FRAG_BODY=%d -> fragments) ==" % FRAG)
    total_b = total_ms = 0
    for label, n, ms in bundles:
        total_b += n
        total_ms += ms
        print(f"  {label:<48} {n:>7} B {frags(n) if n else 0:>3} frag {ms:>9.3f} ms")
    print(f"  {'TOTAL login stream':<48} {total_b:>7} B {'':>8} {total_ms:>9.3f} ms")
    counts = collections.Counter(r["name"] for r in rows if r["stage"] in ("login bundle", "enterHall"))
    print(f"  Athlete methods in login+enterHall bundles: {sum(counts.values())} calls, "
          f"{len(counts)} distinct; repeated: "
          + ", ".join(f"{k} x{v}" for k, v in counts.items() if v > 1))
    print("  createBasePlayer carries the 720 Athlete properties as one stream (not methods).")
    print("\n== Supply catalogue reply ==")
    for label, n, ms in supply:
        print(f"  {label:<48} {n:>7} B {frags(n):>3} frag {ms:>9.3f} ms")


def supply_analysis():
    info = {int(k): v for k, v in json.load(open(os.path.join(EXTRACT, "supplement_info.json"))).items()}
    props = {int(k): v for k, v in json.load(open(os.path.join(EXTRACT, "supplement_props.json")))["props"].items()}
    ids = json.load(open(os.path.join(EXTRACT, "supplement_ids.json")))
    kind_name = {}
    for name, sids in ids.get("by_kind", {}).items():
        for s in sids:
            if s in info:
                kind_name.setdefault(info[s]["KIND"], set()).add(name)
    print("\n== supplement_info.json check ==")
    print(f"  boxes: info={len(info)} ids.all={len(ids.get('all', []))} prize pools={len(props)}")
    print(f"  ids.all == info keys: {set(ids.get('all', [])) == set(info)}; "
          f"boxes without prize pool: {sorted(set(info) - set(props))[:20]}")
    fields = sorted({f for v in info.values() for f in v})
    print(f"  fields: {fields}")
    dated = [f for f in fields if re.search(r"(^|_)(TIME|DATE|START|END|ONLINE|OFFLINE)(_|$)", f)]
    print(f"  date fields: {dated or 'NONE - the extract has no sale dates; date ranges cannot be checked from it'}")
    print(f"  {'KIND':>4} {'client kind name':<30} {'boxes':>5} {'currencies':<22} {'single price':<16} "
          f"{'multi price':<16} {'pool min/max':<12} flags")
    by_kind = collections.defaultdict(list)
    for sid, v in info.items():
        by_kind[v["KIND"]].append((sid, v))
    for kind in sorted(by_kind):
        boxes = by_kind[kind]
        curs, singles, multis = collections.Counter(), set(), set()
        flags = collections.Counter()
        pools = [len(props.get(s, [])) for s, _ in boxes]
        for sid, v in boxes:
            c, p1, p10 = v["CURRENCY_ID"], v["BUY_TIMES_PRICE"], v["BUY_MULTIPLE_TIMES_PRICE"]
            curs[str(c)] += 1
            singles.add(str(p1))
            multis.add(str(p10))
            for f in ("IS_THIS_WEEK", "IS_LAST_WEEK", "IS_PREVIOUS_BOX", "IS_IN_SALE"):
                if v.get(f):
                    flags[f[3:].lower()] += 1
            # shape rule from LOBBY_FINDINGS: list currency -> list prices of the same length
            if isinstance(c, list) != isinstance(p1, list) or (isinstance(c, list) and len(c) != len(p1)):
                print(f"    !! box {sid}: CURRENCY_ID {c} and BUY_TIMES_PRICE {p1} shapes differ")
        nm = "/".join(sorted(kind_name.get(kind, {"(not in supplement_ids)"})))
        print(f"  {kind:>4} {nm[:30]:<30} {len(boxes):>5} {','.join(curs)[:22]:<22} "
              f"{','.join(sorted(singles))[:16]:<16} {','.join(sorted(multis))[:16]:<16} "
              f"{min(pools)}/{max(pools):<8} {','.join(f'{k}={n}' for k, n in flags.items())}")
    ticket = athlete_requests.supply_ticket_currencies()
    print(f"  ticket currencies seeded at login (non-diamond): {ticket}")
    zero_multi = sorted(s for s, v in info.items()
                        if (v["BUY_MULTIPLE_TIMES_PRICE"] == 0 or v["BUY_MULTIPLE_TIMES_PRICE"] == [0, 0]))
    print(f"  boxes with multi price 0 (no 10x draw offered): {zero_multi}")
    print(f"  multi draw count: athlete_requests.multi_count() = {athlete_requests.multi_count(1)} for every box")
    this_week = sorted(s for s, v in info.items() if v.get("IS_THIS_WEEK"))
    print(f"  IS_THIS_WEEK boxes: {[(s, info[s]['KIND']) for s in this_week] or 'none'} (box, KIND)")
    off_sale = sorted(s for s, v in info.items() if not v.get("IS_IN_SALE"))
    print(f"  IS_IN_SALE false: {len(off_sale)} boxes {off_sale[:12]}")
    clocks = {"emulator 2022-04-20": "2022-04-20 12:00:00", "real 2026-11-26": "2026-11-26 00:00:00"}
    print("  clocks: " + "; ".join(f"{k}={v}" for k, v in clocks.items())
          + ". Last monthly box ends 2022.12.30 (LOBBY_FINDINGS, month_dates_probe); not in the extract.")


TS = re.compile(r"^\s*\[(\d\d:\d\d:\d\d)\]")
EVENTS = [
    ("handshake", "Account.handshake ->"),
    ("lobby_data_sent", "Sent Athlete.onLogin + onRoleCreateSuc"),
    ("lobby_ui_burst", "<- Athlete.requestEnterWorldOpenUI"),
    ("queryAvailableSupplement", "<- Athlete.queryAvailableSupplement"),
    ("setHasAlreadyShowSupplyID", "<- Athlete.setHasAlreadyShowSupplyID"),
    ("openSupply*", "<- Athlete.openSupplyBox"),
    ("openSupply*", "<- Athlete.openMultipleSupplyBox"),
]


def _secs(hms):
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s


def scan_logs():
    print("\n== Saved gateway logs (bigworld_gateway/logs/server*.log) ==")
    names = sorted(f for f in os.listdir(LOGS) if f.startswith("server") and f.endswith(".log")) \
        if os.path.isdir(LOGS) else []
    if not names:
        print("  no logs found")
        return
    print(f"  {'file':<36} {'sess':>4} {'hs->UI s (median)':>17} {'UI->1st supply s':>16} "
          f"{'supply q':>8} {'shownID':>7} {'draws':>5}")
    for fn in names:
        sessions, cur, last_ts = [], None, None
        with open(os.path.join(LOGS, fn), encoding="utf-8", errors="replace") as f:
            for line in f:
                m = TS.match(line)
                if m:
                    last_ts = m.group(1)
                    continue
                for key, needle in EVENTS:
                    if needle in line:
                        if key == "handshake":
                            cur = {"handshake": last_ts}
                            sessions.append(cur)
                        elif cur is not None:
                            cur.setdefault(key, last_ts)
                            cur[key + "#"] = cur.get(key + "#", 0) + 1
        ui = [(_secs(s["lobby_ui_burst"]) - _secs(s["handshake"])) % 86400 for s in sessions
              if s.get("handshake") and s.get("lobby_ui_burst")]
        sup = [(_secs(s["queryAvailableSupplement"]) - _secs(s["lobby_ui_burst"])) % 86400 for s in sessions
               if s.get("lobby_ui_burst") and s.get("queryAvailableSupplement")]
        before_ui = sum(1 for s in sessions if s.get("queryAvailableSupplement") and s.get("lobby_ui_burst")
                        and _secs(s["queryAvailableSupplement"]) < _secs(s["lobby_ui_burst"]))
        med = lambda xs: f"{sorted(xs)[len(xs) // 2]} (n={len(xs)})" if xs else "-"
        q = sum(s.get("queryAvailableSupplement#", 0) for s in sessions)
        shown = sum(s.get("setHasAlreadyShowSupplyID#", 0) for s in sessions)
        draws = sum(s.get("openSupply*#", 0) for s in sessions)
        print(f"  {fn:<36} {len(sessions):>4} {med(ui):>17} {med(sup):>16} {q:>8} {shown:>7} {draws:>5}"
              + (f"  ({before_ui} queries before lobby UI)" if before_ui else ""))
    print("  hs->UI: Account.handshake to the client's requestEnterWorldOpenUI burst (lobby UI on_enter;"
          " hall scene load dominates). UI->1st supply: lobby UI to the first queryAvailableSupplement.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logs", action="store_true", help="also scan bigworld_gateway/logs (slow on big logs)")
    ap.add_argument("--no-supply", action="store_true", help="skip the extract check")
    args = ap.parse_args(argv)
    print("RO-101 startup trace (offline; no sockets, no API, no saved_accounts.json)")
    print("env: " + " ".join(f"{k}={os.environ[k]}" for k in
                             ("GAME_DATE", "FRAG_BODY", "HALL_POPUPS", "UNLOCK_ALL", "LOBBY_SWITCHES_OFF")))
    rec = Recorder()
    gate, addr, bundles = build_login_stream(rec)
    supply = build_supply_reply(rec, gate, addr)
    print_table(rec.rows, bundles, supply)
    # Second pass: the same login once caches are warm (bwdefs parse, extract JSON already loaded).
    rec2 = Recorder()
    _, _, bundles2 = build_login_stream(rec2)
    print("\n== Warm second login (process caches filled) ==")
    for label, n, ms in bundles2:
        print(f"  {label:<48} {n:>7} B {ms:>9.3f} ms")
    print("\nNot built offline: Mercury login/encryption, the tutorial Avatar route (SWITCH_TO=avatar),"
          " _unlock_all_batch / _push_appearance (off in config.cmd), the RoS_Server state fetch.")
    if not args.no_supply:
        supply_analysis()
    if args.logs:
        scan_logs()


if __name__ == "__main__":
    main()
