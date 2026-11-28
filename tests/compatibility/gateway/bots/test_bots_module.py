"""Static Robot-58 bot spawn via MatchSession module (RO-069).

Sources labeled in asserts:
- BOT_ENTITIES.md / RO-068: Robot type 58, min create props, no invented 0x58 walk
- battle_flow create_entity / leave_aoi / update_property (RO-059)
- session.solo_fill.bot_count (RO-110) for N; aliveNum = humans + bots

Does not claim original RoS AI, walk sync, or combat values.
In-game LDPlayer visibility is an ops check (single ros_server + BATTLE_SPACE=off).
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

from battle.session import MatchSession, load_battle_modules

from conftest import ADDR, GATEWAY_SERVER

MODULES_DIR = GATEWAY_SERVER / "battle" / "modules"
BOTS_JSON = GATEWAY_SERVER / "battle" / "data" / "bots.json"
BOTS_PY = MODULES_DIR / "bots.py"


def _start_bots(bots_mod, session, **kwargs):
    """Synchronous start for unit tests (skips register's deferred schedule)."""
    mod = bots_mod.BotModule(session, **kwargs)
    mod.start()
    return mod


def test_robot_client_type_is_58(bf):
    assert bf.client_type("Robot") == 58
    assert bf.client_type("Robot") != bf.client_type("BattleGroundAvatar")


def test_sample_create_matches_bot_entities_offline_hex(bf):
    """Offline sample from BOT_ENTITIES.md §2.2 (encoder evidence, not live capture)."""
    import bwdefs

    expected = bytes.fromhex(
        "0b409c0000ff094900409c00003a00004053440000484200301ac5140000000001"
        "6efbfffbf7fffffffffffff7ffffff01bc020000214e00006400000064000000"
        "0000010000000100000005426f74303101"
    )
    got = bf.create_entity(
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
    assert got == expected


def test_spawn_nine_unique_bot_ids_from_solo_fill(
    session, sent, bots_mod, solo_fill_mod, bf
):
    solo_fill_mod.register(session)
    mod = _start_bots(bots_mod, session)
    assert session.solo_fill.bot_count == 9
    assert len(mod.bot_ids) == 9
    assert mod.bot_ids == list(range(40000, 40009))
    assert len(set(mod.bot_ids)) == 9
    # 9 createEntity + 1 aliveNum update
    assert len(sent) == 10
    for i, eid in enumerate(mod.bot_ids):
        body = sent[i]
        assert body[:1] == b"\x0b"  # enterAoI
        assert struct.unpack_from("<I", body, 1)[0] == eid
        ce = body[6:]
        assert ce[0] == 9  # createEntity
        payload = ce[3:]
        wire_eid, typ = struct.unpack_from("<IH", payload, 0)
        assert wire_eid == eid
        assert typ == 58
    assert sent[9] == bf.update_property(
        "BattleGroundSpace", "aliveNum", bf.i32(10), eid=session.space_id
    )
    assert mod.alive_num == 10


def test_placement_deterministic_with_seed(session, bots_mod, solo_fill_mod):
    solo_fill_mod.register(session)
    a = _start_bots(bots_mod, session, seed=69)
    session2 = MatchSession(ADDR, lambda *_: None)
    solo_fill_mod.register(session2)
    b = _start_bots(bots_mod, session2, seed=69)
    assert a.positions == b.positions
    assert a.bot_ids == b.bot_ids

    session3 = MatchSession(ADDR, lambda *_: None)
    solo_fill_mod.register(session3)
    c = _start_bots(bots_mod, session3, seed=70)
    assert c.positions != a.positions


def test_place_bots_helper_seed_stable(bots_mod):
    p1 = bots_mod.place_bots(9, seed=69, anchor=(845.0, 50.0, -2467.0), spacing=4.0)
    p2 = bots_mod.place_bots(9, seed=69, anchor=(845.0, 50.0, -2467.0), spacing=4.0)
    assert p1 == p2
    assert len(p1) == 9
    p3 = bots_mod.place_bots(9, seed=1, anchor=(845.0, 50.0, -2467.0), spacing=4.0)
    assert p3 != p1


def test_session_end_removes_bots(session, sent, bots_mod, solo_fill_mod, bf):
    solo_fill_mod.register(session)
    mod = _start_bots(bots_mod, session)
    assert mod.created
    n = len(mod.bot_ids)
    session.close()
    assert mod.removed
    # leaveAoI for each bot after the create+aliveNum traffic
    leaves = sent[n + 1 :]
    assert len(leaves) == n
    for eid, body in zip(mod.bot_ids, leaves):
        assert body == bf.leave_aoi(eid)


def test_bot_count_from_solo_fill_override(session, sent, bots_mod):
    class _Fill:
        bot_count = 3
        human_count = 1

        @property
        def alive_num(self):
            return self.human_count + self.bot_count

    session.solo_fill = _Fill()
    mod = _start_bots(bots_mod, session)
    assert len(mod.bot_ids) == 3
    assert mod.alive_num == 4
    assert len(sent) == 4  # 3 creates + aliveNum


def test_min_create_props_from_bot_entities(bots_mod, bf):
    """Min props listed in BOT_ENTITIES.md §2.1 for named humanoid render."""
    values = bots_mod.build_bot_values(
        bots_mod.load_bots_config(BOTS_JSON),
        nickname="Bot01",
        character_type=20001,
        gender=1,
    )
    for key in (
        "mapID",
        "characterType",
        "nickname",
        "robotVisible",
        "hp",
        "maxHp",
        "gender",
        "level",
        "battleState",
        "pose",
    ):
        assert key in values
    body = bf.create_entity(
        40000,
        "Robot",
        pos=(845.0, 50.0, -2467.0),
        direction=(0.5, 0.0, 0.0),
        values=values,
    )
    # enterAoI(6) + msgid(1) + len(2) + eid(4) + type(2)
    assert struct.unpack_from("<H", body, 13)[0] == 58
    text = BOTS_PY.read_text(encoding="utf-8")
    assert "Robot" in text
    assert "BattleGroundAvatar" not in text


def test_no_invented_walk_or_combat_opcodes():
    text = BOTS_PY.read_text(encoding="utf-8")
    assert "MSG_FORCED_POSITION" not in text
    assert "dtsKillTip" not in text
    assert "entity_method" not in text
    assert "from app" not in text
    assert "import app" not in text
    # Mentions 0x58 only as forbidden / unknown walk channel.
    assert "0x58" in text
    assert "do not" in text.lower() or "unknown" in text.lower()


def test_no_app_imports_in_bots_sources():
    for path in (BOTS_PY, BOTS_JSON):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(?m)^\s*from\s+app(\.|$|\s)", text)
        assert not re.search(r"(?m)^\s*import\s+app(\.|$|\s)", text)


def test_auto_load_includes_bots(sent, clock, bf):
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    loaded = load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    names = [Path(getattr(m, "__file__", "")).name for m in loaded]
    assert "bots.py" in names
    assert "solo_fill.py" in names
    # Bots start with the waiting stage, once the match starts (client in the world).
    session.start_match("test")
    clock.advance(0.0)
    bots = getattr(session, "bots_module", None)
    assert bots is not None
    assert bots.created
    assert len(bots.bot_ids) == session.solo_fill.bot_count
    assert bots.alive_num == session.solo_fill.alive_num
    eids = list(bots.bot_ids)
    session.close()
    assert bots.removed
    for eid in eids:
        assert bf.leave_aoi(eid) in sent


def test_remaining_issues_document_walk_and_live_ops(bots_mod):
    cfg = bots_mod.load_bots_config(BOTS_JSON)
    joined = " ".join(cfg["remaining_issues"]).lower()
    assert "0x58" in joined or "walk" in joined
    assert "combat" in joined or "kill" in joined
    assert "ldplayer" in joined or "unverified" in joined or "ops" in joined


def test_default_keeps_bots_server_side(session, sent, bots_mod, solo_fill_mod, bf, monkeypatch):
    """Default (BOT_CLIENT_ENTITIES off): no Robot createEntity or leaveAoI reaches the client, but the
    bots still count in aliveNum and in the match flow's slots."""
    monkeypatch.setenv("BOT_CLIENT_ENTITIES", "off")
    solo_fill_mod.register(session)
    mod = _start_bots(bots_mod, session)
    assert len(mod.bot_ids) == 9
    assert all(body[:1] != b"\x0b" for body in sent)          # no enterAoI / createEntity
    assert sent == [bf.update_property("BattleGroundSpace", "aliveNum", bf.i32(10), eid=session.space_id)]
    assert session.flow.slots == 10
    mod.remove()
    assert len(sent) == 1                                       # no leaveAoI for entities never sent
