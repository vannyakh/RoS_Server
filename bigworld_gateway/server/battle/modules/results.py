"""Match end: result screen wire, RoS_Server report, session teardown (RO-071).

Gateway-local placement and rank deltas — not original RoS values. When the session
has ``return_to_lobby`` or ``gate`` set (future ``ros_server`` hook), schedules lobby
return after the result UI delay. Otherwise only the client result bytes and cleanup run.

Other modules call ``session.results_module.eliminate_player`` / ``declare_victory`` or
``apply_zone_fatal`` (zone module, RO-064).
"""

from __future__ import annotations

import os
import pickle
import struct
import time
import traceback
from dataclasses import dataclass, field

import account_link
import battle_flow as bf
import bwdefs

AVATAR_ID = bf.AVATAR_ID
RESULTS_LOBBY_DELAY = float(os.environ.get("RESULTS_LOBBY_DELAY", "3.0"))


@dataclass
class MatchCounters:
    """Session stats mapped to ``GatewayMatchReport``."""

    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: int = 0
    head_shots: int = 0
    hits: int = 0
    fires: int = 0
    collect_count: int = 0
    heal_count: int = 0
    kill_distance_dm: int = 0
    move_distance_dm: int = 0
    fight_time_seconds: int = 0
    team_mode: str = "solo"
    queue: str = "total"
    started_mono: float = field(default_factory=time.monotonic)


def _gid():
    try:
        return int(account_link.current_gid())
    except (TypeError, ValueError):
        return int(os.environ.get("CBP_GID", "9000000001"))


def _nickname():
    cur = account_link.current() or {}
    return str(cur.get("nickname") or os.environ.get("BATTLE_NICK", "Player"))[:32]


def _encode_result_item(*, gid, nickname, kill, die, player_id=1, level=1, main_weapon=0, char_type=20001):
    """One ``SINGLE_BATTLE_GAME_RESULT_ITEM`` row."""
    return (
        struct.pack("<i", int(player_id))
        + bwdefs.blob(nickname.encode("utf-8"))
        + struct.pack("<Q", int(gid))
        + struct.pack("<i", int(level))
        + struct.pack("<i", int(main_weapon))
        + struct.pack("<i", int(kill))
        + struct.pack("<i", int(die))
        + struct.pack("<i", int(char_type))
        + struct.pack("<i", 0)  # rankDValue
    )


def encode_single_battle_game_result(players):
    """``SINGLE_BATTLE_GAME_RESULT`` bytes (ARRAY of items)."""
    rows = [p if isinstance(p, (bytes, bytearray)) else _encode_result_item(**p) for p in players]
    return struct.pack("<I", len(rows)) + b"".join(rows)


def encode_game_end(mode, players):
    """``BattleGroundSpace.gameEnd(INT8, SINGLE_BATTLE_GAME_RESULT)`` args."""
    return struct.pack("<b", int(mode)) + encode_single_battle_game_result(players)


def _py_arg(obj):
    return bwdefs.blob(pickle.dumps(obj, protocol=2))


def encode_on_battle_ground_result(
    *,
    map_id=700,
    mode_byte=0,
    placement,
    kills,
    extra_score=0,
    extra=None,
    meta=None,
):
    """``BattleGroundAvatar.onBattleGroundResult`` args (7 fields)."""
    extra = extra if extra is not None else {}
    meta = meta if meta is not None else {}
    return (
        struct.pack("<i", int(map_id))
        + struct.pack("<b", int(mode_byte))
        + struct.pack("<i", int(placement))
        + struct.pack("<i", int(kills))
        + struct.pack("<i", int(extra_score))
        + _py_arg(extra)
        + _py_arg(meta)
    )


def build_match_report(counters, *, placement, rank_score_delta=None):
    """Body for ``account_link.record_match``."""
    fight = counters.fight_time_seconds
    if fight <= 0:
        fight = max(0, int(time.monotonic() - counters.started_mono))
    delta = rank_score_delta
    if delta is None:
        if placement == 1:
            delta = 25
        elif placement <= 5:
            delta = 5
        else:
            delta = -5
    return {
        "queue": counters.queue,
        "team_mode": counters.team_mode,
        "placement": int(placement),
        "kills": int(counters.kills),
        "deaths": max(1, int(counters.deaths)) if placement > 1 else int(counters.deaths),
        "assists": int(counters.assists),
        "damage": int(counters.damage),
        "head_shots": int(counters.head_shots),
        "hits": int(counters.hits),
        "fires": int(counters.fires),
        "fight_time_seconds": int(fight),
        "collect_count": int(counters.collect_count),
        "heal_count": int(counters.heal_count),
        "kill_distance_dm": int(counters.kill_distance_dm),
        "move_distance_dm": int(counters.move_distance_dm),
        "rank_score_delta": int(delta),
    }


def _starting_alive(session):
    fill = getattr(session, "solo_fill", None)
    if fill is not None and hasattr(fill, "alive_num"):
        return int(fill.alive_num)
    space = getattr(session, "space_module", None)
    if space is not None and getattr(space, "defaults", None):
        return int(space.defaults.get("aliveNum", 100))
    return int(os.environ.get("SPACE_ALIVE_NUM", "100"))


def apply_lobby_return(gate, addr, bf_key):
    """Mirror ``ros_server`` quit-match path (call from the gate when RO-071 hooks land)."""
    gate.__dict__.setdefault("_matches", {}).pop(addr, None)
    end = getattr(gate, "_end_match_session", None)
    if callable(end):
        end(addr)
    if getattr(gate, "_in_battle", None) is not None:
        gate._in_battle[addr] = False
    if getattr(gate, "_athlete_sent", None) is not None:
        gate._athlete_sent.pop(addr, None)
    if getattr(gate, "_hall_entered", None) is not None:
        gate._hall_entered.pop(addr, None)
    transition = getattr(gate, "_transition_to_athlete", None)
    if callable(transition):
        transition(addr, bytes(bf_key))


class ResultsModule:
    """One match end sequence per session."""

    def __init__(self, session):
        self.session = session
        self.counters = MatchCounters()
        self.ended = False
        self._reported = False
        self._eliminated = 0
        self._alive_start = _starting_alive(session)
        self.space_id = getattr(session, "space_id", bf.SPACE_ID)

    def _default_death_placement(self):
        remaining = max(0, self._alive_start - self._eliminated - 1)
        return remaining + 1

    def eliminate_player(self, *, placement=None, reason="death"):
        if placement is None:
            placement = self._default_death_placement()
        self.counters.deaths = max(self.counters.deaths, 1)
        self._eliminated += 1
        self.end_match(placement=int(placement), victory=False, reason=reason)

    def declare_victory(self, *, placement=1, kills=None):
        if kills is not None:
            self.counters.kills = int(kills)
        self.end_match(placement=int(placement), victory=True, reason="victory")

    def apply_zone_fatal(self, *, placement=None):
        """Zone poison killed the player (RO-064 calls this)."""
        self.eliminate_player(placement=placement, reason="zone")

    def end_match(self, *, placement, victory=False, reason="end"):
        if self.ended or self.session.closed:
            return
        self.ended = True

        gid = _gid()
        nick = _nickname()
        kills = self.counters.kills
        deaths = 0 if victory else 1

        player_row = {
            "gid": gid,
            "nickname": nick,
            "kill": kills,
            "die": deaths,
            "player_id": 1,
        }
        game_end_args = encode_game_end(1, [player_row])
        result_args = encode_on_battle_ground_result(
            placement=placement,
            kills=kills,
            extra={"reason": reason, "victory": victory},
        )

        bodies = []
        bodies.append(bf.entity_method(self.space_id, "BattleGroundSpace", "gameEnd", game_end_args))
        if not victory:
            bodies.append(
                bf.client_call("BattleGroundAvatar", "onBattleGroundDie", AVATAR_ID, _py_arg({"placement": placement}))
            )
        bodies.append(bf.client_call("BattleGroundAvatar", "onBattleGroundResult", AVATAR_ID, result_args))
        alive_left = 0 if victory else max(0, self._alive_start - self._eliminated - 1)
        if alive_left >= 0:
            bodies.append(
                bf.update_property("BattleGroundSpace", "aliveNum", bf.i32(alive_left), eid=self.space_id)
            )
        for chunk in bodies:
            self.session.enqueue(chunk)

        self._send_match_report(placement)
        self._teardown_session()
        self.session.schedule(RESULTS_LOBBY_DELAY, self._return_to_lobby)
        self.session._log(
            "      [BATTLE] results end placement=%s victory=%s reason=%s alive_left=%s"
            % (placement, victory, reason, alive_left)
        )

    def _send_match_report(self, placement):
        if self._reported:
            return
        self._reported = True
        report = build_match_report(self.counters, placement=placement)
        try:
            profile = account_link.record_match(report)
            if profile is None:
                self.session._log("      [BATTLE] results record_match skipped (not linked or refused)")
            else:
                self.session._log(
                    "      [BATTLE] results record_match ok rank_score=%s"
                    % profile.get("rank_score", "?")
                )
        except Exception as e:
            self.session._log(f"      [BATTLE] results record_match failed: {e!r}")
            self.session._log(traceback.format_exc())

    def _teardown_session(self):
        plane = getattr(self.session, "plane_module", None)
        if plane is not None and hasattr(plane, "remove"):
            try:
                plane.remove()
            except Exception as e:
                self.session._log(f"      [BATTLE] results plane remove failed: {e!r}")
        space = getattr(self.session, "space_module", None)
        if space is not None and hasattr(space, "remove"):
            try:
                space.remove()
            except Exception as e:
                self.session._log(f"      [BATTLE] results space remove failed: {e!r}")
        bots = getattr(self.session, "bots_module", None)
        if bots is not None and hasattr(bots, "remove_all"):
            try:
                bots.remove_all()
            except Exception as e:
                self.session._log(f"      [BATTLE] results bots remove failed: {e!r}")

    def _return_to_lobby(self):
        if self.session.closed:
            return
        cb = getattr(self.session, "return_to_lobby", None)
        if callable(cb):
            try:
                cb()
            except Exception as e:
                self.session._log(f"      [BATTLE] results return_to_lobby callback failed: {e!r}")
        gate = getattr(self.session, "gate", None)
        bf_key = getattr(self.session, "bf_key", None)
        if gate is not None:
            fresh = getattr(gate, "_last_bf", {}).get(self.session.addr)
            if fresh is not None:
                bf_key = bytes(fresh)
        if gate is not None and bf_key is not None:
            try:
                apply_lobby_return(gate, self.session.addr, bf_key)
            except Exception as e:
                self.session._log(f"      [BATTLE] results apply_lobby_return failed: {e!r}")
        else:
            self.session._log(
                "      [BATTLE] results lobby return pending (set session.gate + bf_key or return_to_lobby)"
            )
        self.session.close()


def _inbound_handler(session, mod):
    def _handle(msgid, payload):
        if mod.ended:
            return b""
        req = bf.decode_request(msgid, payload)
        if req is None:
            return None
        _eid, entity, name, _args = req
        if entity == "BattleGroundAvatar" and name in (
            "suicideFromClient",
            "requestLeaveSpaceBeforeWin",
        ):
            mod.eliminate_player(reason=name)
            return b""
        return None

    return _handle


def register(session):
    """MatchSession entry point."""
    mod = ResultsModule(session)
    session.results_module = mod
    session.on_inbound(lambda mid, _pay: 0x80 <= mid <= 0xBF, _inbound_handler(session, mod))
    session._log("      [BATTLE] results module registered")
    return mod