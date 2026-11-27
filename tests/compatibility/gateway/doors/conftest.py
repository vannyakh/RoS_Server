"""RO-067: BattleGroundSpace door module tests."""

from __future__ import annotations

import importlib
import importlib.util
import json
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
    "battle.requests",
)

ADDR = ("127.0.0.1", 25009)


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    names = list(GATEWAY_MODULES) + [k for k in sys.modules if k.startswith("battle.modules.")]
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
def session(sent):
    from battle.session import MatchSession

    return MatchSession(ADDR, lambda body: sent.append(body))


def _load_doors_module():
    path = GATEWAY_SERVER / "battle" / "modules" / "doors.py"
    name = "battle.modules.doors"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def doors_mod():
    return _load_doors_module()


@pytest.fixture
def tiny_doors_data(tmp_path):
    data = {
        "space_entity_id": 20001,
        "default_open_state": 1,
        "default_close_state": 0,
        "opened_elements_on_reply": False,
        "unknown_elem_policy": "echo_and_log_once",
        "doors": [
            {"elem_id": 815, "open_states": [1], "close_state": 0, "pair_elem_ids": None},
            {
                "elem_id": 4660,
                "open_states": [3],
                "close_state": 0,
                "pair_elem_ids": [4661],
            },
            {
                "elem_id": 4661,
                "open_states": [1],
                "close_state": 0,
                "pair_elem_ids": [4660],
            },
        ],
    }
    p = tmp_path / "doors.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def pack_open(reqs, elem_id, state, *, space_id=20001):
    args = __import__("struct").pack("<ib", int(elem_id), int(state))
    frame = reqs.encode_call("BattleGroundSpace", "openElement", space_id, args)
    return frame[0], frame[3:]


def pack_close(reqs, elem_id, *, space_id=20001):
    args = __import__("struct").pack("<i", int(elem_id))
    frame = reqs.encode_call("BattleGroundSpace", "closeElement", space_id, args)
    return frame[0], frame[3:]