"""Gateway API client tests: import api_client from bigworld_gateway/server, as the gateway
process does, and the local test server from this folder."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATEWAY_SERVER = HERE.parents[3] / "bigworld_gateway" / "server"
for folder in (GATEWAY_SERVER, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
