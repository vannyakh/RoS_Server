# Resource mapping (mobile restoration index)

| Resource | Location |
| --- | --- |
| Hall props / depot catalog | `bigworld_gateway/server/extract/hall_props.json`, `hallprop_prices.json` |
| Supply / supplement | `bigworld_gateway/server/extract/supplement_info.json`, `supplement_props.json` |
| Lobby reference capture | `data/reference/original_lobby.json` |
| Entity / interface names | `bigworld_gateway/server/extract/entities_names.json` |
| Hero / character rules | `bigworld_gateway/server/hero_rules.py` |
| Map id used for battle entry | Map **700** (`DtsMapBaseType.MAP_4K`) via gateway env `BATTLE_MAP` |
| Character types (historical) | 20001 human male works; 30001 robot; 10001 empty model — see LOBBY_FINDINGS |
| Store listing overrides | `app/models/store_listing.py`, Alembic `c8f3a5d27e14` |
| Game catalogs (JSON stack) | `app/models/game_data.py`, seeds under `app/database/seeds/` |

Workshop cultivate: extract + Frida under RO-095; durable compound API RO-096; gateway handler RO-097. See [RESTORATION_STATUS.md](RESTORATION_STATUS.md) section 4.
