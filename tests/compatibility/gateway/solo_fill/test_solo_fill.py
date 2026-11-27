"""Solo fill config via MatchSession module (RO-110).

Defaults are proposed / unverified. No Mercury opcodes. No app/ imports.
Raising N is a JSON (or env) change — not an edit to ros_server.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from battle.session import MatchSession, load_battle_modules

from conftest import ADDR, GATEWAY_SERVER

MODULES_DIR = GATEWAY_SERVER / "battle" / "modules"
SOLO_FILL_JSON = GATEWAY_SERVER / "battle" / "data" / "solo_fill.json"
SOLO_FILL_PY = MODULES_DIR / "solo_fill.py"
SOLO_FILL_DOC = (
    Path(__file__).resolve().parents[4] / "docs" / "engineering" / "SOLO_MATCH_FILL.md"
)
ROS_SERVER_PY = GATEWAY_SERVER / "ros_server.py"


def test_default_bot_count_is_nine(solo_fill_mod):
    cfg = solo_fill_mod.load_solo_fill(SOLO_FILL_JSON)
    assert cfg.bot_count == 9
    assert cfg.human_count == 1
    assert cfg.warmup_seconds == 30.0
    assert cfg.alive_num == 10
    assert cfg.map_id is None
    assert cfg.mode_id is None


def test_register_attaches_config_without_wire_bytes(session, sent, solo_fill_mod):
    mod = solo_fill_mod.register(session)
    assert session.solo_fill is mod.config
    assert session.solo_fill.bot_count == 9
    assert session.solo_fill.warmup_seconds == 30.0
    assert sent == []  # no Mercury / createEntity traffic from this module


def test_bot_count_raised_via_json_without_ros_server_edit(
    tmp_path, session, sent, solo_fill_mod
):
    """N is data-driven; ros_server.py is not part of the fill path."""
    ros_before = ROS_SERVER_PY.read_bytes()
    path = tmp_path / "solo_fill.json"
    path.write_text(
        json.dumps(
            {
                "human_count": 1,
                "bot_count": 29,
                "warmup_seconds": 30,
                "bot_scale_targets": [29, 59, 119],
                "map_id": None,
                "mode_id": None,
                "remaining_issues": ["map_id unknown", "mode_id unknown"],
            }
        ),
        encoding="utf-8",
    )
    mod = solo_fill_mod.SoloFillModule(session, data_path=path)
    mod.attach()
    assert session.solo_fill.bot_count == 29
    assert session.solo_fill.alive_num == 30
    assert sent == []
    assert ROS_SERVER_PY.read_bytes() == ros_before
    # Source must not hard-require a fixed N inside ros_server.py for fill.
    assert "solo_fill" not in ros_before.decode("utf-8", errors="replace")


def test_env_override_bot_count(monkeypatch, solo_fill_mod):
    monkeypatch.setenv("SOLO_BOT_COUNT", "59")
    cfg = solo_fill_mod.load_solo_fill(SOLO_FILL_JSON)
    assert cfg.bot_count == 59
    assert cfg.alive_num == 60


def test_remaining_issues_include_unknown_map_and_mode(solo_fill_mod):
    cfg = solo_fill_mod.load_solo_fill(SOLO_FILL_JSON)
    joined = " ".join(cfg.remaining_issues).lower()
    assert "map" in joined
    assert "mode" in joined
    assert cfg.map_id is None
    assert cfg.mode_id is None


def test_doc_names_json_keys_and_marks_unverified():
    text = SOLO_FILL_DOC.read_text(encoding="utf-8")
    for key in (
        "human_count",
        "bot_count",
        "warmup_seconds",
        "bot_scale_targets",
        "map_id",
        "mode_id",
        "remaining_issues",
    ):
        assert key in text
    assert re.search(r"unverified|UNVERIFIED", text)
    assert "proposed" in text.lower()


def test_no_app_imports_in_solo_fill_sources():
    for path in (SOLO_FILL_PY, SOLO_FILL_JSON, SOLO_FILL_DOC):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(?m)^\s*from\s+app(\.|$|\s)", text)
        assert not re.search(r"(?m)^\s*import\s+app(\.|$|\s)", text)
        assert "from app" not in text
        assert "import app" not in text


def test_auto_load_includes_solo_fill(sent, clock):
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    loaded = load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    names = [Path(getattr(m, "__file__", "")).name for m in loaded]
    assert "solo_fill.py" in names
    assert hasattr(session, "solo_fill")
    assert session.solo_fill.bot_count == 9
