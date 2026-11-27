"""Give a gateway player props and gold on a development server.

    python scripts/dev_grant.py <external_uid> --prop 142091:2 [--prop id:n ...] [--gold 5000]

Calls POST /api/v1/gateway/accounts/{external_uid}/dev/grant, which RoS_Server answers only
when APP_ENV=development. Reads GATEWAY_API_KEY and ROS_API_URL (default
http://127.0.0.1:8000) from the environment, then from the repository .env. The key is never
printed. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = 1


def setting(name: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    try:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    except OSError:
        pass
    return default


def prop_arg(text: str) -> tuple[int, int]:
    try:
        prop_id, _, number = text.partition(":")
        pair = int(prop_id), int(number or "1")
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected prop_id:number, got {text!r}") from None
    if pair[0] < 0 or pair[1] < 1:
        raise argparse.ArgumentTypeError(f"prop_id must be >= 0 and number >= 1, got {text!r}")
    return pair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("external_uid", help="gateway login uid, e.g. 9000000001")
    parser.add_argument("--prop", action="append", type=prop_arg, default=[], metavar="ID:N",
                        help="prop id and count to add (repeatable)")
    parser.add_argument("--gold", type=int, default=0, help="gold coins to add (currency 1)")
    args = parser.parse_args(argv)
    if args.gold < 0:
        parser.error("--gold must be >= 0")
    if not args.prop and not args.gold:
        parser.error("nothing to grant: give --prop and/or --gold")

    key = setting("GATEWAY_API_KEY")
    if not key:
        print("GATEWAY_API_KEY is not set (environment or .env)", file=sys.stderr)
        return 2
    base = setting("ROS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/api/v1/gateway/accounts/{urllib.parse.quote(args.external_uid, safe='')}/dev/grant"
    body = {
        "props": [{"prop_id": p, "number": n} for p, n in args.prop],
        "currencies": [{"currency_id": GOLD, "amount": args.gold}] if args.gold else [],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "X-Gateway-Key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            state = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", errors="replace")
        hint = " (dev grant needs APP_ENV=development)" if exc.code == 404 else ""
        print(f"HTTP {exc.code}{hint}: {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"cannot reach {base}: {exc}", file=sys.stderr)
        return 1

    granted = {p for p, _n in args.prop}
    counts = {row["prop_id"]: row["number"] for row in state.get("items", [])}
    for prop_id in sorted(granted):
        print(f"prop {prop_id}: {counts.get(prop_id, 0)}")
    print(f"gold: {state.get('currencies', {}).get(str(GOLD), 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
