"""createBasePlayer(Athlete) and the login bundle built with the process-wide .def cache
(bwdefs.shared() + Defs.base_client_defaults) must be byte-identical to a fresh, uncached build
that parses the .def files again and encodes every default per call (the pre-cache algorithm,
copied below). Only per-process constants are cached: per-account values still change the bytes."""

import itertools
import struct

import pytest

FIXED_NOW = 1650456000.0      # 2022-04-20 12:00:00 UTC (config.cmd GAME_DATE)


def uncached_stream_for(defs, entity, overrides=None, log=None, props=None):
    """bwdefs.stream_for before RO-105 (no cache): parse, resolve and encode per call."""
    import bwdefs
    out = b""
    for prop, ttext, flags, owner in (props if props is not None else defs.base_client_props(entity)):
        t = defs.resolve(ttext)
        val = (overrides or {}).get(prop)
        enc = val if val is not None else bwdefs.encode_default(t, defs.defaults.get(prop))
        if log is not None:
            log.append((prop, owner, t[0], len(enc)))
        out += enc
    return out


def _repeatable(gw, monkeypatch):
    """Fixed game clock and item uuids, reset before each build."""
    counter = itertools.count()
    monkeypatch.setattr(gw.os, "urandom", lambda n: bytes([next(counter) & 0xFF]) * n)
    monkeypatch.setattr(gw.athlete_requests, "game_now", lambda: FIXED_NOW)


def _build(gw, monkeypatch, cached):
    _repeatable(gw, monkeypatch)
    gw._ATHLETE_METHODS = None
    if cached:
        cbp = gw.athlete_create_message()
    else:
        with monkeypatch.context() as m:
            m.setattr(gw.bwdefs, "shared", lambda: gw.bwdefs.Defs())
            m.setattr(gw.bwdefs, "stream_for", uncached_stream_for)
            cbp = gw.athlete_create_message()
            gate = gw.GateUDP(25000)
            lobby = gate._lobby_data_calls()
            gw._ATHLETE_METHODS = None
            return cbp, lobby
    gate = gw.GateUDP(25000)
    return cbp, gate._lobby_data_calls()


def _existing_account(gw):
    gw.save_account("default", {"name": "Raven", "char_type": 20001})
    gw.save_account(gw._inventory_key(), {
        "yuanbao": 4321, "items": [391085, 15, 16, 102003],
        "outfit": {"body": [102003], "theme": 270000}, "recent_got": [15, 16]})
    gw.save_account(gw._portrait_key(), "file-1234")
    gw.save_account("supply_push", {"id": 9778})


@pytest.mark.parametrize("account", ["new", "existing"])
def test_cached_login_bytes_equal_a_fresh_uncached_build(gw, monkeypatch, account):
    if account == "existing":
        _existing_account(gw)
        monkeypatch.setenv("ATHLETE_SEED_ITEMS", "15:2,16")
    fresh = _build(gw, monkeypatch, cached=False)
    cold = _build(gw, monkeypatch, cached=True)       # fills the process-wide cache
    warm = _build(gw, monkeypatch, cached=True)       # served from it
    assert cold == fresh
    assert warm == fresh


def test_per_account_values_are_not_cached(gw, monkeypatch):
    first, _ = _build(gw, monkeypatch, cached=True)
    _existing_account(gw)
    second, _ = _build(gw, monkeypatch, cached=True)
    assert second != first
    assert b"Raven" in second and b"Raven" not in first
    fresh, _ = _build(gw, monkeypatch, cached=False)
    assert second == fresh


def test_defs_are_parsed_once_per_process(gw, monkeypatch):
    shared = gw.bwdefs.shared()
    assert gw.bwdefs.shared() is shared
    gw.athlete_create_message()
    parses = []
    real = gw.bwdefs.Defs.properties
    monkeypatch.setattr(gw.bwdefs.Defs, "properties",
                        lambda self, *a, **k: parses.append(a) or real(self, *a, **k))
    monkeypatch.setattr(gw.bwdefs, "Defs", lambda *a, **k: pytest.fail("Defs() rebuilt"))
    gw.athlete_create_message()
    assert parses == []


def test_cached_stream_matches_uncached_for_every_athlete_default(gw):
    """No overrides: the default Athlete stream and its property log are the same."""
    log_cached, log_fresh = [], []
    cached = gw.bwdefs.stream_for(gw.bwdefs.shared(), "Athlete", None, log_cached)
    fresh = uncached_stream_for(gw.bwdefs.Defs(), "Athlete", None, log_fresh)
    assert cached == fresh and log_cached == log_fresh
    assert len(log_cached) == 720


def test_create_base_player_header(gw, monkeypatch):
    cbp, _ = _build(gw, monkeypatch, cached=True)
    assert cbp[0] == 0x05
    (size,) = struct.unpack_from("<H", cbp, 1)
    assert size == len(cbp) - 3
    assert struct.unpack_from("<IH", cbp, 3) == (10002, 56)
