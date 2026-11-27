# Player inventory (depot vs battle)

| Store | Contents | Lifetime |
| --- | --- | --- |
| **Depot / hall** | Skins, owned costumes, emotes, workshop items | SQL + `/api/v1/gateway` |
| **Battle bag** | Weapons, ammo, heals, match loot | `PlayerRuntimeState.battle_inventory`, `gun_slots` — cleared each match |

Match start calls `PlayerRuntimeState.reset_battle_loadout()` so prior Solo weapons are **not** restored.

**Gateway pickup:** `battle/modules/props.py` (RO-066). **Discard / capacity:** RO-077–079.

**JSON path:** Durable HTTP inventory vs `PlayerState.inventory` in `app/game`.

Status: [PLAYER_SYSTEM_STATUS.md](PLAYER_SYSTEM_STATUS.md) section 7.