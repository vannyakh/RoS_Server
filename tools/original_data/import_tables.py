"""Read original gameplay data tables from a local OBB and write JSON for local study.

Reads assets.npk inside the main OBB (standard zlib, not encrypted). It never
modifies the OBB and never touches script.npk. Output goes to
storage/original_data/, which is git-ignored: it is publisher data and must not
be committed.

    python -m tools.original_data.import_tables <main.obb> [--out DIR]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import struct
import warnings
import zipfile
import zlib
from pathlib import Path

NPK = "assets.npk"
# table title (from the file's `name =` line) -> output file stem
WANTED = {
    "装备表:枪械机械表": "gun_mechanics",
    "大逃杀道具表": "br_items",
    "物品表": "items",
    "投掷物表": "throwables",
    "可争抢载具表": "vehicles",
    "补给箱表": "supply_crates",
}
_TRANS = re.compile(r"_g89na_trans\('[0-9a-f]+'\)")


def read_entries(obb: Path):
    """Yield (hash, bytes) for every entry of assets.npk."""
    with zipfile.ZipFile(obb) as z, z.open(NPK) as f:
        head = f.read(24)
        if head[:4] != b"NXPK":
            raise ValueError("assets.npk is not an NXPK archive")
        count = struct.unpack("<I", head[4:8])[0]
        index = struct.unpack("<I", head[20:24])[0]
        f.seek(index)
        raw = f.read(count * 28)
        for i in range(count):
            h, off, csize, _osize, _c, _z, flag = struct.unpack("<7I", raw[i * 28 : i * 28 + 28])
            f.seek(off)
            body = f.read(csize)
            try:
                yield h, (zlib.decompress(body) if flag == 1 else body)
            except zlib.error:
                continue


def parse_table(text: str) -> tuple[str, dict] | None:
    """Return (title, data) for a `name = ...` / `data = {...}` table, else None."""
    title = re.search(r'^name\s*=\s*"(.*?)"', text, re.M)
    start = re.search(r"^data\s*=\s*\\?", text, re.M)
    if not title or not start:
        return None
    body = _TRANS.sub("'T'", text[start.end() :])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return title.group(1), ast.literal_eval(body.strip())
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("obb", type=Path)
    ap.add_argument("--out", type=Path, default=Path("storage/original_data"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    written: dict[str, dict] = {}
    for h, body in read_entries(args.obb):
        if body[:1] not in (b"#", b"\xef"):
            continue
        parsed = parse_table(body.decode("utf-8", errors="replace"))
        if parsed is None or parsed[0] not in WANTED:
            continue
        title, data = parsed
        # Several tables can share a title, so every match is kept under its own hash.
        name = f"{WANTED[title]}__{h:08x}"
        (args.out / f"{name}.json").write_text(
            json.dumps({"source": f"{NPK}:{h:08x}", "title": title, "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )
        written[name] = {"source": f"{NPK}:{h:08x}", "records": len(data)}
    (args.out / "manifest.json").write_text(json.dumps(written, indent=2), encoding="utf-8")
    for stem, info in sorted(written.items()):
        print(f"{stem}: {info['records']} records from {info['source']}")
    missing = set(WANTED.values()) - {n.split("__")[0] for n in written}
    if missing:
        print("not found:", ", ".join(sorted(missing)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
