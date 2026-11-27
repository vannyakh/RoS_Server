"""RO-120: ApiClient keeps the account_link._call contract over keep-alive connections."""

import socket
import threading
import time

import pytest

import api_client
from api_client import ApiClient
from fake_api import FakeApi

KEY = "test-gateway-key-ro120-not-a-real-secret"


@pytest.fixture
def api():
    server = FakeApi()
    yield server
    server.stop()


@pytest.fixture
def client(api):
    c = ApiClient(api.url, KEY, timeout=2.0)
    yield c
    c.close()


def _closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_json_round_trip(api, client):
    assert client.call("POST", "/echo", {"price": 5, "props": [1, 2]}) == {
        "method": "POST", "path": "/echo", "echo": {"price": 5, "props": [1, 2]}}
    assert client.call("GET", "/thing", None)["method"] == "GET"
    assert client.call("PUT", "/thing", {"a": 1})["echo"] == {"a": 1}
    assert client.call("DELETE", "/thing", None)["method"] == "DELETE"
    assert client.call("GET", "/empty", None) == {}


def test_headers_sent(api, client):
    client.call("POST", "/echo", {"x": 1})
    _, _, headers, body = api.requests[-1]
    assert headers["X-Gateway-Key"] == KEY
    assert headers["Content-Type"] == "application/json"
    assert body == b'{"x": 1}'


def test_base_path_prefix(api):
    c = ApiClient(api.url + "/base/", KEY)
    assert c.call("GET", "/x", None)["path"] == "/base/x"
    c.close()


def test_http_error_with_json_detail(api, client, capsys):
    assert client.call("POST", "/conflict", {}) == {"_error": 409, "detail": "insufficient_gold"}
    assert "[ACC-LINK] POST /conflict -> HTTP 409" in capsys.readouterr().out


def test_http_error_with_text_body(api, client):
    assert client.call("GET", "/text-error", None) == {"_error": 500}


def test_non_json_success_body_is_none(api, client):
    assert client.call("GET", "/not-json", None) is None


def test_server_down_returns_none(capsys):
    c = ApiClient(f"http://127.0.0.1:{_closed_port()}", KEY, timeout=0.5)
    assert c.call("GET", "/x", None) is None
    assert c.call("POST", "/x", {}) is None
    assert "using local accounts" in capsys.readouterr().out


def test_no_key_sends_nothing(api):
    c = ApiClient(api.url, "")
    assert c.call("POST", "/echo", {}) is None
    assert c.get_cached("/listings", 10) is None
    assert api.count() == 0 and api.connections == 0


def test_connection_reused(api, client):
    for i in range(20):
        assert client.call("GET" if i % 2 else "POST", "/echo", {"i": i})["echo"] == {"i": i}
    assert api.connections == 1
    assert client.idle_connections() == 1


def test_stale_get_retried_once(api, client):
    client.call("GET", "/prime", None)
    api.drop_after_response = True
    client.call("GET", "/prime", None)  # server closes this connection after answering
    time.sleep(0.05)
    assert client.call("GET", "/after", None)["path"] == "/after"
    assert api.count("GET") == 3
    assert api.connections == 2


def test_stale_put_and_delete_retried(api, client):
    for method in ("PUT", "DELETE"):
        api.drop_after_response = True
        client.call("GET", "/prime", None)
        time.sleep(0.05)
        assert client.call(method, "/after", None)["method"] == method
        assert api.count(method) == 1


def test_stale_post_not_retried(api, client, capsys):
    api.drop_after_response = True
    client.call("GET", "/prime", None)
    time.sleep(0.05)
    result = client.call("POST", "/purchase", {"price": 100})
    assert result is None
    assert api.count("POST") == 0  # failed on the stale socket and was not sent again
    assert "POST /purchase failed" in capsys.readouterr().out
    # the next call works on a new connection
    assert client.call("POST", "/purchase2", {})["path"] == "/purchase2"
    assert api.count("POST") == 1


def test_timeout_honoured(api):
    c = ApiClient(api.url, KEY, timeout=0.2)
    start = time.monotonic()
    assert c.call("GET", "/slow", None) is None
    assert time.monotonic() - start < 0.8
    assert c.idle_connections() == 0  # a timed-out connection is never reused
    c.close()


def test_timed_out_get_not_retried(api):
    c = ApiClient(api.url, KEY, timeout=0.2)
    c.call("GET", "/prime", None)
    assert c.call("GET", "/slow", None) is None
    assert api.count("GET") == 2
    c.close()


def test_cache_hit_expiry_and_invalidate(api, client):
    first = client.get_cached("/listings", 0.3)
    assert first["listings"][0]["price"] == 10
    first["listings"].clear()  # callers get a copy
    assert client.get_cached("/listings", 0.3)["listings"]
    assert api.count("GET") == 1
    time.sleep(0.35)
    client.get_cached("/listings", 0.3)
    assert api.count("GET") == 2
    client.invalidate("/other")
    client.get_cached("/listings", 10)
    assert api.count("GET") == 2
    client.invalidate("/list")
    client.get_cached("/listings", 10)
    assert api.count("GET") == 3
    client.invalidate()
    client.get_cached("/listings", 10)
    assert api.count("GET") == 4


def test_cache_failures_cached_by_default():
    c = ApiClient("http://127.0.0.1:9", KEY, timeout=0.3)
    calls = []
    c.call = lambda *a: calls.append(a)  # returns None, like a dead server
    assert c.get_cached("/listings", 10) is None
    assert c.get_cached("/listings", 10) is None
    assert len(calls) == 1
    assert c.get_cached("/other", 10, cache_failures=False) is None
    assert c.get_cached("/other", 10, cache_failures=False) is None
    assert len(calls) == 3


def test_concurrent_threads(api, client):
    errors = []

    def work(n):
        for i in range(25):
            method = "POST" if i % 2 else "GET"
            result = client.call(method, f"/t{n}", {"n": n, "i": i})
            if not result or result.get("path") != f"/t{n}" or result["echo"] != {"n": n, "i": i}:
                errors.append((n, i, result))

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert api.count() == 200
    assert api.connections <= 8
    assert client.idle_connections() <= api_client.POOL_SIZE


def test_key_never_logged(api, capfd):
    c = ApiClient(api.url, KEY, timeout=0.2)
    c.call("POST", "/conflict", {})
    c.call("GET", "/text-error", None)
    c.call("GET", "/not-json", None)
    c.call("GET", "/slow", None)
    print(repr(c))
    dead = ApiClient(f"http://127.0.0.1:{_closed_port()}", KEY, timeout=0.3)
    dead.call("GET", "/x", None)
    out, err = capfd.readouterr()
    assert "[ACC-LINK]" in out
    assert KEY not in out and KEY not in err
    c.close()


def test_from_settings_rebuilds_on_change(api):
    settings = {"ROS_API_URL": api.url, "GATEWAY_API_KEY": KEY, "ROS_API_TIMEOUT": "2"}

    def setting(name, default=""):
        return settings.get(name) or default

    first = api_client.from_settings(setting)
    assert api_client.from_settings(setting) is first
    assert first.call("GET", "/x", None)["path"] == "/x"
    settings["ROS_API_TIMEOUT"] = "1.5"
    second = api_client.from_settings(setting)
    assert second is not first and second.timeout == 1.5
    assert first.idle_connections() == 0
    settings["GATEWAY_API_KEY"] = ""
    third = api_client.from_settings(setting)
    assert third is not second and third.call("GET", "/x", None) is None
    third.close()


def test_bad_url_rejected():
    with pytest.raises(ValueError):
        ApiClient("ftp://host", KEY)
