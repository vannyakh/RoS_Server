"""Split one server->client Mercury bundle into reliable fragments the client can reassemble.

BigWorld's receiver (Bundle::iterator::unpack) reads every message header from a single packet:
when `offset + headerSize > bodyEnd` it logs "Not enough data on stream ... for header" and
"Got corrupted message header", and the whole fragmented bundle is dropped. Only the message
*payload* may continue into the next fragment (Bundle::iterator::data copies it across packets).

The gateway used to cut a bundle every FRAG_BODY bytes without looking at message boundaries.
Whether a cut fell inside a 2-3 byte header depended on the lobby data, so the login bundle
reached the lobby only some of the time. `split_bundle` cuts so that no header (including the
4-byte extended length of a var8/var16 message whose length field is all 0xFF) crosses a
fragment boundary.

Header sizes per message id (this client, server->client direction):
  0x00            authenticate, fixed 4
  0x01-0x62       ClientInterface, from extract/message_map.txt (wire id = map seq - 21)
  0xC0-0xFC       shortEntityMessage, var8   (libclient registration loop @+0x93d150)
  0x80-0xBF, 0xFD-0xFF  longEntityMessage, var16
"""

import struct

FIXED, VAR = "fixed", "var"

# (style, param) for ClientInterface wire ids 0..98. VAR param = length-field width in bytes,
# FIXED param = payload size. Source: RosGG extract/message_map.txt seq 21+id.
_CLIENT_INTERFACE = {
    0x00: (FIXED, 4),    # authenticate
    0x01: (FIXED, 4),    # bandwidthNotification
    0x02: (FIXED, 1),    # updateFrequencyNotification
    0x03: (FIXED, 4),    # setGameTime
    0x04: (FIXED, 1),    # resetEntities
    0x05: (VAR, 2),      # createBasePlayer
    0x06: (VAR, 2),      # createCellPlayer
    0x07: (VAR, 2),      # spaceData
    0x08: (FIXED, 13),   # spaceViewportInfo
    0x09: (VAR, 2),      # createEntity
    0x0A: (VAR, 2),      # updateEntity
    0x0B: (FIXED, 5),    # enterAoI
    0x0C: (FIXED, 6),    # enterAoIThruViewport
    0x0D: (FIXED, 9),    # enterAoIOnVehicle
    0x0E: (FIXED, 5),    # partialUpdate
    0x0F: (VAR, 2),      # leaveAoI
    0x10: (FIXED, 1),    # tickSync
    0x11: (FIXED, 1),    # relativePositionReference
    0x12: (FIXED, 1),    # setSpaceViewport
    0x13: (FIXED, 4),    # setVehicle
    0x14: (FIXED, 4),    # stayPut
    0x15: (FIXED, 1),    # stayPutAlias
    0x16: (FIXED, 4),    # historyEventBegin
    0x17: (FIXED, 1),    # historyEventEnd
    0x58: (FIXED, 30),   # detailedPosition
    0x59: (FIXED, 36),   # forcedPosition
    0x5A: (FIXED, 5),    # controlEntity
    0x5B: (VAR, 2),      # voiceData
    0x5C: (VAR, 2),      # restoreClient
    0x5D: (VAR, 2),      # restoreBaseApp
    0x5E: (FIXED, 8),    # versionPointIdentity
    0x5F: (FIXED, 34),   # versionPointSummary
    0x60: (VAR, 2),      # resourceFragment
    0x61: (FIXED, 8),    # resourceVersionStatus
    0x62: (FIXED, 1),    # loggedOff
}
# avatarUpdate* family, wire 0x18-0x57 (map seq 45-108), all fixed size.
_AVATAR_UPDATE_SIZES = (
    14, 12, 13, 11, 12, 10, 11, 9, 15, 13, 14, 12, 13, 11, 12, 10,
    12, 10, 11, 9, 10, 8, 9, 7, 9, 7, 8, 6, 7, 5, 6, 4,
    11, 9, 10, 8, 9, 7, 8, 6, 12, 10, 11, 9, 10, 8, 9, 7,
    9, 7, 8, 6, 7, 5, 6, 4, 6, 4, 5, 3, 4, 2, 3, 1,
)
for _i, _n in enumerate(_AVATAR_UPDATE_SIZES):
    _CLIENT_INTERFACE[0x18 + _i] = (FIXED, _n)


def message_style(msg_id):
    """(style, param) of a server->client message id, or None when the id is unknown."""
    if msg_id >= 0x80:
        return (VAR, 1) if 0xC0 <= msg_id <= 0xFC else (VAR, 2)
    return _CLIENT_INTERFACE.get(msg_id)


def parse_messages(body):
    """Walk a bundle body. Returns ([(start, header_len, end)], tail_start).
    tail_start is len(body) when every message parsed, else the offset of the first message
    that could not be parsed (unknown id or truncated)."""
    out, i, n = [], 0, len(body)
    while i < n:
        style = message_style(body[i])
        if style is None:
            return out, i
        kind, param = style
        if kind == FIXED:
            hdr, length = 1, param
        else:
            if i + 1 + param > n:
                return out, i
            length = int.from_bytes(body[i + 1:i + 1 + param], "little")
            hdr = 1 + param
            if length == (1 << (8 * param)) - 1:          # extended length: int32 follows
                if i + hdr + 4 > n:
                    return out, i
                length = struct.unpack_from("<I", body, i + hdr)[0]
                hdr += 4
        end = i + hdr + length
        if end > n:
            return out, i
        out.append((i, hdr, end))
        i = end
    return out, n


def split_bundle(body, max_body):
    """Cut `body` into fragments of at most `max_body` bytes with no message header split
    across two fragments. Payloads may span fragments (the client joins them). Bytes after
    an unparseable message are cut at fixed size, as before."""
    if max_body < 8:
        raise ValueError("max_body too small")
    msgs, _tail = parse_messages(body)
    cuts, cs = [], 0
    for start, hdr, end in msgs:
        if start + hdr > cs + max_body:                    # header would cross the boundary
            cuts.append(start)
            cs = start
        while end > cs + max_body:                         # payload spans fragments
            cs += max_body
            cuts.append(cs)
    while len(body) > cs + max_body:                       # unparsed tail: old fixed cuts
        cs += max_body
        cuts.append(cs)
    bounds = [0] + [c for c in cuts if 0 < c < len(body)] + [len(body)]
    return [body[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]


def header_split_points(body, max_body):
    """Message headers that a blind every-`max_body` slice would cut (diagnostics/tests)."""
    msgs, _ = parse_messages(body)
    bad = []
    for start, hdr, _end in msgs:
        k = (start // max_body + 1) * max_body
        if start < k < start + hdr:
            bad.append(start)
    return bad
