"""supply_cache returns the exact queryAvailableSupplement argument bytes, built once."""

import importlib
import random
import threading

import pytest

import supply_cache


@pytest.fixture(autouse=True)
def athlete_requests():
    """The athlete_requests module supply_cache will see at call time. Other test files pop or
    reload it, so bind it per test (not at collection) and start each test with an empty cache."""
    supply_cache.invalidate()
    yield importlib.import_module("athlete_requests")
    supply_cache.invalidate()


def test_blob_equals_uncached_reply_bytes(athlete_requests):
    expected = athlete_requests.py(athlete_requests.supplement_info())
    assert supply_cache.supplement_info_blob() == expected
    assert len(expected) > 10000  # the real catalog (about 17 KB pickled), not an empty dict


def test_blob_built_once(athlete_requests, monkeypatch):
    calls = []
    real_py = athlete_requests.py

    def counting_py(obj):
        calls.append(1)
        return real_py(obj)

    monkeypatch.setattr(athlete_requests, "py", counting_py)
    first = supply_cache.supplement_info_blob()
    for _ in range(50):
        assert supply_cache.supplement_info_blob() is first
    assert len(calls) == 1
    assert supply_cache.build_count() == 1


def test_blob_built_once_under_threads(athlete_requests, monkeypatch):
    calls = []
    real_py = athlete_requests.py
    monkeypatch.setattr(athlete_requests, "py", lambda o: (calls.append(1), real_py(o))[1])
    start = threading.Barrier(16)
    results = []

    def worker():
        start.wait()
        results.append(supply_cache.supplement_info_blob())

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert len({id(r) for r in results}) == 1


def test_invalidate_rebuilds(athlete_requests, monkeypatch):
    first = supply_cache.supplement_info_blob()
    supply_cache.invalidate()
    assert supply_cache.build_count() == 0
    monkeypatch.setattr(athlete_requests, "py", lambda o: b"rebuilt")
    assert supply_cache.supplement_info_blob() == b"rebuilt"
    assert supply_cache.build_count() == 1
    assert first != b"rebuilt"


def _box_ids(athlete_requests):
    info = athlete_requests.supplement_info()
    return sorted(s for s in info if athlete_requests.supplement_prizes(s))


def test_prize_pool_matches_supplement_prizes(athlete_requests):
    sids = _box_ids(athlete_requests)
    assert sids
    for sid in sids:
        assert supply_cache.prize_pool(sid) == tuple(athlete_requests.supplement_prizes(sid))
    assert supply_cache.prize_pool(-1) == ()


def test_draw_same_as_uncached_with_seeded_rng(athlete_requests):
    for sid in _box_ids(athlete_requests):
        for count in (1, athlete_requests.multi_count(sid)):
            a = athlete_requests.draw(sid, count, random.Random(sid))
            b = supply_cache.draw(sid, count, random.Random(sid))
            assert a == b
            assert len(b) == count
    assert supply_cache.draw(-1, 10) == []
