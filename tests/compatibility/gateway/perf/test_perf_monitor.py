"""perf_monitor keeps a bounded, thread-safe window of latency and payload samples."""

import threading
import time

import pytest

import perf_monitor
from perf_monitor import Monitor, percentile


def test_percentile_nearest_rank():
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile(values, 100) == 100
    assert percentile([7], 95) == 7
    assert percentile([], 50) is None
    assert percentile([1, 2, 3, 4], 50) == 2


def test_summary_on_known_samples():
    mon = Monitor(maxlen=1000)
    for ms in range(1, 101):  # 1..100 ms, bytes = 10 * ms
        mon.record("q", ms / 1000.0, ms * 10)
    s = mon.summary()["q"]
    assert s["count"] == 100
    assert s["p50_ms"] == pytest.approx(50.0)
    assert s["p95_ms"] == pytest.approx(95.0)
    assert s["max_ms"] == pytest.approx(100.0)
    assert s["mean_ms"] == pytest.approx(50.5)
    assert s["mean_bytes"] == pytest.approx(505.0)


def test_ring_is_bounded():
    mon = Monitor(maxlen=10)
    for i in range(1000):
        mon.record("q", i / 1000.0, i)
    s = mon.summary()["q"]
    assert s["count"] == 10
    assert s["total"] == 1000
    assert s["max_ms"] == pytest.approx(999.0)
    assert s["p50_ms"] == pytest.approx(994.0)  # window holds 990..999


def test_concurrent_records_are_all_counted():
    mon = Monitor(maxlen=100000)
    threads_n, per_thread = 8, 5000
    start = threading.Barrier(threads_n)

    def worker(k):
        start.wait()
        for i in range(per_thread):
            mon.record("name%d" % (k % 2), 0.001, 1)

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    s = mon.summary()
    assert s["name0"]["count"] + s["name1"]["count"] == threads_n * per_thread
    assert s["name0"]["total"] == threads_n // 2 * per_thread


def test_concurrent_records_stay_bounded():
    mon = Monitor(maxlen=50)

    def worker():
        for _ in range(2000):
            mon.record("q", 0.0, 0)
            mon.summary()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    s = mon.summary()["q"]
    assert s["count"] == 50
    assert s["total"] == 12000


def test_measure_context_and_decorator():
    mon = Monitor()
    with mon.measure("ctx") as m:
        time.sleep(0.002)
        m.bytes = 123

    @mon.timed("deco")
    def build():
        return b"x" * 40

    assert build() == b"x" * 40
    s = mon.summary()
    assert s["ctx"]["count"] == 1 and s["ctx"]["mean_bytes"] == 123
    assert s["ctx"]["max_ms"] >= 1.0
    assert s["deco"]["mean_bytes"] == 40


def test_log_runs_off_thread_and_drops_when_full():
    seen = []
    gate = threading.Event()

    def slow_log(line):
        gate.wait(2)
        seen.append((threading.current_thread().name, line))

    mon = Monitor(log=slow_log, log_queue=2)
    t0 = time.perf_counter()
    for _ in range(20):
        mon.record("q", 0.001, 5)
    assert time.perf_counter() - t0 < 0.5  # record() never waits on the log sink
    assert mon.summary()["q"]["count"] == 20
    assert mon.dropped > 0
    gate.set()
    mon.close()
    assert seen
    assert all(name == "perf-monitor-log" for name, _ in seen)
    assert seen[0][1].startswith("perf q ")


def test_module_monitor_exists():
    assert isinstance(perf_monitor.MONITOR, Monitor)
