"""RO-075: doors.json coverage vs map700_elements wire table."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
GATEWAY_SERVER = REPO / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))


@pytest.fixture
def bf():
    return importlib.import_module("battle_flow")


@pytest.fixture
def doors_data():
    path = GATEWAY_SERVER / "battle" / "data" / "doors.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def elements_data():
    path = GATEWAY_SERVER / "extract" / "map700_elements.json"
    return json.loads(path.read_text(encoding="utf-8"))