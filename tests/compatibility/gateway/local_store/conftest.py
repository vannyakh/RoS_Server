"""local_store tests: import the gateway modules from bigworld_gateway/server,
as the gateway process does. Every test works on tmp files only."""

import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture(autouse=True)
def _fresh_store_cache():
    import local_store
    local_store._stores.clear()
    yield
    local_store._stores.clear()
