"""jev.ai helper: key handling, caching, and error handling. HTTP is mocked; no real key is used."""

import json

import httpx
import pytest

from tools.jev_assist.client import JevConfig, JevError, ask, cache_key

CONFIG = JevConfig(api_key="test-key-not-real", base_url="https://jev.test")


def _transport(calls: list, answer="Use app/game/rules.py", status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"answer": answer})

    return httpx.MockTransport(handler)


def test_config_needs_key_and_base_url():
    with pytest.raises(JevError, match="JEV_API_KEY"):
        JevConfig.from_env({})
    with pytest.raises(JevError, match="JEV_BASE_URL"):
        JevConfig.from_env({"JEV_API_KEY": "k"})
    config = JevConfig.from_env({"JEV_API_KEY": "k", "JEV_BASE_URL": "https://x.test/"})
    assert config.base_url == "https://x.test"


def test_answer_is_cached_and_second_call_needs_no_key(tmp_path):
    calls: list = []
    answer, cached = ask("How does revive work?", config=CONFIG, cache_dir=tmp_path, transport=_transport(calls))
    assert (answer, cached) == ("Use app/game/rules.py", False)
    request = calls[0]
    assert request.headers["authorization"] == "Bearer test-key-not-real"
    assert "revive" in json.loads(request.content)["prompt"]
    # Same question, different case: served from disk, no config, no network.
    again, cached = ask("how does revive work?  ", cache_dir=tmp_path, transport=_transport([], status=500))
    assert (again, cached) == (answer, True)
    assert len(calls) == 1


def test_cache_never_stores_the_key(tmp_path):
    ask("Where is the zone?", config=CONFIG, cache_dir=tmp_path, transport=_transport([]))
    text = "".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    assert "test-key-not-real" not in text


def test_refresh_skips_the_cache(tmp_path):
    calls: list = []
    ask("q", config=CONFIG, cache_dir=tmp_path, transport=_transport(calls, "one"))
    answer, cached = ask("q", config=CONFIG, cache_dir=tmp_path, transport=_transport(calls, "two"), refresh=True)
    assert (answer, cached) == ("two", False)


def test_http_error_does_not_leak_the_key_or_cache(tmp_path):
    with pytest.raises(JevError) as caught:
        ask("q", config=CONFIG, cache_dir=tmp_path, transport=_transport([], status=401))
    assert "401" in str(caught.value) and "test-key-not-real" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_missing_answer_field_is_a_clear_error(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"other": 1}))
    with pytest.raises(JevError, match="JEV_ANSWER_FIELD"):
        ask("q", config=CONFIG, cache_dir=tmp_path, transport=transport)


def test_cache_key_ignores_case_and_spaces():
    assert cache_key(" Hello ", "c") == cache_key("hello", "c")
    assert cache_key("hello", "c") != cache_key("hello", "d")
