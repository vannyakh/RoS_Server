"""In-match client → server cell-method decoder (RO-060).

Loads names from ``server/extract/battle_cell_exposed.json`` (RO-057). Framing matches
``athlete_requests.decode`` style for the lobby: msgid ``0x80|k`` (var16 length),
payload = entity id u32 LE + optional extended sub-byte + args.

Rules from RO-057 review:

- ``0xBC`` / ``0xBD`` are BattleGroundAvatar **extended cell-method** ids (eff=60),
  not a dedicated position channel.
- Position uses ClientInterface message 3; **layout is unknown** — do not invent.
- Apply ``EXPOSED_SHIFT=2`` for Avatar wire indices ``>= 60``.
- ``requestGetOffPlane`` may carry trailing ``ffffffff`` despite an empty .def
  signature; keep those bytes as observed args (length quirk).

Unknown ids, truncated frames, and oversized lengths never raise: one log line
each (unknown ids once per key). This is a private-gateway decode helper, not
original Rules of Survival compatibility evidence.
"""

from __future__ import annotations

import json
import os
import struct
from typing import Callable, NamedTuple, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXTRACT = os.path.join(_HERE, "..", "extract", "battle_cell_exposed.json")

# Framing / bounds (untrusted input).
MSGID_MIN = 0x80
MSGID_MAX = 0xBF
MAX_VAR16_LEN = 0xFFFF
MAX_ENTITY_ID = 0xFFFFFFFF
MAX_LOG_HEX = 64

# Entity id ranges used by this gateway (same as battle.session / battle_flow).
SPACE_ENTITY_ID = int(os.environ.get("SPACE_ENTITY_ID", "20001"))
PLANE_ENTITY_ID = int(os.environ.get("PLANE_ENTITY_ID", "20002"))
PROP_ID_BASE = int(os.environ.get("PROP_ENTITY_ID_BASE", "30000"))

# Avatar client table vs raw .def (LOBBY_FINDINGS / RO-057).
EXPOSED_SHIFT = int(os.environ.get("EXPOSED_SHIFT", "2"))
EXPOSED_SHIFT_FROM = int(os.environ.get("EXPOSED_SHIFT_FROM", "60"))

# Suspected client position path; layout not verified for this task.
CLIENT_INTERFACE_POSITION_MSG = 3
POSITION_LAYOUT_STATUS = "unknown"

LogFn = Callable[..., None]

_tables = None
_unknown_logged: set[str] = set()
_position_logged = False


class CellCall(NamedTuple):
    """One decoded in-match cell-method call."""

    entity_id: int
    entity: str
    method: str
    args: bytes
    verified: bool = False


def _load():
    """Cache per-entity method lists and framing metadata from the RO-057 extract."""
    global _tables
    if _tables is not None:
        return _tables
    with open(_EXTRACT, encoding="utf-8") as f:
        raw = json.load(f)
    tables = {}
    for name, block in raw.get("entities", {}).items():
        methods = list(block.get("methods") or [])
        by_index = {int(m["index"]): m for m in methods}
        tables[name] = {
            "eff": int(block.get("eff", 62)),
            "exposed_count": int(block.get("exposed_count", len(methods))),
            "methods": methods,
            "by_index": by_index,
        }
    _tables = tables
    return _tables


def reset_log_state():
    """Clear once-only log keys (tests)."""
    _unknown_logged.clear()
    global _position_logged
    _position_logged = False


def entity_type_of(entity_id: int) -> str:
    """Map a target entity id to the extract entity class used for the method table."""
    eid = int(entity_id) & MAX_ENTITY_ID
    if eid == SPACE_ENTITY_ID:
        return "BattleGroundSpace"
    if eid == PLANE_ENTITY_ID:
        return "Plane"
    if eid >= PROP_ID_BASE:
        return "DtsProp"
    return "BattleGroundAvatar"


def _clamp_eid(raw: int) -> int:
    return int(raw) & MAX_ENTITY_ID


def _bound_len(n: int) -> int:
    if n < 0:
        return 0
    return min(int(n), MAX_VAR16_LEN)


def _hex_preview(data: bytes) -> str:
    if len(data) <= MAX_LOG_HEX:
        return data.hex()
    return data[:MAX_LOG_HEX].hex() + "…"


def _log_once(key: str, message: str, log: LogFn) -> None:
    if key in _unknown_logged:
        return
    _unknown_logged.add(key)
    log(message)


def split_frame(data: bytes) -> Optional[tuple[int, bytes, str]]:
    """Split ``msgid | var16_le | payload``.

    Returns ``(msgid, payload, None)`` on success, or ``(None, b"", reason)`` when
    the frame is truncated / oversized / empty. Never raises.
    """
    if not data:
        return None, b"", "empty"
    if len(data) < 3:
        return None, b"", "truncated"
    msgid = data[0]
    length = struct.unpack_from("<H", data, 1)[0]
    length = _bound_len(length)
    if length > MAX_VAR16_LEN:
        return None, b"", "oversized"
    need = 3 + length
    if len(data) < need:
        return None, b"", "truncated"
    # Extra trailing bytes beyond the declared length are ignored (not an error).
    return msgid, data[3:need], None


def decode(msgid: int, payload: bytes, *, log: Optional[LogFn] = None) -> Optional[CellCall]:
    """Decode one cell-method call.

    Returns ``CellCall(entity_id, entity, method, args, verified)`` or ``None``
    when the msgid is out of range, the payload is truncated, or the method index
    is unknown. Never raises. Unknown / bad frames produce at most one log line
    per distinct key when ``log`` is set.
    """
    log = log or (lambda *_a, **_k: None)
    try:
        if payload is None:
            payload = b""
        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload)
        msgid = int(msgid) & 0xFF
        if not (MSGID_MIN <= msgid <= MSGID_MAX):
            _log_once(
                f"msgid:{msgid:02x}",
                f"      [BATTLE] ignore unknown msgid=0x{msgid:02x} payload={_hex_preview(payload)}",
                log,
            )
            return None
        if len(payload) > MAX_VAR16_LEN:
            _log_once(
                f"over:{msgid:02x}:{len(payload)}",
                f"      [BATTLE] ignore oversized msgid=0x{msgid:02x} len={len(payload)}",
                log,
            )
            return None
        if len(payload) < 4:
            _log_once(
                f"trunc:{msgid:02x}:{len(payload)}",
                f"      [BATTLE] ignore truncated msgid=0x{msgid:02x} payload={_hex_preview(payload)}",
                log,
            )
            return None

        eid = _clamp_eid(struct.unpack_from("<I", payload, 0)[0])
        entity = entity_type_of(eid)
        tables = _load()
        block = tables.get(entity)
        if block is None:
            _log_once(
                f"entity:{entity}",
                f"      [BATTLE] ignore unknown entity class {entity} eid={eid} "
                f"msgid=0x{msgid:02x} payload={_hex_preview(payload)}",
                log,
            )
            return None

        tab = block["methods"]
        eff = int(block["eff"])
        # Prefer extract eff; fall back to the shared formula when missing.
        if eff <= 0:
            n = max(int(block["exposed_count"]), len(tab))
            eff = 62 - (n + 192) // 255

        j = msgid - MSGID_MIN
        args = bytes(payload[4:])
        if j < eff:
            k = j
        else:
            if not args:
                _log_once(
                    f"exttrunc:{msgid:02x}:{eid}",
                    f"      [BATTLE] ignore truncated extended msgid=0x{msgid:02x} "
                    f"eid={eid} payload={_hex_preview(payload)}",
                    log,
                )
                return None
            k = eff + ((j - eff) << 8) + args[0]
            args = args[1:]

        if entity == "BattleGroundAvatar" and k >= EXPOSED_SHIFT_FROM:
            k -= EXPOSED_SHIFT

        if k < 0 or k >= len(tab):
            _log_once(
                f"idx:{entity}:{k}",
                f"      [BATTLE] ignore unknown {entity} exposed#{k} "
                f"msgid=0x{msgid:02x} eid={eid} payload={_hex_preview(payload)}",
                log,
            )
            return None

        meta = tab[k]
        name = str(meta.get("name") or f"exposed#{k}")
        verified = bool(meta.get("verified"))
        # Length quirk: empty .def signatures may still carry observed trailing
        # bytes (requestGetOffPlane → ffffffff). Keep args as on the wire.
        return CellCall(eid, entity, name, args, verified)
    except Exception as exc:  # noqa: BLE001 — untrusted bytes must never escape
        _log_once(
            f"err:{type(exc).__name__}",
            f"      [BATTLE] ignore decode error {type(exc).__name__}: {exc}",
            log,
        )
        return None


def decode_frame(data: bytes, *, log: Optional[LogFn] = None) -> Optional[CellCall]:
    """Decode a full ``msgid|var16|payload`` frame. Never raises."""
    log = log or (lambda *_a, **_k: None)
    try:
        if data is None:
            data = b""
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        msgid, payload, reason = split_frame(data)
        if reason == "truncated":
            _log_once(
                f"frame:trunc:{_hex_preview(data)}",
                f"      [BATTLE] ignore truncated frame hex={_hex_preview(data)}",
                log,
            )
            return None
        if reason == "oversized":
            _log_once(
                f"frame:over:{_hex_preview(data[:8])}",
                f"      [BATTLE] ignore oversized frame hex={_hex_preview(data)}",
                log,
            )
            return None
        if reason or msgid is None:
            _log_once(
                f"frame:bad:{reason}",
                f"      [BATTLE] ignore bad frame ({reason}) hex={_hex_preview(data)}",
                log,
            )
            return None
        return decode(msgid, payload, log=log)
    except Exception as exc:  # noqa: BLE001
        _log_once(
            f"frameerr:{type(exc).__name__}",
            f"      [BATTLE] ignore frame error {type(exc).__name__}: {exc}",
            log,
        )
        return None


def encode_call(entity: str, method: str, entity_id: int, args: bytes = b"") -> bytes:
    """Build a framed cell call from extract indices (tests / fixtures).

    Uses **client** sub-bytes for Avatar methods with ``client_sub_byte`` set so the
    wire matches live captures after ``EXPOSED_SHIFT`` on decode. Space / DtsProp
    use the raw exposed index (no shift).
    """
    tables = _load()
    block = tables[entity]
    meta = next(m for m in block["methods"] if m["name"] == method)
    idx = int(meta["index"])
    eid = _clamp_eid(entity_id)
    args = bytes(args or b"")
    if len(args) > MAX_VAR16_LEN - 5:
        args = args[: MAX_VAR16_LEN - 5]

    if entity == "BattleGroundAvatar" and idx >= EXPOSED_SHIFT_FROM:
        # Live client index is raw + EXPOSED_SHIFT (see extract client_sub_byte).
        wire_k = idx + EXPOSED_SHIFT
    else:
        wire_k = idx

    eff = int(block["eff"])
    if wire_k < eff:
        msgid = MSGID_MIN | wire_k
        payload = struct.pack("<I", eid) + args
    else:
        k = wire_k - eff
        msgid = MSGID_MIN | (eff + (k >> 8))
        payload = struct.pack("<I", eid) + bytes([k & 0xFF]) + args

    length = _bound_len(len(payload))
    payload = payload[:length]
    return bytes([msgid]) + struct.pack("<H", length) + payload


class PositionTracker:
    """Session-facing position holder.

    ClientInterface message 3 is the suspected position path, but its field layout
    is **unknown** in RO-057 evidence. This tracker records that status and never
    invents xyz from ``0xBC``/``0xBD`` or from msg 3 bytes.
    """

    def __init__(self):
        self.status = POSITION_LAYOUT_STATUS
        self.last = None  # type: ignore[assignment]
        self.last_raw = None  # type: ignore[assignment]

    def note_client_interface(self, msgid: int, payload: bytes = b"", *, log: Optional[LogFn] = None) -> None:
        """Observe a ClientInterface message. Msg 3 stays ``unknown`` (no parse)."""
        global _position_logged
        log = log or (lambda *_a, **_k: None)
        try:
            msgid = int(msgid) & 0xFF
            payload = bytes(payload or b"")
            if len(payload) > MAX_VAR16_LEN:
                payload = payload[:MAX_VAR16_LEN]
            if msgid != CLIENT_INTERFACE_POSITION_MSG:
                return
            self.status = POSITION_LAYOUT_STATUS
            self.last = None
            self.last_raw = payload
            if not _position_logged:
                _position_logged = True
                log(
                    f"      [BATTLE] position ClientInterface msg "
                    f"{CLIENT_INTERFACE_POSITION_MSG} layout={POSITION_LAYOUT_STATUS} "
                    f"hex={_hex_preview(payload)}"
                )
        except Exception as exc:  # noqa: BLE001
            log(f"      [BATTLE] position note ignored ({type(exc).__name__})")


def decode_position(msgid: int, payload: bytes = b"", *, tracker: Optional[PositionTracker] = None,
                    log: Optional[LogFn] = None) -> None:
    """Position decode entry: always unknown; optionally store raw on ``tracker``."""
    t = tracker or PositionTracker()
    t.note_client_interface(msgid, payload, log=log)
    return None
