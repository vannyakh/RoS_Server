"""scripts/sync_rosgg_gateway.py: three-way sync between RosGG-Server-v2 and bigworld_gateway/."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sync_rosgg_gateway", ROOT / "scripts" / "sync_rosgg_gateway.py")
sync = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sync
_spec.loader.exec_module(sync)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "core.autocrlf=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _commit(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repos(tmp_path: Path):
    src = tmp_path / "rosgg"
    dest = tmp_path / "ros"
    for repo in (src, dest):
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "core.autocrlf", "false")
    files = {"server/a.py": "a1\n", "server/b.py": "b1\n", "server/c.py": "c1\n", "README.md": "r1\n"}
    for rel, text in files.items():
        _write(src / rel, text)
        _write(dest / "bigworld_gateway" / rel, text)
    base = _commit(src, "base")
    _commit(dest, "base")
    assert sync.main(["init", "--source", str(src), "--dest", str(dest), "--base", base]) == 0
    return src, dest, base


def test_pull_takes_upstream_keeps_local_and_reports_conflict(repos):
    src, dest, _base = repos
    gw = dest / "bigworld_gateway"
    _write(src / "server/a.py", "a2 upstream\n")          # upstream only -> take
    _write(src / "server/c.py", "c2 upstream\n")          # both -> conflict
    (src / "server/b.py").unlink()                         # upstream delete -> delete
    _write(src / "server/new.py", "new\n")                 # upstream add -> take
    _write(src / "logs/server.log", "secret-ish\n")        # excluded
    _write(gw / "server/c.py", "c2 local\n")
    _write(gw / "README.md", "r2 local\n")                 # local only -> keep
    target = _commit(src, "upstream work")

    assert sync.main(["pull", "--source", str(src), "--dest", str(dest)]) == 1  # conflict
    assert (gw / "server/a.py").read_text() == "a2 upstream\n"
    assert (gw / "server/new.py").read_text() == "new\n"
    assert not (gw / "server/b.py").exists()
    assert (gw / "server/c.py").read_text() == "c2 local\n"
    assert (gw / "README.md").read_text() == "r2 local\n"
    assert not (gw / "logs/server.log").exists()
    state = json.loads((gw / sync.STATE_NAME).read_text())
    assert state["commit"] != target  # base not advanced while a conflict remains

    _write(gw / "server/c.py", "c2 upstream\n")           # resolve by hand
    assert sync.main(["pull", "--source", str(src), "--dest", str(dest)]) == 0
    assert json.loads((gw / sync.STATE_NAME).read_text())["commit"] == target


def test_dry_run_writes_nothing(repos):
    src, dest, base = repos
    _write(src / "server/a.py", "a2\n")
    _commit(src, "up")
    assert sync.main(["pull", "--source", str(src), "--dest", str(dest), "--dry-run"]) == 0
    gw = dest / "bigworld_gateway"
    assert (gw / "server/a.py").read_text() == "a1\n"
    assert json.loads((gw / sync.STATE_NAME).read_text())["commit"] == base


def test_push_copies_local_changes_into_rosgg_worktree(repos):
    src, dest, _base = repos
    gw = dest / "bigworld_gateway"
    _write(gw / "server/a.py", "a-fix from RoS_Server\n")
    _write(gw / "server/fresh.py", "fresh\n")
    _write(gw / "server/latest_bf_key.bin", "key\n")      # excluded from push
    assert sync.main(["push", "--source", str(src), "--dest", str(dest)]) == 0
    assert (src / "server/a.py").read_text() == "a-fix from RoS_Server\n"
    assert (src / "server/fresh.py").read_text() == "fresh\n"
    assert not (src / "server/latest_bf_key.bin").exists()
    assert sync.main(["push", "--source", str(src), "--dest", str(dest)]) == 0  # idempotent


def test_push_does_not_overwrite_uncommitted_rosgg_work(repos):
    src, dest, _base = repos
    _write(dest / "bigworld_gateway/server/a.py", "ros\n")
    _write(src / "server/a.py", "rosgg wip\n")
    assert sync.main(["push", "--source", str(src), "--dest", str(dest)]) == 1
    assert (src / "server/a.py").read_text() == "rosgg wip\n"


def test_excluded_patterns():
    assert sync.excluded(".env")
    assert sync.excluded("server/server_keys/login_private.pem")
    assert sync.excluded("server/gate_capture.bin")
    assert sync.excluded("client/frida/payloads/framing/captures/close1.png")
    assert not sync.excluded("server/ros_server.py")
    assert not sync.excluded("config.cmd")
