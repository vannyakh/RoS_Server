"""In-memory latency and payload-size recorder for gateway handlers.

Each name keeps its last `maxlen` samples (collections.deque, so memory is bounded). Recording
takes one lock and appends; nothing touches the disk on the hot path. An optional log callback
(for example a logging.Logger method) runs on a background thread fed by a bounded queue; when
the queue is full, samples are dropped from the log (never from the in-memory summary) and
counted in `dropped`.

    mon = Monitor()
    with mon.measure("queryAvailableSupplement") as m:
        payload = build()
        m.bytes = len(payload)
    mon.summary()  # {"queryAvailableSupplement": {"count", "p50_ms", "p95_ms", "max_ms", ...}}
"""
import functools
import queue
import threading
import time
from collections import deque

DEFAULT_MAXLEN = 1024


def percentile(sorted_values, pct):
    """Nearest-rank percentile of an ascending list (pct in 0..100); None for an empty list."""
    if not sorted_values:
        return None
    if pct <= 0:
        return sorted_values[0]
    rank = -(-pct * len(sorted_values) // 100)  # ceil(pct/100 * n)
    return sorted_values[min(int(rank), len(sorted_values)) - 1]


class _Measure:
    __slots__ = ("bytes", "_mon", "_name", "_t0")

    def __init__(self, mon, name):
        self._mon = mon
        self._name = name
        self.bytes = 0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self._mon.record(self._name, time.perf_counter() - self._t0, self.bytes)
        return False


class Monitor:
    def __init__(self, maxlen=DEFAULT_MAXLEN, log=None, log_queue=1024):
        self.maxlen = maxlen
        self._lock = threading.Lock()
        self._samples = {}   # name -> deque[(seconds, bytes)]
        self._totals = {}    # name -> calls ever recorded (not bounded by maxlen)
        self.dropped = 0
        self._log = log
        self._queue = None
        self._thread = None
        if log is not None:
            self._queue = queue.Queue(maxsize=log_queue)
            self._thread = threading.Thread(target=self._drain, name="perf-monitor-log",
                                            daemon=True)
            self._thread.start()

    def record(self, name, seconds, nbytes=0):
        with self._lock:
            ring = self._samples.get(name)
            if ring is None:
                ring = self._samples[name] = deque(maxlen=self.maxlen)
            ring.append((seconds, nbytes))
            self._totals[name] = self._totals.get(name, 0) + 1
        if self._queue is not None:
            try:
                self._queue.put_nowait((name, seconds, nbytes))
            except queue.Full:
                with self._lock:
                    self.dropped += 1

    def measure(self, name):
        """Context manager; set `.bytes` on the yielded object to record a payload size."""
        return _Measure(self, name)

    def timed(self, name=None, size=None):
        """Decorator. `size(result)` gives the payload bytes; default len() of bytes results."""
        def wrap(fn):
            label = name or fn.__name__

            @functools.wraps(fn)
            def inner(*args, **kwargs):
                t0 = time.perf_counter()
                result = fn(*args, **kwargs)
                elapsed = time.perf_counter() - t0
                if size is not None:
                    nbytes = size(result)
                elif isinstance(result, (bytes, bytearray)):
                    nbytes = len(result)
                else:
                    nbytes = 0
                self.record(label, elapsed, nbytes)
                return result
            return inner
        return wrap

    def summary(self):
        """{name: {count, total, p50_ms, p95_ms, max_ms, mean_ms, mean_bytes}} over the window."""
        with self._lock:
            snap = {name: list(ring) for name, ring in self._samples.items()}
            totals = dict(self._totals)
        out = {}
        for name, samples in snap.items():
            secs = sorted(s for s, _ in samples)
            n = len(samples)
            out[name] = {
                "count": n,
                "total": totals.get(name, n),
                "p50_ms": percentile(secs, 50) * 1000.0,
                "p95_ms": percentile(secs, 95) * 1000.0,
                "max_ms": secs[-1] * 1000.0,
                "mean_ms": sum(secs) / n * 1000.0,
                "mean_bytes": sum(b for _, b in samples) / n,
            }
        return out

    def reset(self):
        with self._lock:
            self._samples.clear()
            self._totals.clear()
            self.dropped = 0

    def _drain(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            name, seconds, nbytes = item
            try:
                self._log("perf %s %.3f ms %d B" % (name, seconds * 1000.0, nbytes))
            except Exception:  # a broken log sink must not kill the drain thread
                pass

    def close(self, timeout=1.0):
        """Stop the log thread after it writes what is queued."""
        if self._thread is not None:
            try:
                self._queue.put(None, timeout=timeout)
            except queue.Full:
                pass  # daemon thread; it ends with the process
            self._thread.join(timeout)
            self._thread = None


# Process-wide monitor the gateway can share.
MONITOR = Monitor()
