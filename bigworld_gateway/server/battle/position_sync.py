"""Bridge ClientInterface position msg 3 into PlayerRuntimeState and zone (evidenced layout).

Uses the same xyz offset as ``battle_flow.Match.on_position`` (8-byte header + 3×float32).
Does not invent a new layout. RO-057 still marks msg 3 as formally unknown; this path
only mirrors the historical parser used for landing detection.
"""

from __future__ import annotations

import struct


def try_sync_xyz(session, payload: bytes) -> tuple[float, float, float] | None:
    """Update session.player and zone_module from a msg-3 payload. Returns xyz or None."""
    if session is None or len(payload) < 20:
        return None
    try:
        x, y, z = struct.unpack_from("<3f", payload, 8)
    except struct.error:
        return None
    player = getattr(session, "player", None)
    if player is not None:
        player.sync_position(x, y, z)
    zone = getattr(session, "zone_module", None)
    if zone is not None and hasattr(zone, "track_position"):
        zone.track_position(x, z)
    return (float(x), float(y), float(z))