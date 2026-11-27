"""Gateway Supply cache and perf monitor tests: import the gateway modules from
bigworld_gateway/server, as the gateway process does."""

import sys
from pathlib import Path

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))
