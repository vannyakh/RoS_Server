"""In-battle request decoder tests (RO-060): import battle.requests from gateway server."""

import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

PAYLOADS = (
    Path(__file__).resolve().parents[4]
    / "bigworld_gateway"
    / "client"
    / "frida"
    / "payloads"
    / "requests"
)


def _read_full_hex(name: str) -> bytes:
    """Parse ``full_message_hex=`` from a RO-057 capture comment file."""
    text = (PAYLOADS / name).read_text(encoding="utf-8")
    lines = text.splitlines()
    collecting = False
    hex_parts = []
    for line in lines:
        if line.startswith("full_message_hex="):
            rest = line.split("=", 1)[1].strip()
            if rest:
                hex_parts.append(rest)
            collecting = True
            continue
        if collecting:
            s = line.strip()
            if not s or s.startswith("#") or "=" in s:
                break
            hex_parts.append(s)
    blob = "".join(hex_parts)
    return bytes.fromhex(blob)


@pytest.fixture
def reqs():
    import battle.requests as requests_mod

    requests_mod.reset_log_state()
    requests_mod._tables = None  # reload extract between tests
    return requests_mod


@pytest.fixture
def capture_hex():
    return _read_full_hex


@pytest.fixture
def logs():
    lines = []

    def log(msg=""):
        lines.append(str(msg))

    return lines, log
