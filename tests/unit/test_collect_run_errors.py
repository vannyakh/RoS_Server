"""Unit tests for bigworld_gateway/tools/collect_run_errors.py (fixture text only)."""

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "collect_run_errors", ROOT / "bigworld_gateway" / "tools" / "collect_run_errors.py")
cre = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cre)

S = "I/[10:00:00.000] M   <SCRIPT> ( 500): "

LOGCAT = "\n".join([
    "--------- beginning of main",
    "01-01 09:00:00.000 I/ActivityManager( 100): Start proc 400:com.netease.chiji/u0a61 for activity x",
    "01-01 09:00:01.000 " + S.replace("500", "400") + "Traceback (most recent call last):",
    "01-01 09:00:01.000 " + S.replace("500", "400") + "  File \"ui\\Old.py\", line 1, in old",
    "01-01 09:00:01.000 " + S.replace("500", "400") + "KeyError: 9",
    "01-01 10:00:00.000 I/ActivityManager( 100): Start proc 500:com.netease.chiji/u0a61 for activity x",
    "01-01 10:00:01.000 I/[10:00:01.000] M ( 500): [ERROR] Script execution returned the error '<type 'exceptions.KeyError'>'",
    "01-01 10:00:01.000 " + S + "Traceback (most recent call last):",
    "01-01 10:00:01.000 " + S + "  File \"libclaudia\\Classes\\WidgetTouchesBinder.py\", line 224, in on_touch",
    "01-01 10:00:01.001 I/chatty  ( 500): uid=10061 identical 2 lines",
    "01-01 10:00:01.001 " + S + "  File \"ui\\UIShareMall.py\", line 267, in onBuyBtnClicked",
    "01-01 10:00:01.002 " + S + "KeyError: 0",
    "01-01 10:00:05.000 " + S + "Traceback (most recent call last):",
    "01-01 10:00:05.000 " + S + "  File \"libclaudia\\Classes\\WidgetTouchesBinder.py\", line 224, in on_touch",
    "01-01 10:00:05.001 " + S + "  File \"ui\\UIShareMall.py\", line 267, in onBuyBtnClicked",
    "01-01 10:00:05.002 " + S + "KeyError: 0",
    "01-01 10:01:00.000 I/[10:01:00.000] M ( 500): [INFO] ServerConnection::createCellPlayer: id 10003",
    "01-01 10:01:10.000 " + S + "Traceback (most recent call last):",
    "01-01 10:01:10.000 " + S + "  File \"weapon\\ShootAssist.py\", line 385, in _updateAimTarget",
    "01-01 10:01:10.000 " + S + "  File \"libclaudia/internals/CyObject.pyx\", line 192, in PyGetAttr (/x/y.c:1)",
    "01-01 10:01:10.001 " + S + "AttributeError: 'PlayerAthlete' object has no attribute 'hp'",
    "01-01 10:02:00.000 F/libc    ( 500): Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0 "
    "in tid 520 (GLThread 12), pid 500 (m.netease.chiji)",
    "01-01 10:02:01.000 I/ActivityManager( 100): Process com.netease.chiji (pid 500) has died: fore TOP",
    "",
])

SERVER = "\n".join([
    "  [16:00:00] [BASEAPP RECV] 20B",
    "      [BASEAPP] <- Athlete.matchBattleGround args=01",
    "  [16:00:01] [BASEAPP SEND] 8B",
    "      [FLOW] stage -> waiting (timeline:warmup) | after 0.0s | human_ready=True bots_ready=False slots=10",
] + ["  [16:00:%02d] [BASEAPP RESEND] seq=%d ack=1 (24B) to ('10.0.0.1', 5000)" % (2 + i // 40, 50 + i % 3)
     for i in range(120)] + [
    "  [16:00:30] [BASEAPP SEND] 8B",
    "      [FLOW] stage -> aircraft (timeline:boarding) | after 30.0s | human_ready=True bots_ready=True slots=10",
    "      [FLOW] TIMEOUT stage=aircraft expected=jump elapsed=45.0 human_ready=True bots_ready=True "
    "pending_messages=3 reason=no completion within 45s recovery=forced",
    "  [16:01:20] [SESSION] ('10.0.0.1', 5000): packet (40B) matches no session key -> stale channel; dropped",
    "      [BATTLE SESSION] tick failed: KeyError(3)",
    "Traceback (most recent call last):",
    '  File "server/battle/flow.py", line 10, in advance',
    "    callback(stage)",
    "ValueError: bad stage",
    "  [16:01:30] [BASEAPP SEND] 8B",
    "      [FLOW] stage -> parachute (force) | after 60.0s | human_ready=True bots_ready=True slots=10",
    "",
])


@pytest.fixture
def run_dir(tmp_path):
    (tmp_path / "logcat.txt").write_text(LOGCAT, encoding="utf-8")
    (tmp_path / "server.log").write_text(SERVER, encoding="utf-8")
    (tmp_path / "s_lobby.png").write_bytes(b"\x89PNG")
    return tmp_path


def _by_kind(report, kind):
    return [f for f in report["findings"] if f["kind"] == kind]


def test_identical_tracebacks_grouped_with_count_and_first_time(run_dir):
    r = cre.collect(str(run_dir))
    tbs = _by_kind(r, "client_traceback")
    mall = [t for t in tbs if "UIShareMall" in t["title"]]
    assert len(mall) == 1
    t = mall[0]
    assert t["count"] == 2
    assert t["first_time"] == "01-01 10:00:01.000"
    assert t["client_frame"] == "ui\\UIShareMall.py line 267 onBuyBtnClicked"
    assert t["exception"] == "KeyError: 0"
    assert t["severity"] == "WARN" and t["in_battle"] is False


def test_battle_traceback_is_error_and_skips_engine_frame(run_dir):
    r = cre.collect(str(run_dir))
    t = [x for x in _by_kind(r, "client_traceback") if "hp" in x["title"]][0]
    assert t["severity"] == "ERROR" and t["in_battle"] is True
    assert t["client_frame"] == "weapon\\ShootAssist.py line 385 _updateAimTarget"
    assert t["last_frame"].startswith("libclaudia/internals/CyObject.pyx line 192 PyGetAttr")


def test_only_last_client_process_by_default(run_dir):
    r = cre.collect(str(run_dir))
    assert r["client"]["pid"] == "500"
    assert not [x for x in _by_kind(r, "client_traceback") if "Old.py" in x["title"]]
    every = cre.collect(str(run_dir), all_pids=True)
    assert [x for x in _by_kind(every, "client_traceback") if "Old.py" in x["title"]]


def test_script_error_and_native_crash(run_dir):
    r = cre.collect(str(run_dir))
    se = _by_kind(r, "script_error")
    assert len(se) == 1 and "KeyError" in se[0]["title"]
    sig = _by_kind(r, "native_crash")
    assert len(sig) == 1 and sig[0]["severity"] == "CRASH"
    assert "11 (SIGSEGV)" in sig[0]["title"] and "GLThread 12" in sig[0]["title"]
    died = _by_kind(r, "process_died")
    assert len(died) == 1 and died[0]["severity"] == "CRASH" and "pid 500" in died[0]["title"]


def test_flow_stages_and_timeout(run_dir):
    r = cre.collect(str(run_dir))
    assert r["stages_reached"] == ["waiting", "aircraft", "parachute"]
    assert r["last_stage"] == "parachute"
    assert r["flow"][1] == {"stage": "aircraft", "reason": "timeline:boarding", "after_s": 30.0,
                            "time": "16:00:30", "line": r["flow"][1]["line"]}
    assert len(r["timeouts"]) == 1
    to = r["timeouts"][0]
    assert to["stage"] == "aircraft" and to["elapsed"] == "45.0" and to["reason"] == "no completion within 45s"
    assert to["recovery"] == "forced"
    assert _by_kind(r, "flow_timeout")[0]["severity"] == "BLOCKER"
    stopped = _by_kind(r, "flow_stopped")
    assert len(stopped) == 1 and stopped[0]["severity"] == "BLOCKER" and "parachute" in stopped[0]["title"]


def test_stale_channel_resend_storm_and_gateway_errors(run_dir):
    r = cre.collect(str(run_dir))
    stale = _by_kind(r, "stale_channel")
    assert len(stale) == 1 and stale[0]["severity"] == "BLOCKER" and stale[0]["first_time"] == "16:01:20"
    assert r["resend"]["lines"] == 120
    assert r["resend"]["distinct_seqs"] == 3
    assert r["resend"]["max_resends_one_seq"] == 40
    assert _by_kind(r, "resend_storm")[0]["severity"] == "BLOCKER"
    fails = _by_kind(r, "gateway_failure")
    assert len(fails) == 1 and fails[0]["severity"] == "ERROR" and fails[0]["in_battle"] is True
    tb = _by_kind(r, "gateway_traceback")
    assert len(tb) == 1 and "ValueError: bad stage" in tb[0]["title"] and "flow.py line 10 advance" in tb[0]["title"]


def test_lobby_reached_is_not_a_blocker(tmp_path):
    (tmp_path / "server.log").write_text("\n".join([
        "  [16:00:00] x", "      [BASEAPP] <- Athlete.matchBattleGround args=01",
        "      [FLOW] stage -> waiting (timeline:warmup) | after 0.0s",
        "      [FLOW] stage -> results (victory) | after 100.0s",
        "      [BATTLE] results record_match ok rank_score=50",
        "      [BATTLE] results end placement=1 victory=True reason=victory alive_left=0",
        "      [FLOW] stage -> lobby (results) | after 3.2s", ""]), encoding="utf-8")
    r = cre.collect(str(tmp_path))
    assert r["counts"] == {"CRASH": 0, "BLOCKER": 0, "ERROR": 0, "WARN": 0}
    assert r["match"]["record_match"][0]["ok"] is True
    assert "placement=1" in r["match"]["results_end"]["text"]
    assert any("logcat.txt missing" in n for n in r["notes"])


def test_cli_writes_errors_md_and_json(run_dir, capsys):
    assert cre.main([str(run_dir)]) == 0
    md = (run_dir / "ERRORS.md").read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert md.startswith("# Run errors:") and "**Summary:**" in md
    for sev in ("## CRASH", "## BLOCKER", "## ERROR", "## WARN", "## Flow timeline"):
        assert sev in md
    assert "only the order inside each file is reliable" in md
    assert "s_lobby.png" in md
    assert "**Summary:**" in out
    assert cre.main([str(run_dir), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["counts"]["CRASH"] == 2 and data["counts"]["BLOCKER"] == 4
    assert data["last_stage"] == "parachute"
