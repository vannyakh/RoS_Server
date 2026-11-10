"""This server's documented JSON contract. Not an original client protocol."""

from pathlib import Path

from app.networking.protocol import ClientMessage, PlayerAction

INTERFACE = Path("docs/reverse-engineering/NETWORK_INTERFACE.md")


def _listed(heading: str) -> set[str]:
    lines = INTERFACE.read_text(encoding="utf-8").splitlines()
    found = set()
    collecting = False
    for line in lines:
        if line.startswith("## "):
            collecting = line == f"## {heading}"
            continue
        if collecting and line.startswith("- `") and line.endswith("`"):
            found.add(line[3:-1])
    return found


def test_documented_messages_match_this_server():
    documented = _listed("Message types")
    implemented = set(ClientMessage.model_fields["type"].annotation.__args__)
    assert documented == implemented
    assert "auth" in documented


def test_documented_actions_match_this_server():
    documented = _listed("Player actions")
    implemented = set(PlayerAction.model_fields["action"].annotation.__args__)
    assert documented == implemented
    assert INTERFACE.read_text(encoding="utf-8").count("official Rules of Survival client protocol") == 1
