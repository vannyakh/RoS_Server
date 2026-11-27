"""Loot / DtsProp tests (RO-066)."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

GATEWAY_MODULES = (
    "battle_flow",
    "bwdefs",
    "battle",
    "battle.session",
    "battle.timeline",
    "battle.requests",
)

ADDR = ("127.0.0.1", 25008)


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    names = list(GATEWAY_MODULES) + [
        k for k in sys.modules if k.startswith("battle.modules.")
    ]
    saved = {name: sys.modules.pop(name, None) for name in names}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def bf():
    return importlib.import_module("battle_flow")


@pytest.fixture
def reqs():
    return importlib.import_module("battle.requests")


@pytest.fixture
def sent():
    return []


@pytest.fixture
def clock():
    from battle.session import FakeClock

    return FakeClock(start=0.0)


@pytest.fixture
def session(sent, clock):
    from battle.session import MatchSession

    return MatchSession(ADDR, lambda body: sent.append(body), clock=clock)


def _load_module(stem):
    path = GATEWAY_SERVER / "battle" / "modules" / f"{stem}.py"
    name = f"battle.modules.{stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def props_mod():
    return _load_module("props")


@pytest.fixture
def jump_mod():
    return _load_module("jump")


@pytest.fixture
def tiny_loot(tmp_path):
    data = {
        "map_id": 700,
        "pickup_range_xz": 50.0,
        "entries": [
            {"prop_id": 1001, "amount": 1, "x": 698.0, "y": -677.0, "z": -373.0},
            {"prop_id": 1101, "amount": 1, "x": 700.0, "y": -677.0, "z": -373.0},
        ],
    }
    p = tmp_path / "loot.json"
    p.write_text(__import__("json").dumps(data), encoding="utf-8")
    return p