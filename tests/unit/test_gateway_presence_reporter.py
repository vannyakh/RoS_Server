"""bigworld_gateway renews a presence lease while packets arrive and ends it when they stop."""

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def link(monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "test-key")
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    module = importlib.reload(importlib.import_module("account_link"))
    sent = []
    monkeypatch.setattr(module, "report_presence", lambda uid, online: sent.append((uid, online)) or online)
    monkeypatch.setattr(module, "_start_presence", lambda: None)
    module.sent = sent
    yield module
    sys.modules.pop("account_link", None)


def test_active_player_is_reported_once_per_interval(link):
    link.touch("9000000001")
    start = link._activity["9000000001"]
    assert link.presence_tick(start + 1) == [("9000000001", True)]
    assert link.presence_tick(start + 5) == []
    link._activity["9000000001"] = start + 21
    assert link.presence_tick(start + 22) == [("9000000001", True)]


def test_silent_player_is_reported_offline_and_forgotten(link):
    link.touch("9000000002")
    start = link._activity["9000000002"]
    link.presence_tick(start + 1)
    assert link.presence_tick(start + link.PRESENCE_IDLE + 1) == [("9000000002", False)]
    assert "9000000002" not in link._activity
    assert link.presence_tick(start + link.PRESENCE_IDLE + 10) == []


def test_touch_without_a_linked_player_or_key_does_nothing(link, monkeypatch):
    link.touch()
    assert link._activity == {}
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setattr(link, "_dotenv", lambda name: "")
    link.touch("9000000003")
    assert link._activity == {}
