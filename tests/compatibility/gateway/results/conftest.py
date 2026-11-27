"""Match results / lobby return tests (RO-071)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

GATEWAY_MODULES = (
    "battle",
    "battle.session",
    "battle_flow",
    "bwdefs",
    "account_link",
)

ADDR = ("127.0.0.1", 25071)


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
def sent():
    return []


@pytest.fixture
def clock():
    from battle.session import FakeClock

    return FakeClock(start=100.0)


@pytest.fixture
def session(sent, clock):
    from battle.session import MatchSession

    return MatchSession(ADDR, lambda body: sent.append(body), clock=clock, scheduler=clock)


@pytest.fixture
def bf():
    import battle_flow

    return battle_flow


@pytest.fixture
def results_mod():
    path = GATEWAY_SERVER / "battle" / "modules" / "results.py"
    spec = importlib.util.spec_from_file_location("battle.modules.results", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["battle.modules.results"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def solo_fill_mod():
    path = GATEWAY_SERVER / "battle" / "modules" / "solo_fill.py"
    spec = importlib.util.spec_from_file_location("battle.modules.solo_fill", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["battle.modules.solo_fill"] = module
    spec.loader.exec_module(module)
    return module