"""Offline RO-068 helper: print Robot create/update indices and a sample createEntity hex.

Not a live Frida payload. Run from repo root:

  .\\.venv\\Scripts\\python.exe bigworld_gateway/client/frida/payloads/bots/_ro068_probe_indices.py
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "bigworld_gateway" / "server"))

import battle_flow as bf  # noqa: E402
import bwdefs  # noqa: E402

_FL = {
    "CELL_PRIVATE": 0,
    "PRIVATE": 0,
    "CELL_PUBLIC": 1,
    "CELL": 1,
    "GHOSTED": 1,
    "OTHER_CLIENTS": 3,
    "OTHER_CLIENT": 3,
    "OWN_CLIENT": 4,
    "BASE": 8,
    "BASE_AND_CLIENT": 0xC,
    "CELL_PUBLIC_AND_OWN": 5,
    "GHOSTED_AND_OWN": 5,
    "CELL_AND_OWN": 5,
    "ALL_CLIENTS": 7,
    "ALL_CLIENT": 7,
    "EDITOR_ONLY": 0x40,
    "": 0,
}


def main() -> None:
    out = Path(__file__).with_name("entities_out")
    extract = ROOT / "bigworld_gateway" / "server" / "extract" / "entities_out"
    for fn, label in (("430_9c05fc29.bin", "avatar"), ("321_7855a65a.bin", "bga"), ("130_3298c23a.bin", "robot")):
        text = (extract / fn).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"<Volatile>[\s\S]*?</Volatile>", text)
        print(label, m.group(0).replace("\n", " ") if m else "NO VOLATILE")

    order, last = [], {}
    for p in bf.defs().properties("Robot"):
        if p[0] not in last:
            order.append(p[0])
        last[p[0]] = p
    upd = [n for n in order if _FL.get(last[n][2], 0) & 6]
    create_names = [p[0] for p in bf.other_client_props("Robot")]
    print("update_N", len(upd), "create_N", len(create_names), "type", bf.client_type("Robot"))
    for n in (
        "mapID",
        "characterType",
        "hp",
        "maxHp",
        "deadInGame",
        "campType",
        "handingWeapon",
        "dieReason",
        "planeID",
        "battleState",
        "pose",
        "nickname",
        "robotVisible",
        "gender",
        "level",
        "dtsCurWeapon",
        "identityType",
    ):
        print(
            "prop",
            n,
            "create",
            create_names.index(n) if n in create_names else None,
            "update",
            upd.index(n) if n in upd else None,
        )

    for entity in ("Robot", "BattleGroundAvatar"):
        table = bf.defs().client_method_table(entity)
        for i, m in enumerate(table):
            if m[0] in (
                "dtsKillTip",
                "onBattleGroundDie",
                "showKillerOverview",
                "onKillOther",
                "damage",
                "die",
            ):
                print("client_method", entity, i, m[0], m[1])

    print("space_aliveNum_create", bf.prop_index("BattleGroundSpace", "aliveNum"))

    body = bf.create_entity(
        40000,
        "Robot",
        pos=(845.0, 50.0, -2467.0),
        direction=(0.5, 0.0, 0.0),
        values={
            "mapID": bf.i32(700),
            "characterType": struct.pack("<I", 20001),
            "nickname": bwdefs.blob(b"Bot01"),
            "robotVisible": struct.pack("<B", 1),
            "hp": bf.i32(100),
            "maxHp": bf.i32(100),
            "gender": bf.i32(1),
            "level": bf.i32(1),
            "battleState": bf.i8(0),
            "pose": bf.i8(0),
        },
    )
    print("sample_len", len(body))
    print("sample_hex", body.hex())
    _ = out  # reserved for future capture dumps beside this script


if __name__ == "__main__":
    main()
