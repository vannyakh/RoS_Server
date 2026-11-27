"""MatchTimeline phases with FakeClock (RO-061). Gateway durations, not original RoS."""

from __future__ import annotations

import json

from battle.timeline import PHASES, MatchTimeline, load_phase_durations


def test_default_phases_match_data_file():
    durations = load_phase_durations()
    assert list(durations) == list(PHASES)
    assert durations["warmup"] == 3.0
    assert durations["boarding"] == 2.0
    assert durations["flight"] == 8.0
    assert durations["play"] == 0.0


def test_env_overrides_data_file(monkeypatch, tmp_path):
    data = tmp_path / "timeline.json"
    data.write_text(
        json.dumps({"warmup": 10.0, "boarding": 20.0, "flight": 30.0, "play": 40.0}),
        encoding="utf-8",
    )
    monkeypatch.setenv("BATTLE_PHASE_WARMUP", "1.5")
    monkeypatch.setenv("BATTLE_PHASE_BOARDING", "0.5")
    durations = load_phase_durations(data)
    assert durations["warmup"] == 1.5
    assert durations["boarding"] == 0.5
    assert durations["flight"] == 30.0
    assert durations["play"] == 40.0


def test_legacy_battle_prepare_sets_warmup(monkeypatch, tmp_path):
    data = tmp_path / "timeline.json"
    data.write_text(json.dumps({"warmup": 3.0, "boarding": 1.0, "flight": 1.0, "play": 0.0}), encoding="utf-8")
    monkeypatch.delenv("BATTLE_PHASE_WARMUP", raising=False)
    monkeypatch.setenv("BATTLE_PREPARE", "79")
    durations = load_phase_durations(data)
    assert durations["warmup"] == 79.0


def test_timeline_steps_with_fake_clock(session, clock):
    entered = []
    tl = MatchTimeline({"warmup": 3.0, "boarding": 2.0, "flight": 8.0, "play": 0.0})
    for name in PHASES:
        tl.on_phase(name, entered.append)
    tl.start(session)

    assert entered == []
    assert tl.phase is None

    # warmup is scheduled at delay 0; FakeClock runs it on the first advance.
    clock.advance(0.0)
    assert entered == ["warmup"]
    assert tl.phase == "warmup"

    clock.advance(2.9)
    assert entered == ["warmup"]
    clock.advance(0.2)  # t=3.1 -> boarding
    assert entered == ["warmup", "boarding"]
    clock.advance(2.0)  # t=5.1 -> flight (offset 5)
    assert entered == ["warmup", "boarding", "flight"]
    clock.advance(8.0)  # t=13.1 -> play (offset 13)
    assert entered == ["warmup", "boarding", "flight", "play"]
    assert tl.finished


def test_phase_offsets():
    tl = MatchTimeline({"warmup": 3.0, "boarding": 2.0, "flight": 8.0, "play": 0.0})
    assert tl.phase_offset("warmup") == 0.0
    assert tl.phase_offset("boarding") == 3.0
    assert tl.phase_offset("flight") == 5.0
    assert tl.phase_offset("play") == 13.0
    assert tl.total_duration() == 13.0
