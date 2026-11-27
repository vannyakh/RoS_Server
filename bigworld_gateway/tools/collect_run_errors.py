"""Turn one LDPlayer test run into an error report.

A run folder holds:

* ``server.log``  - the gateway log slice for the run
* ``logcat.txt``  - ``adb logcat -d -v time`` output from the emulator
* ``*.png``       - optional screenshots (listed, not read)

Usage::

    python bigworld_gateway/tools/collect_run_errors.py <run_dir> [--json] [--all-pids]

The Markdown report is printed and written to ``<run_dir>/ERRORS.md``. ``--json`` prints a
machine-readable dict instead (ERRORS.md is still written).

Clocks: server.log ``[HH:MM:SS]`` stamps are the gateway host clock; logcat stamps are the
emulator clock. The two are not aligned, so only the order inside each file is reliable. A
server finding is "in battle" when it comes after the first ``[FLOW] stage -> waiting``. A
client finding is "in battle" when it comes after the client's own battle-entry line
(``ServerConnection::createCellPlayer``) in the same process.

Stdlib only. Reads the files; never touches the emulator, adb or a running server.
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

SEVERITIES = ("CRASH", "BLOCKER", "ERROR", "WARN")
RESEND_STORM = 100          # more RESEND lines than this is a BLOCKER
CLIENT_PACKAGE = "com.netease.chiji"

# ---- logcat patterns -------------------------------------------------------------------------

LOGCAT_LINE = re.compile(r"^(?P<ts>\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+(?P<lvl>[VDIWEFA])/(?P<tag>.*?)\(\s*(?P<pid>\d+)\):\s?(?P<msg>.*)$")
SCRIPT_TAG = "<SCRIPT>"
TB_HEAD = "Traceback (most recent call last):"
TB_FRAME = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\S+)')
SCRIPT_ERROR = re.compile(r"\[ERROR\] Script execution returned the error\s*(?P<what>.*)$")
FATAL_SIGNAL = re.compile(r"Fatal signal (?P<sig>\d+) \((?P<name>\w+)\)(?P<rest>.*)$")
FATAL_THREAD = re.compile(r"in tid (?P<tid>\d+) \((?P<thread>[^)]*)\)")
PROC_DIED = re.compile(r"Process " + re.escape(CLIENT_PACKAGE) + r" \(pid (?P<pid>\d+)\) has died(?P<rest>.*)$")
PROC_START = re.compile(r"Start proc (?P<pid>\d+):" + re.escape(CLIENT_PACKAGE) + r"/")
CLIENT_BATTLE_MARKER = re.compile(r"ServerConnection::createCellPlayer")

# ---- server.log patterns ---------------------------------------------------------------------

SERVER_TS = re.compile(r"^\s*\[(?P<ts>\d\d:\d\d:\d\d)\]")
FLOW_STAGE = re.compile(r"\[FLOW\] stage -> (?P<stage>\w+)(?: \((?P<reason>[^)]*)\))?(?: \| after (?P<after>[\d.]+)s)?")
FLOW_TIMEOUT = re.compile(r"\[FLOW\] TIMEOUT (?P<rest>.*)$")
KV = re.compile(r"(\w+)=(.*?)(?=\s+\w+=|$)")
STALE = re.compile(r"\[SESSION\].*stale channel")
RESEND = re.compile(r"\[(?P<who>[\w ]*?)\s*RESEND\]\s*seq=(?P<seq>\d+)")
MATCH_REQUEST = re.compile(r"matchBattleGround")
RECORD_MATCH = re.compile(r"record_match")
RESULTS_END = re.compile(r"results end\b")
GATEWAY_FAIL = re.compile(r"failed:|Error handling|\[BATTLE SESSION\].*\bfailed\b")


def _normalise(text):
    """Grouping key: numbers, hex and addresses folded so repeats of one error group together."""
    text = re.sub(r"\('[\d.]+', \d+\)", "(ADDR)", text)
    text = re.sub(r"0x[0-9a-fA-F]+", "0xN", text)
    text = re.sub(r"\b[0-9a-fA-F]{8,}\b", "HEX", text)
    return re.sub(r"\d+", "N", text).strip()


ENGINE_FRAME = re.compile(r'File "libclaudia[\\/]')


def _client_frame(frames):
    """Last frame in game code; engine (libclaudia) frames are skipped when game frames exist."""
    game = [x for x in frames if not ENGINE_FRAME.search(x)]
    pick = (game or frames)
    return _frame_label(pick[-1]) if pick else "(no frame)"


def _frame_label(frame_line):
    m = TB_FRAME.match(frame_line)
    if not m:
        return frame_line.strip()
    return "%s line %s %s" % (m.group("file"), m.group("line"), m.group("func"))


class Findings:
    """Grouped findings: one entry per (severity, kind, key) with a count and the first sighting."""

    def __init__(self):
        self._items = OrderedDict()

    def add(self, severity, source, kind, key, title, time=None, line=None, in_battle=None, detail=None):
        k = (severity, kind, key)
        item = self._items.get(k)
        if item is None:
            item = {"severity": severity, "source": source, "kind": kind, "title": title, "count": 0,
                    "first_time": time, "first_line": line, "in_battle": in_battle, "detail": detail or []}
            self._items[k] = item
        item["count"] += 1
        return item

    def items(self):
        return list(self._items.values())


# ---- logcat ----------------------------------------------------------------------------------

def _pick_pid(lines):
    """The client process of the run: the last ``Start proc N:com.netease.chiji/`` in the dump."""
    pid = None
    for raw in lines:
        m = PROC_START.search(raw)
        if m:
            pid = m.group("pid")
    return pid


def parse_logcat(text, all_pids=False):
    lines = text.splitlines()
    pid = None if all_pids else _pick_pid(lines)
    out = {"pid": pid, "tracebacks": [], "script_errors": [], "crashes": [], "battle_marker": None,
           "lines": len(lines)}
    in_battle = {}          # pid -> True once the client entered battle
    open_tb = {}            # pid -> traceback being collected
    for n, raw in enumerate(lines, 1):
        m = LOGCAT_LINE.match(raw)
        if not m:
            continue
        lpid, msg, ts = m.group("pid"), m.group("msg"), m.group("ts")

        died = PROC_DIED.search(msg)
        if died and (pid is None or died.group("pid") == pid):
            out["crashes"].append({"kind": "process_died", "time": ts, "line": n, "pid": died.group("pid"),
                                   "thread": None, "text": msg.strip()})
            continue
        if pid is not None and lpid != pid:
            continue

        fatal = FATAL_SIGNAL.search(msg)
        if fatal:
            t = FATAL_THREAD.search(fatal.group("rest"))
            out["crashes"].append({"kind": "fatal_signal", "time": ts, "line": n, "pid": lpid,
                                   "signal": "%s (%s)" % (fatal.group("sig"), fatal.group("name")),
                                   "thread": t.group("thread") if t else None, "text": msg.strip(),
                                   "in_battle": in_battle.get(lpid, False)})
            continue

        if CLIENT_BATTLE_MARKER.search(msg) and not in_battle.get(lpid):
            in_battle[lpid] = True
            if out["battle_marker"] is None:
                out["battle_marker"] = {"time": ts, "line": n, "pid": lpid}

        se = SCRIPT_ERROR.search(msg)
        if se:
            out["script_errors"].append({"time": ts, "line": n, "what": se.group("what").strip(),
                                         "in_battle": in_battle.get(lpid, False)})
            continue

        if SCRIPT_TAG not in m.group("tag") and SCRIPT_TAG not in raw.split("(")[0]:
            continue
        body = msg.rstrip()
        if body.strip() == TB_HEAD:
            open_tb[lpid] = {"time": ts, "line": n, "frames": [], "in_battle": in_battle.get(lpid, False)}
            continue
        tb = open_tb.get(lpid)
        if tb is None:
            continue
        if TB_FRAME.match(body):
            tb["frames"].append(body.strip())
            continue
        if body.startswith("    ") or not body.strip():      # source line under a frame
            continue
        tb["exception"] = body.strip()
        out["tracebacks"].append(tb)
        del open_tb[lpid]
    return out


# ---- server.log ------------------------------------------------------------------------------

def parse_server(text):
    out = {"stages": [], "timeouts": [], "stale": [], "failures": [], "tracebacks": [],
           "resend": {"lines": 0, "by_who": {}}, "match_requested": None, "record_match": [],
           "results_end": None, "lines": 0}
    lines = text.splitlines()
    out["lines"] = len(lines)
    last_ts = None
    resend_seqs = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        n = i + 1
        i += 1
        tm = SERVER_TS.match(raw)
        if tm:
            last_ts = tm.group("ts")

        if raw.startswith(TB_HEAD):
            frames, exc = [], None
            while i < len(lines) and len(frames) < 200:
                nxt = lines[i]
                if TB_FRAME.match(nxt):
                    frames.append(nxt.strip())
                    i += 1
                elif nxt.startswith("    ") and not SERVER_TS.match(nxt) and frames:
                    i += 1          # source line
                elif nxt.strip() and not nxt.startswith(" "):
                    exc = nxt.strip()
                    i += 1
                    break
                else:
                    break
            out["tracebacks"].append({"time": last_ts, "line": n, "frames": frames, "exception": exc or "?"})
            continue

        st = FLOW_STAGE.search(raw)
        if st:
            out["stages"].append({"stage": st.group("stage"), "reason": st.group("reason") or "",
                                  "after_s": float(st.group("after")) if st.group("after") else None,
                                  "time": last_ts, "line": n})
            continue
        to = FLOW_TIMEOUT.search(raw)
        if to:
            rec = {k: v.strip() for k, v in KV.findall(to.group("rest"))}
            rec.update({"time": last_ts, "line": n})
            out["timeouts"].append(rec)
            continue
        if STALE.search(raw):
            out["stale"].append({"time": last_ts, "line": n, "text": raw.strip()})
            continue
        rs = RESEND.search(raw)
        if rs:
            out["resend"]["lines"] += 1
            who = (rs.group("who") or "?").strip() or "?"
            seqs = resend_seqs.setdefault(who, {})
            seqs[rs.group("seq")] = seqs.get(rs.group("seq"), 0) + 1
            continue
        if MATCH_REQUEST.search(raw) and out["match_requested"] is None:
            out["match_requested"] = {"time": last_ts, "line": n}
        if RECORD_MATCH.search(raw):
            out["record_match"].append({"time": last_ts, "line": n, "text": raw.strip(),
                                        "ok": bool(re.search(r"record_match ok\b", raw))})
            continue
        if RESULTS_END.search(raw):
            out["results_end"] = {"time": last_ts, "line": n, "text": raw.strip()}
            continue
        if GATEWAY_FAIL.search(raw):
            out["failures"].append({"time": last_ts, "line": n, "text": raw.strip()})

    for who, seqs in resend_seqs.items():
        out["resend"]["by_who"][who] = {"lines": sum(seqs.values()), "distinct_seqs": len(seqs),
                                        "max_resends_one_seq": max(seqs.values()) if seqs else 0}
    out["resend"]["distinct_seqs"] = sum(v["distinct_seqs"] for v in out["resend"]["by_who"].values())
    out["resend"]["max_resends_one_seq"] = max(
        [v["max_resends_one_seq"] for v in out["resend"]["by_who"].values()] or [0])
    return out


# ---- classification --------------------------------------------------------------------------

def _server_in_battle(server, line):
    first_wait = next((s["line"] for s in server["stages"] if s["stage"] == "waiting"), None)
    return first_wait is not None and line > first_wait


def classify(server, logcat):
    f = Findings()
    if logcat is not None:
        for c in logcat["crashes"]:
            if c["kind"] == "fatal_signal":
                f.add("CRASH", "logcat", "native_crash", ("sig", c["signal"], c["thread"]),
                      "Fatal signal %s in thread %s" % (c["signal"], c["thread"] or "?"),
                      c["time"], c["line"], c.get("in_battle"), [c["text"]])
            else:
                f.add("CRASH", "logcat", "process_died", ("died", c["pid"]),
                      "Process %s (pid %s) has died" % (CLIENT_PACKAGE, c["pid"]),
                      c["time"], c["line"], None, [c["text"]])
        for tb in logcat["tracebacks"]:
            last = _frame_label(tb["frames"][-1]) if tb["frames"] else "(no frame)"
            where = _client_frame(tb["frames"])
            exc = tb.get("exception", "?")
            sev = "ERROR" if tb["in_battle"] else "WARN"
            item = f.add(sev, "logcat", "client_traceback", (last, exc), "%s: %s" % (where, exc),
                         tb["time"], tb["line"], tb["in_battle"], [_frame_label(x) for x in tb["frames"]])
            item["client_frame"], item["last_frame"], item["exception"] = where, last, exc
        for se in logcat["script_errors"]:
            sev = "ERROR" if se["in_battle"] else "WARN"
            f.add(sev, "logcat", "script_error", se["what"],
                  "[ERROR] Script execution returned the error %s" % se["what"],
                  se["time"], se["line"], se["in_battle"])

    if server is not None:
        stages = [s["stage"] for s in server["stages"]]
        last = stages[-1] if stages else None
        if server["match_requested"] and last != "lobby":
            f.add("BLOCKER", "server", "flow_stopped", "flow",
                  "Match requested but flow stopped at stage %r (never reached lobby)" % (last or "none"),
                  server["match_requested"]["time"], server["match_requested"]["line"], last is not None)
        for to in server["timeouts"]:
            f.add("BLOCKER", "server", "flow_timeout", to.get("stage"),
                  "FLOW TIMEOUT stage=%s %s" % (to.get("stage"), to.get("reason", "")),
                  to["time"], to["line"], True,
                  ["%s=%s" % (k, v) for k, v in to.items() if k not in ("time", "line")])
        for s in server["stale"]:
            f.add("BLOCKER", "server", "stale_channel", _normalise(s["text"]), s["text"],
                  s["time"], s["line"], _server_in_battle(server, s["line"]))
        rs = server["resend"]
        if rs["lines"] > RESEND_STORM:
            f.add("BLOCKER", "server", "resend_storm", "resend",
                  "RESEND storm: %d RESEND lines, %d distinct seqs, max %d resends of one seq"
                  % (rs["lines"], rs["distinct_seqs"], rs["max_resends_one_seq"]),
                  None, None, None,
                  ["%s: %d lines, %d seqs, max %d of one seq"
                   % (w, v["lines"], v["distinct_seqs"], v["max_resends_one_seq"]) for w, v in rs["by_who"].items()])
        for tb in server["tracebacks"]:
            last_frame = _frame_label(tb["frames"][-1]) if tb["frames"] else "(no frame)"
            f.add("ERROR", "server", "gateway_traceback", (last_frame, _normalise(tb["exception"])),
                  "%s: %s" % (last_frame, tb["exception"]), tb["time"], tb["line"],
                  _server_in_battle(server, tb["line"]), [_frame_label(x) for x in tb["frames"]])
        for fl in server["failures"]:
            f.add("ERROR", "server", "gateway_failure", _normalise(fl["text"]), fl["text"],
                  fl["time"], fl["line"], _server_in_battle(server, fl["line"]))
        for rm in server["record_match"]:
            if not rm["ok"]:
                f.add("ERROR", "server", "record_match", _normalise(rm["text"]), rm["text"],
                      rm["time"], rm["line"], True)
    return f.items()


# ---- report ----------------------------------------------------------------------------------

def collect(run_dir, all_pids=False):
    def read(name):
        p = os.path.join(run_dir, name)
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    server_text, logcat_text = read("server.log"), read("logcat.txt")
    server = parse_server(server_text) if server_text is not None else None
    logcat = parse_logcat(logcat_text, all_pids=all_pids) if logcat_text is not None else None
    findings = classify(server, logcat)
    counts = {s: sum(1 for x in findings if x["severity"] == s) for s in SEVERITIES}
    occurrences = {s: sum(x["count"] for x in findings if x["severity"] == s) for s in SEVERITIES}
    notes = ["server.log [HH:MM:SS] is the gateway clock and logcat time is the emulator clock; they are "
             "not aligned, so only the order inside each file is reliable."]
    if server is None:
        notes.append("server.log missing.")
    if logcat is None:
        notes.append("logcat.txt missing.")
    else:
        if logcat["pid"]:
            notes.append("logcat limited to the last %s process (pid %s); use --all-pids for every process."
                         % (CLIENT_PACKAGE, logcat["pid"]))
        if logcat["battle_marker"] is None:
            notes.append("No client battle-entry line (createCellPlayer) in logcat: client findings count as lobby.")
    stages = server["stages"] if server else []
    return {
        "run_dir": os.path.abspath(run_dir),
        "stages_reached": [s["stage"] for s in stages],
        "last_stage": stages[-1]["stage"] if stages else None,
        "counts": counts,
        "occurrences": occurrences,
        "findings": findings,
        "flow": stages,
        "timeouts": server["timeouts"] if server else [],
        "match": {
            "requested": server["match_requested"] if server else None,
            "record_match": server["record_match"] if server else [],
            "results_end": server["results_end"] if server else None,
        },
        "resend": server["resend"] if server else None,
        "client": {"pid": logcat["pid"], "battle_marker": logcat["battle_marker"]} if logcat else None,
        "screenshots": sorted(x for x in os.listdir(run_dir) if x.lower().endswith(".png")),
        "notes": notes,
    }


def _where(item):
    bits = []
    if item["first_time"]:
        bits.append(item["first_time"])
    if item["first_line"]:
        bits.append("%s:%d" % ("logcat.txt" if item["source"] == "logcat" else "server.log", item["first_line"]))
    if item["in_battle"] is not None:
        bits.append("in battle" if item["in_battle"] else "lobby")
    return ", ".join(bits)


def render_markdown(r):
    out = ["# Run errors: %s" % os.path.basename(r["run_dir"].rstrip("\\/")), ""]
    c, o = r["counts"], r["occurrences"]
    out.append("**Summary:** stages %s (last: %s) | %s"
               % (" -> ".join(r["stages_reached"]) or "none", r["last_stage"] or "none",
                  ", ".join("%s %d (%d hits)" % (s, c[s], o[s]) for s in SEVERITIES)))
    out.append("")
    for n in r["notes"]:
        out.append("> %s" % n)
    out.append("")
    for sev in SEVERITIES:
        items = [x for x in r["findings"] if x["severity"] == sev]
        out.append("## %s (%d)" % (sev, len(items)))
        out.append("")
        if not items:
            out.append("None.")
            out.append("")
            continue
        for x in sorted(items, key=lambda x: -x["count"]):
            out.append("- **%s** x%d - %s [%s]" % (x["kind"], x["count"], x["title"], _where(x)))
            for d in x["detail"][-6:]:
                out.append("    - `%s`" % d)
        out.append("")
    out.append("## Flow timeline")
    out.append("")
    if r["flow"]:
        out.append("| # | time | stage | reason | after |")
        out.append("|---|------|-------|--------|-------|")
        for i, s in enumerate(r["flow"], 1):
            out.append("| %d | %s | %s | %s | %s |" % (i, s["time"] or "", s["stage"], s["reason"],
                                                     "" if s["after_s"] is None else "%.1fs" % s["after_s"]))
    else:
        out.append("No `[FLOW] stage` lines.")
    out.append("")
    m = r["match"]
    if m["requested"]:
        out.append("- matchBattleGround first seen: %s (server.log:%d)" % (m["requested"]["time"], m["requested"]["line"]))
    for rm in m["record_match"]:
        out.append("- record_match: `%s`" % rm["text"])
    if m["results_end"]:
        out.append("- results: `%s`" % m["results_end"]["text"])
    if r["resend"]:
        rs = r["resend"]
        out.append("- RESEND: %d lines, %d distinct seqs, max %d resends of one seq"
                   % (rs["lines"], rs["distinct_seqs"], rs["max_resends_one_seq"]))
    if r["client"] and r["client"]["battle_marker"]:
        bm = r["client"]["battle_marker"]
        out.append("- client battle entry (device clock): %s (logcat.txt:%d)" % (bm["time"], bm["line"]))
    if r["screenshots"]:
        out.append("- screenshots: %s" % ", ".join(r["screenshots"]))
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--json", action="store_true", help="print a machine-readable dict")
    ap.add_argument("--all-pids", action="store_true", help="scan every logcat process, not only the last client")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.run_dir):
        print("not a folder: %s" % args.run_dir, file=sys.stderr)
        return 2
    report = collect(args.run_dir, all_pids=args.all_pids)
    md = render_markdown(report)
    with open(os.path.join(args.run_dir, "ERRORS.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        sys.stdout.write(md if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("utf")
                         else md.encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
