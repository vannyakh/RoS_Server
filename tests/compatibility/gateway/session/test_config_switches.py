"""start.cmd runs config.cmd, whose LOBBY_SWITCHES_OFF replaces the default list in ros_server.py.
A switch the code relies on must be in both, or it stays on in a real run."""

from pathlib import Path

CONFIG = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "config.cmd"


def test_config_keeps_the_entertain_score_switch_off():
    lines = CONFIG.read_text(encoding="utf-8", errors="replace").splitlines()
    value = [ln.split("=", 1)[1] for ln in lines if ln.startswith("set LOBBY_SWITCHES_OFF=")]
    assert value and "EnableEntertainScore" in value[-1].split(",")
