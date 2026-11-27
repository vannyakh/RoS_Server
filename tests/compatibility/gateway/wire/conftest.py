"""Gateway wire encoder tests (createEntity / property / entity method)."""

import importlib
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

GATEWAY_MODULES = ("battle_flow", "bwdefs")


@pytest.fixture(autouse=True)
def fresh_battle_flow():
    saved = {name: sys.modules.pop(name, None) for name in GATEWAY_MODULES}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def bf():
    return importlib.import_module("battle_flow")


def load_hex(name: str) -> bytes:
    text = (FIXTURES / name).read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return bytes.fromhex(text)
