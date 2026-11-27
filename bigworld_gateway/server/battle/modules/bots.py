"""Static Robot (type 58) bots for Solo BR first-playable visibility (RO-069).

Spawns N named Robot entities via RO-059 ``create_entity`` using ids from
``MatchSession.alloc_bot_id()`` (40000+). N comes from ``session.solo_fill.bot_count``
(RO-110, default 9). Sets BattleGroundSpace ``aliveNum`` to humans + bots.

Movement after create uses the createEntity header pose only. Do **not** invent
detailedPosition (0x58) walk packets — layout unknown (RO-068). Combat / death /
kill-feed are skipped (RO-111+). No LLM AI. No app/ imports.

When this module is loaded with space.py, set BATTLE_SPACE=off so the legacy
ros_server delayed spacet path does not create a second space entity.
"""

from __future__ import annotations

import json
import os
import random
import struct
from pathlib import Path

import battle_flow as bf
import bwdefs
from battle import player_entity as pe

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_BOTS_PATH = DATA_DIR / "bots.json"

# Proposed first-playable defaults — unverified against original RoS.
_BUILTIN = {
    "seed": 69,
    "map_id": 700,
    "hp": 100,
    "max_hp": 100,
    "level": 1,
    "anchor": [845.0, 50.0, -2467.0],
    "yaw": 0.5,
    "spacing": 4.0,
    "nicknames": ["Bot%02d" % i for i in range(1, 30)],
    "character_types": [20001, 20002],
    "remaining_issues": [
        "Live Robot createEntity accept unverified",
        "0x58 walk layout unknown — static pose only",
        "Combat / death deferred",
    ],
}

ROBOT_ENTITY = "Robot"
DEFAULT_BOT_COUNT = 9
DEFAULT_HUMAN_COUNT = 1


def _u32(v):
    return struct.pack("<I", int(v))


def _bool(v):
    return struct.pack("<B", 1 if v else 0)


def load_bots_config(path=None):
    """Load bots.json. Missing file falls back to built-in proposed defaults."""
    root = Path(path) if path is not None else DEFAULT_BOTS_PATH
    data = dict(_BUILTIN)
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in (
            "seed",
            "map_id",
            "hp",
            "max_hp",
            "level",
            "anchor",
            "yaw",
            "spacing",
            "nicknames",
            "character_types",
            "remaining_issues",
        ):
            if key in raw:
                data[key] = raw[key]
    if "BOTS_SEED" in os.environ:
        data["seed"] = int(os.environ["BOTS_SEED"])
    if "BATTLE_MAP" in os.environ:
        data["map_id"] = int(os.environ["BATTLE_MAP"])
    return data


def resolve_bot_count(session, *, default=DEFAULT_BOT_COUNT):
    """Prefer session.solo_fill.bot_count (RO-110); else default 9."""
    fill = getattr(session, "solo_fill", None)
    if fill is not None and hasattr(fill, "bot_count"):
        return int(fill.bot_count)
    if "SOLO_BOT_COUNT" in os.environ:
        return int(os.environ["SOLO_BOT_COUNT"])
    return int(default)


def resolve_human_count(session, *, default=DEFAULT_HUMAN_COUNT):
    fill = getattr(session, "solo_fill", None)
    if fill is not None and hasattr(fill, "human_count"):
        return int(fill.human_count)
    if "SOLO_HUMAN_COUNT" in os.environ:
        return int(os.environ["SOLO_HUMAN_COUNT"])
    return int(default)


def resolve_alive_num(session, bot_count=None):
    """Gateway convention: humans + bots (BOT_ENTITIES.md / RO-110)."""
    fill = getattr(session, "solo_fill", None)
    if fill is not None and hasattr(fill, "alive_num"):
        return int(fill.alive_num)
    n = resolve_bot_count(session) if bot_count is None else int(bot_count)
    return resolve_human_count(session) + n


def place_bots(count, *, seed, anchor, spacing):
    """Deterministic prep-island positions from a seeded PRNG (static spawn OK).

    Returns list of (x, y, z). Same seed + count => same positions.
    """
    ax, ay, az = (float(anchor[0]), float(anchor[1]), float(anchor[2]))
    step = float(spacing)
    rng = random.Random(int(seed))
    # Shuffle a grid of candidate offsets so placement is seed-dependent but
    # collisions stay bounded near the prep anchor (no teleport / wallhack).
    cols = max(1, int(count**0.5) + 1)
    candidates = []
    for i in range(max(count * 2, cols * cols)):
        gx = i % cols
        gz = i // cols
        ox = (gx - (cols - 1) / 2.0) * step
        oz = (gz - (cols - 1) / 2.0) * step
        # Tiny seed-tied jitter (< spacing/4) so layout is not a perfect lattice only.
        jx = (rng.random() - 0.5) * (step * 0.25)
        jz = (rng.random() - 0.5) * (step * 0.25)
        candidates.append((ax + ox + jx, ay, az + oz + jz))
    rng.shuffle(candidates)
    return candidates[: int(count)]


def build_bot_values(cfg, *, nickname, character_type, gender):
    """Min create props from BOT_ENTITIES.md (RO-068). Mask everything else."""
    return {
        "mapID": bf.i32(int(cfg["map_id"])),
        "characterType": _u32(character_type),
        "nickname": bwdefs.blob(nickname.encode("utf-8")),
        "robotVisible": _bool(1),
        "hp": bf.i32(int(cfg["hp"])),
        "maxHp": bf.i32(int(cfg["max_hp"])),
        "gender": bf.i32(int(gender)),
        "level": bf.i32(int(cfg["level"])),
        "battleState": bf.i8(0),
        "pose": bf.i8(0),
    }


def _nickname_for(cfg, index):
    names = list(cfg.get("nicknames") or [])
    if index < len(names):
        return str(names[index])
    return "Bot%02d" % (index + 1)


def _character_for(cfg, index, rng):
    types = list(cfg.get("character_types") or [20001, 20002])
    if not types:
        types = [20001]
    # Deterministic pick: cycle with seed-offset, not live random without seed.
    return int(types[(index + int(rng.randrange(len(types)))) % len(types)])


def _gender_for(character_type):
    # hero_rules / LOBBY_FINDINGS: 20001 male / 20002 female.
    return 2 if int(character_type) == 20002 else 1


class BotModule:
    """Owns Robot bot entities for one MatchSession."""

    def __init__(self, session, *, bots_data_path=None, bot_count=None, seed=None):
        self.session = session
        self.cfg = load_bots_config(bots_data_path)
        if seed is not None:
            self.cfg["seed"] = int(seed)
        self.bot_count_override = bot_count
        self.bot_ids = []
        self.positions = []
        self.alive_num = None
        self.created = False
        self.removed = False
        self._orig_close = None

    def start(self):
        if self.created or self.session.closed:
            return
        # Capture close at start() so deferred register chains after space/plane wraps.
        self._orig_close = self.session.close
        n = (
            int(self.bot_count_override)
            if self.bot_count_override is not None
            else resolve_bot_count(self.session)
        )
        if n < 0:
            n = 0
        seed = int(self.cfg["seed"])
        positions = place_bots(
            n,
            seed=seed,
            anchor=self.cfg["anchor"],
            spacing=self.cfg["spacing"],
        )
        yaw = float(self.cfg["yaw"])
        rng = random.Random(seed)
        self.bot_ids = []
        self.positions = []
        create_len = 0
        for i in range(n):
            eid = self.session.alloc_bot_id()
            nick = _nickname_for(self.cfg, i)
            ctype = _character_for(self.cfg, i, rng)
            gender = _gender_for(ctype)
            pos = positions[i] if i < len(positions) else tuple(self.cfg["anchor"])
            values = build_bot_values(
                self.cfg, nickname=nick, character_type=ctype, gender=gender
            )
            body = bf.create_entity(
                eid,
                ROBOT_ENTITY,
                pos=pos,
                direction=(yaw, 0.0, 0.0),
                values=values,
            )
            self.session.enqueue(body)
            self.bot_ids.append(eid)
            self.positions.append(pos)
            bot_runtime = pe.new_bot_player(
                player_id="bot:%s" % eid,
                entity_id=eid,
                nickname=nick,
                max_health=float(self.cfg["max_hp"]),
                position=pos,
            )
            self.session.combatants[bot_runtime.player_id] = bot_runtime
            prt = getattr(self.session, "player_runtime_module", None)
            if prt is not None and hasattr(prt, "register_bot"):
                prt.register_bot(bot_runtime)
            create_len = len(body)

        self.alive_num = resolve_alive_num(self.session, bot_count=n)
        space = getattr(self.session, "space_module", None)
        space_id = self.session.alloc_space_id()
        if space is not None:
            space_id = getattr(space, "space_id", space_id)
            if hasattr(space, "defaults") and isinstance(space.defaults, dict):
                space.defaults["aliveNum"] = int(self.alive_num)
        self.session.enqueue(
            bf.update_property(
                "BattleGroundSpace",
                "aliveNum",
                bf.i32(int(self.alive_num)),
                eid=space_id,
            )
        )

        self.created = True
        self.session.bots_module = self
        self.session.close = self._close_with_cleanup
        self.session._log(
            "      [BATTLE] bots module spawn n=%s eids=%s..%s aliveNum=%s seed=%s type=%s (~%dB create)"
            % (
                n,
                self.bot_ids[0] if self.bot_ids else None,
                self.bot_ids[-1] if self.bot_ids else None,
                self.alive_num,
                seed,
                bf.client_type(ROBOT_ENTITY),
                create_len,
            )
        )

    def remove(self):
        if self.removed:
            return
        if self.created and not self.session.closed:
            for eid in self.bot_ids:
                self.session.enqueue(bf.leave_aoi(eid))
        self.removed = True

    def _close_with_cleanup(self):
        try:
            self.remove()
        finally:
            if self._orig_close is not None:
                self._orig_close()
            else:
                type(self.session).close(self.session)


def register(session):
    """MatchSession module entry point (GATEWAY_BATTLE_SESSION.md).

    Deferred start so alphabetically later solo_fill.py and space.py attach
    before we read bot_count and update aliveNum.
    """
    mod = BotModule(session)
    session.schedule(0.0, _deferred_start, mod)
    return mod


def _deferred_start(mod):
    if mod.session.closed:
        return
    mod.start()
    # Plane (and other modules) may also defer-wrap session.close after us.
    # Re-chain once more at the same tick so bot leaveAoI still runs on end.
    mod.session.schedule(0.0, _ensure_close_hook, mod)


def _ensure_close_hook(mod):
    if mod.session.closed or not mod.created:
        return
    current = mod.session.close
    if current is mod._close_with_cleanup:
        return
    mod._orig_close = current
    mod.session.close = mod._close_with_cleanup
