"""Log search reads the newest entries first and keeps tracebacks with their entry."""

from datetime import datetime

from app.core.log_search import search

LOG = """2026-11-20 09:00:00,001 INFO ros.function {"function_name":"/health","status":"ok","duration_ms":3.2,"request_id":"r1"}
2026-11-20 09:00:05,100 WARNING app.game.tick_manager Tick overran the interval by 0.0120s
2026-11-20 09:01:00,250 ERROR asyncio Exception in callback
Traceback (most recent call last):
  File "x.py", line 1, in <module>
ValueError: boom
2026-11-20 09:02:00,000 INFO ros.function {"function_name":"/api/v1/lobby","status":"error","duration_ms":1250.5,"error_message":"bad"}
"""


def _log(tmp_path):
    path = tmp_path / "server.log"
    path.write_text(LOG, encoding="utf-8")
    return path


def test_returns_entries_oldest_first_with_tracebacks(tmp_path):
    result = search(_log(tmp_path), start=None, end=None, levels=None, text=None, kind=None, limit=100)
    assert [entry["level"] for entry in result["entries"]] == ["INFO", "WARNING", "ERROR", "INFO"]
    error = result["entries"][2]
    assert error["at"] == "2026-11-20 09:01:00.250"
    assert error["extra"][-1] == "ValueError: boom"
    assert result["entries"][3]["request"]["duration_ms"] == 1250.5
    assert result["counts"] == {"INFO": 2, "WARNING": 1, "ERROR": 1}


def test_filters_by_range_level_text_and_kind(tmp_path):
    path = _log(tmp_path)
    ranged = search(path, start=datetime(2026, 11, 20, 9, 0, 30), end=datetime(2026, 11, 20, 9, 1, 30), levels=None, text=None, kind=None, limit=100)
    assert [entry["level"] for entry in ranged["entries"]] == ["ERROR"]
    errors = search(path, start=None, end=None, levels={"ERROR", "WARNING"}, text=None, kind=None, limit=100)
    assert len(errors["entries"]) == 2
    assert errors["counts"]["INFO"] == 2  # counts cover every level so the filter chips can show them
    assert len(search(path, start=None, end=None, levels=None, text="valueerror", kind=None, limit=100)["entries"]) == 1
    assert len(search(path, start=None, end=None, levels=None, text=None, kind="request", limit=100)["entries"]) == 2
    assert len(search(path, start=None, end=None, levels=None, text=None, kind="app", limit=100)["entries"]) == 2


def test_limit_keeps_the_newest_and_marks_truncation(tmp_path):
    result = search(_log(tmp_path), start=None, end=None, levels=None, text=None, kind=None, limit=2)
    assert result["truncated"] is True
    assert [entry["level"] for entry in result["entries"]] == ["ERROR", "INFO"]


def test_missing_file_is_empty(tmp_path):
    assert search(tmp_path / "none.log", start=None, end=None, levels=None, text=None, kind=None, limit=5)["entries"] == []
