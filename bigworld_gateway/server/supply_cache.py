"""Pre-serialized Supply catalog for the queryAvailableSupplement reply.

athlete_requests.supplement_info() is static data loaded once from extract/supplement_info.json,
but the reply re-pickles it (17 KB pickled, from a 62 KB JSON extract) every time the client
opens Supply. This module builds the reply argument once: supplement_info_blob() == athlete_requests.py(athlete_requests
.supplement_info()), byte for byte. Prize pools are cached as tuples per box id so draw() does not
look the pool up and copy it on every call; draw() makes the same rng calls as
athlete_requests.draw, so a seeded rng gives the same prizes.

invalidate() drops everything (tests, or a reload of the extract files).
"""
import random
import threading

_lock = threading.Lock()
_info_blob = None
_pools = {}
_builds = 0  # times the supplement blob was built; tests read it through build_count()


def _reqs():
    # Resolve through sys.modules at call time: tests reload or drop athlete_requests.
    import athlete_requests
    return athlete_requests


def supplement_info_blob():
    """py(supplement_info()) bytes, built once per process (or once per invalidate())."""
    global _info_blob, _builds
    data = _info_blob
    if data is not None:
        return data
    with _lock:
        if _info_blob is None:
            reqs = _reqs()
            _info_blob = reqs.py(reqs.supplement_info_client())
            _builds += 1
        return _info_blob


def prize_pool(sid):
    """Tuple of prop ids box `sid` can award (athlete_requests.supplement_prizes, frozen)."""
    sid = int(sid)
    pool = _pools.get(sid)
    if pool is not None:
        return pool
    with _lock:
        pool = _pools.get(sid)
        if pool is None:
            pool = tuple(_reqs().supplement_prizes(sid))
            _pools[sid] = pool
        return pool


def draw(sid, count, rng=random):
    """Same result as athlete_requests.draw(sid, count, rng), from the cached pool."""
    pool = prize_pool(sid)
    if not pool:
        return []
    choice = rng.choice
    return [choice(pool) for _ in range(count)]


def build_count():
    return _builds


def invalidate():
    """Forget the cached blob and pools; the next call rebuilds them."""
    global _info_blob, _builds
    with _lock:
        _info_blob = None
        _pools.clear()
        _builds = 0


def warm():
    """Build the supplement catalogue blob at process start so the first Supply open is not cold."""
    supplement_info_blob()
