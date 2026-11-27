# Protocol mapping (mobile restoration index)

This repository does **not** publish invented numeric opcodes. Use only documented names and extract tables.

| Layer | Mapping source |
| --- | --- |
| Athlete base methods (lobby) | `bigworld_gateway/server/athlete_requests.py` + `bigworld_gateway/server/extract/athlete_base_exposed.json` |
| Battle cell / entity methods | `bigworld_gateway/server/battle_flow.py` + research docs under `bigworld_gateway/docs/` |
| createEntity framing | [CREATE_ENTITY_FRAMING.md](../bigworld_gateway/docs/CREATE_ENTITY_FRAMING.md) |
| Message map extract | `bigworld_gateway/server/extract/message_map.txt` |
| This server's JSON messages | `app/networking/protocol.py` + [API_CONTRACT.md](API_CONTRACT.md) |
| Research (non-authoritative) | [NETWORK_PROTOCOL.md](NETWORK_PROTOCOL.md), [reverse-engineering/NETWORK_INTERFACE.md](reverse-engineering/NETWORK_INTERFACE.md) |

Open research tasks: **RO-056** (createEntity framing proof), **RO-057** (in-match request ids).
