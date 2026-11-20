"""Upload a folder of display images to the asset library.

Layout: <folder>/<kind>/<key>.<png|jpg|jpeg|gif|webp>, or <folder>/model/<key>.glb, for example icons/prop/70001.png or
icons/rank/gold.png. Kinds: rank, prop, item, character, currency, badge, other, model.

Every upload records --source as its provenance (where the files came from).

    python scripts/upload_assets.py icons --source "my notes on where these came from" \
        --api http://127.0.0.1:8000 --username ops

The password is read from ROS_ADMIN_PASSWORD or prompted; it is never printed.
"""

import argparse
import getpass
import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path

KINDS = {"rank", "prop", "item", "character", "currency", "badge", "other", "model"}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".glb"}


def _request(url: str, data: bytes, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"{}")


def login(api: str, username: str, password: str) -> str:
    body = json.dumps({"username": username, "password": password}).encode()
    return _request(f"{api}/api/v1/admin/auth/login", body, {"Content-Type": "application/json"})["access_token"]


def multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="upload"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode()
    )
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def plan(folder: Path) -> list[tuple[str, str, Path]]:
    found = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        kind = path.parent.name.lower()
        if kind in KINDS:
            found.append((kind, path.stem, path))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--source", required=True, help="Provenance recorded on every upload")
    parser.add_argument("--api", default=os.environ.get("ROS_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--username", default=os.environ.get("ROS_ADMIN_USERNAME", ""))
    parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded")
    args = parser.parse_args()

    files = plan(args.folder)
    if not files:
        print("No <kind>/<key>.<image> files found.")
        return 1
    if args.dry_run:
        for kind, key, path in files:
            print(f"{kind}/{key}  <- {path}")
        print(f"{len(files)} files")
        return 0
    password = os.environ.get("ROS_ADMIN_PASSWORD") or getpass.getpass("Operator password: ")
    api = args.api.rstrip("/")
    token = login(api, args.username or input("Operator username: "), password)
    failed = 0
    for kind, key, path in files:
        body, content_type = multipart(
            {"kind": kind, "key": key, "name": key, "source": f"{args.source} ({path.name})"[:240]}, path.name, path.read_bytes()
        )
        try:
            _request(f"{api}/api/v1/admin/assets", body, {"Content-Type": content_type, "Authorization": f"Bearer {token}"})
            print(f"ok    {kind}/{key}")
        except urllib.error.HTTPError as error:
            failed += 1
            print(f"fail  {kind}/{key}: HTTP {error.code} {error.read()[:120]!r}")
    print(f"{len(files) - failed} uploaded, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
