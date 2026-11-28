"""bigworld_gateway/server/server_registry.py: heartbeat body, player counts, server list text."""

import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[2] / "bigworld_gateway" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


@pytest.fixture
def reg(monkeypatch):
    sys.modules.pop("server_registry", None)
    import server_registry

    for var in ("SERVER_STATUS_CODES", "SERVER_LIST_FROM_API", "GATEWAY_SERVER_KEY", "GATEWAY_SERVER_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ROS_PC_IP", "192.0.2.10")
    return server_registry


ENTRY = {"server_key": "main", "name": "Private-Server", "host": "192.0.2.10", "port": 25000, "zone": 1,
         "group_id": 10001, "status": "smooth", "listed": True}


def test_list_matches_the_static_file_layout_byte_for_byte(reg):
    static = (SERVER / "real" / "server_list_ad.local.txt").read_bytes().replace(b"\r\n", b"\n")
    ip = static.split()[6].split(b":")[0].decode()
    built = reg.build_list([{**ENTRY, "host": ip}])
    assert built == static.rstrip(b"\n") or built + b"\n" == static


def test_status_codes_default_to_the_verified_value_and_can_be_set(reg, monkeypatch):
    assert reg.status_codes() == {"smooth": 8, "busy": 8, "full": 8, "maintenance": 8}
    monkeypatch.setenv("SERVER_STATUS_CODES", "busy:5, full:1,maintenance:0,bogus:3,smooth:x")
    assert reg.status_codes() == {"smooth": 8, "busy": 5, "full": 1, "maintenance": 0}
    line = reg.list_line({**ENTRY, "status": "full"})
    assert line.split()[2] == "1" and line.split()[3] == "2"


def test_unlisted_servers_are_left_out_and_an_empty_list_is_none(reg):
    two = reg.build_list([ENTRY, {**ENTRY, "server_key": "b", "name": "Asia-1", "zone": 5, "group_id": 10201}])
    assert two.count(b"Region ") == 2 and b"Region 5 8 2 Asia-1 Asia-1 " in two
    assert reg.build_list([{**ENTRY, "listed": False}]) is None


def test_counts_drop_silent_clients(reg):
    reg.note(("10.0.0.1", 1), in_match=False, now=100.0)
    reg.note(("10.0.0.2", 2), in_match=True, now=110.0)
    assert reg.counts(now=120.0) == (2, 1)
    assert reg.counts(now=135.0) == (1, 1)          # first client silent > 30 s
    assert reg.counts(now=200.0) == (0, 0)


def test_heartbeat_body(reg, monkeypatch):
    monkeypatch.setenv("GATEWAY_SERVER_KEY", "asia-1")
    reg.note(("10.0.0.3", 3), in_match=True)
    body = reg.heartbeat_body()
    assert (body["server_key"], body["name"], body["host"], body["port"]) == ("asia-1", "Private-Server", "192.0.2.10", 25000)
    assert (body["players_online"], body["players_in_match"]) == (1, 1)
    assert body["started_at"].endswith("Z")


def test_server_list_from_api_cached_with_fallbacks(reg, monkeypatch):
    calls = []
    answers = [{"servers": [ENTRY]}, None]
    monkeypatch.setattr(reg.account_link, "enabled", lambda: True)
    monkeypatch.setattr(reg.account_link, "_call", lambda m, p, b, **k: calls.append((m, p)) or answers.pop(0))
    first = reg.server_list_text(now=1000.0)
    assert first.startswith(b"Region 1 8 2 Private-Server") and calls == [("GET", "/api/v1/gateway/servers")]
    assert reg.server_list_text(now=1005.0) == first and len(calls) == 1      # cached
    assert reg.server_list_text(now=1020.0) == first and len(calls) == 2      # API down: last good list
    monkeypatch.setenv("SERVER_LIST_FROM_API", "off")
    assert reg.server_list_text(now=1030.0) is None
    monkeypatch.setenv("SERVER_LIST_FROM_API", "on")
    monkeypatch.setattr(reg.account_link, "enabled", lambda: False)
    assert reg.server_list_text(now=1040.0) is None                            # not linked: static file


def test_heartbeat_posts_only_when_linked(reg, monkeypatch):
    sent = []
    monkeypatch.setattr(reg.account_link, "_call", lambda m, p, b, **k: sent.append((m, p, b)) or {"status": "smooth"})
    monkeypatch.setattr(reg.account_link, "enabled", lambda: False)
    assert reg.heartbeat() is None and sent == []
    monkeypatch.setattr(reg.account_link, "enabled", lambda: True)
    assert reg.heartbeat() == {"status": "smooth"}
    assert sent[0][:2] == ("POST", "/api/v1/gateway/servers/heartbeat") and sent[0][2]["server_key"] == "main"
