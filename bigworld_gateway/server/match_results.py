"""Match results kept by the gateway (checklist 19.11 survival time, 19.16 save match result).

Match.finish() calls save() once per match. Each result is one JSON line in match_results.jsonl next to
this file (MATCH_RESULTS_FILE overrides the path). Nothing reads it back yet: the profile record screens
(lane 1, profile_screens.py) and rewards (19.12-19.17) can build on it.
"""
import json
import os
import time

PATH = os.environ.get("MATCH_RESULTS_FILE",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_results.jsonl"))


def survival_seconds(match, now=None):
    """Seconds from the match start (avatar entered the battle) to now."""
    t0 = getattr(match, "t_start", None)
    return int((now or time.time()) - t0) if t0 else 0


def save(match, gid, nickname, rank, total, won, log=print):
    rec = {"time": int(time.time()), "gid": gid, "nickname": nickname, "map": getattr(match, "map_id", 0),
           "rank": rank, "total": total, "won": bool(won), "survival_s": survival_seconds(match),
           "kills": getattr(match, "kills", 0), "collected": getattr(match, "collected", 0),
           "cause": "win" if won else getattr(match, "death_cause", "zone")}
    try:
        with open(PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        log("      [BATTLE] result saved: %s" % json.dumps(rec))
    except OSError as e:
        log("      [BATTLE] result save failed: %r" % e)
    return rec


def history(gid=None):
    """Saved results, oldest first (optionally for one gid)."""
    if not os.path.exists(PATH):
        return []
    out = []
    with open(PATH, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if gid is None or rec.get("gid") == gid:
                out.append(rec)
    return out
