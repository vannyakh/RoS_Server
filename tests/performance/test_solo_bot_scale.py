"""RO-112: Gateway offline scale probe for Solo BR static Robot bots (N=9 gate).

Measures MatchSession bot spawn enqueue cost using battle/modules/bots.py and solo_fill
defaults. This is a disposable offline bench, not a live Mercury gateway process and not
original Rules of Survival capacity.
"""

from __future__ import annotations

import importlib.util
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY_SERVER = ROOT / "bigworld_gateway" / "server"
REPORT = ROOT / "reports" / "performance" / "solo_bot_scale.json"
DOC = ROOT / "docs" / "performance" / "SOLO_BOT_SCALE.md"

ADDR = ("127.0.0.1", 25001)
ITERATIONS_N9 = 50
WARMUP = 5
SCALE_TARGETS = (29, 59, 119)
GATE_BOT_COUNT = 9

if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_BOTS_MOD = None


def _bots_mod():
    global _BOTS_MOD
    if _BOTS_MOD is None:
        _BOTS_MOD = _load_module(
            "battle.modules.bots",
            GATEWAY_SERVER / "battle" / "modules" / "bots.py",
        )
    return _BOTS_MOD


def _spawn_cycle(*, bot_count: int, seed: int = 69):
    """One spawn + teardown; returns timing ms and wire stats."""
    from battle.session import MatchSession

    bots_mod = _bots_mod()
    sent: list[bytes] = []

    class _Fill:
        def __init__(self):
            self.bot_count = bot_count
            self.human_count = 1

        @property
        def alive_num(self):
            return self.human_count + self.bot_count

    t0 = time.perf_counter()
    session = MatchSession(ADDR, lambda body: sent.append(body))
    session.solo_fill = _Fill()
    mod = bots_mod.BotModule(session, bot_count=bot_count, seed=seed)
    mod.start()
    spawn_ms = (time.perf_counter() - t0) * 1000.0
    spawn_packets = len(sent)
    spawn_bytes = sum(len(b) for b in sent)
    # Expected: N createEntity (+ enterAoI) blobs + 1 aliveNum update.
    assert spawn_packets == bot_count + 1, (bot_count, spawn_packets)

    t1 = time.perf_counter()
    session.close()
    teardown_ms = (time.perf_counter() - t1) * 1000.0

    return {
        "spawn_ms": spawn_ms,
        "teardown_ms": teardown_ms,
        "wire_bytes_spawn": spawn_bytes,
        "wire_packets_spawn": spawn_packets,
        "wire_bytes_total": sum(len(b) for b in sent),
        "wire_packets_total": len(sent),
        "bot_ids": len(mod.bot_ids),
    }


def _percentile(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    idx = max(0, min(len(sorted_samples) - 1, int(len(sorted_samples) * pct) - 1))
    return sorted_samples[idx]


def _summarize(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "mean_ms": round(statistics.fmean(ordered), 4),
        "p50_ms": round(statistics.median(ordered), 4),
        "p95_ms": round(_percentile(ordered, 0.95), 4),
        "max_ms": round(ordered[-1], 4),
    }


def _bench_n(bot_count: int, *, iterations: int) -> dict:
    for _ in range(WARMUP):
        _spawn_cycle(bot_count=bot_count)
    spawn_samples: list[float] = []
    teardown_samples: list[float] = []
    wire_bytes: list[int] = []
    wire_packets: list[int] = []
    for _ in range(iterations):
        row = _spawn_cycle(bot_count=bot_count)
        spawn_samples.append(row["spawn_ms"])
        teardown_samples.append(row["teardown_ms"])
        wire_bytes.append(row["wire_bytes_spawn"])
        wire_packets.append(row["wire_packets_spawn"])
    return {
        "bot_count": bot_count,
        "iterations": iterations,
        "warmup": WARMUP,
        "spawn": _summarize(spawn_samples),
        "teardown": _summarize(teardown_samples),
        "wire_bytes_per_cycle": {
            "mean": int(round(statistics.fmean(wire_bytes))),
            "min": min(wire_bytes),
            "max": max(wire_bytes),
        },
        "wire_packets_per_cycle": {
            "mean": round(statistics.fmean(wire_packets), 2),
            "value": wire_packets[0],
        },
    }


def _environment() -> dict:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def _write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_doc(payload: dict) -> None:
    gate = payload["gates"]["n9"]
    lines = [
        "# Solo bot scale gates (RO-112)",
        "",
        "Gateway-local **offline** measurement for static Robot (type 58) bot spawns via",
        "`bigworld_gateway/server/battle/modules/bots.py`. Uses `MatchSession` enqueue only —",
        "no live Mercury socket, no LLM bots, **no original RoS capacity claim**.",
        "",
        "## Scope",
        "",
        "| Item | Detail |",
        "| --- | --- |",
        "| Measured gate | **N = 9** (first-playable default from RO-110 / solo_fill) |",
        "| Later targets | 29, 59, 119 — listed as **NOT measured** until a disposable run exists |",
        "| FastAPI / Locust | Out of scope; see `docs/performance/PERFORMANCE_BASELINE.md` |",
        "",
        "## N = 9 measured run",
        "",
        f"- Measured at: `{payload['measured_at']}`",
        f"- Iterations: **{gate['iterations']}** spawn+teardown cycles (warmup **{gate['warmup']}**)",
        f"- Spawn enqueue: mean **{gate['spawn']['mean_ms']} ms**, p50 **{gate['spawn']['p50_ms']} ms**, "
        f"p95 **{gate['spawn']['p95_ms']} ms**",
        f"- Teardown (leaveAoI): mean **{gate['teardown']['mean_ms']} ms**, p95 **{gate['teardown']['p95_ms']} ms**",
        f"- Wire per cycle: **{gate['wire_packets_per_cycle']['value']}** packets, "
        f"**{gate['wire_bytes_per_cycle']['mean']}** bytes total",
        f"- Process RSS delta during bench: **{payload['process']['rss_delta_mb']} MB** "
        f"(start **{payload['process']['rss_start_mb']} MB** → end **{payload['process']['rss_end_mb']} MB**)",
        f"- CPU sample (pytest process): **{payload['process']['cpu_percent']}%**",
        "",
        "Two users for 10 seconds in Locust is unrelated. `MAX_PLAYERS_PER_MATCH` is not used here.",
        "",
        "## Scale targets (NOT measured)",
        "",
    ]
    for label, entry in payload["gates"]["future"].items():
        lines.append(
            f"- **N = {entry['bot_count']}** — status: **{entry['status']}**. {entry['note']}"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -m pytest tests/performance/test_solo_bot_scale.py -q",
            ".\\.venv\\Scripts\\python.exe -m pytest tests/compatibility/gateway/bots -q",
            "```",
            "",
            "Report: `reports/performance/solo_bot_scale.json`.",
            "",
        ]
    )
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines), encoding="utf-8")


def test_solo_bot_scale_n9_measured_and_reported():
    """Disposable offline gateway bot spawn bench for the N=9 gate."""
    proc = psutil.Process()
    rss_start = proc.memory_info().rss
    cpu_start = proc.cpu_percent(interval=None)

    t_wall = time.perf_counter()
    gate_n9 = _bench_n(GATE_BOT_COUNT, iterations=ITERATIONS_N9)
    wall_s = round(time.perf_counter() - t_wall, 3)

    # Single probe per future target — documented, not a passed gate.
    future = {}
    for n in SCALE_TARGETS:
        row = _spawn_cycle(bot_count=n)
        future[f"n{n}"] = {
            "bot_count": n,
            "status": "NOT measured",
            "note": "Single offline probe only; no iterative gate run.",
            "probe_spawn_ms": round(row["spawn_ms"], 4),
            "probe_wire_bytes_spawn": row["wire_bytes_spawn"],
            "probe_wire_packets_spawn": row["wire_packets_spawn"],
        }

    rss_end = proc.memory_info().rss
    cpu_pct = proc.cpu_percent(interval=0.1)
    if cpu_start is not None:
        pass  # first call primes psutil; second sample is reported

    payload = {
        "benchmark": "solo_bot_scale",
        "task": "RO-112",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python -m pytest tests/performance/test_solo_bot_scale.py -q",
        "environment": _environment(),
        "notes": [
            "Offline MatchSession enqueue via bots.py; not a live gateway process load test.",
            "N=9 gate uses 50 iterations; 29/59/119 are single probes only.",
            "No secrets; no original-compatibility claim.",
        ],
        "process": {
            "rss_start_mb": round(rss_start / (1024 * 1024), 2),
            "rss_end_mb": round(rss_end / (1024 * 1024), 2),
            "rss_delta_mb": round((rss_end - rss_start) / (1024 * 1024), 2),
            "cpu_percent": round(cpu_pct, 2),
            "wall_s_n9_bench": wall_s,
        },
        "gates": {
            "n9": {**gate_n9, "status": "measured", "human_count": 1},
            "future": future,
        },
    }
    _write_report(payload)
    _write_doc(payload)

    assert gate_n9["spawn"]["count"] == ITERATIONS_N9
    assert gate_n9["wire_packets_per_cycle"]["value"] == GATE_BOT_COUNT + 1  # spawn only
    assert gate_n9["spawn"]["mean_ms"] < 5000, "spawn mean unexpectedly high"
    assert REPORT.is_file()
    assert DOC.is_file()