# Game rules

Date: 2026-11-11. Every number on this page is this server's independent design. The full audit, including phases, loot weights, healing, and vehicles, is `docs/GAMEPLAY_SYSTEMS.md`. Change a number there only in the same change as `app/game` and its tests.

Original Rules of Survival movement, weapon, armor, vehicle, zone, and reward values are UNKNOWN. The original client was observed only as far as the patch gate.

## Where the numbers live

| Rule | Independent value in this server | Status for this server | Original value |
| --- | --- | --- | --- |
| Map square | 200 by 200 | CONFIRMED in `app/game/rules.py` (`map_size`). DOCUMENTED in `docs/GAMEPLAY_SYSTEMS.md` | UNKNOWN |
| On-foot speed | 5 map units per second | CONFIRMED (`speed`) | UNKNOWN |
| Pistol damage | 22 | CONFIRMED in `app/game/items.py` | UNKNOWN |
| Rifle damage | 16 | CONFIRMED in `app/game/items.py` | UNKNOWN |
| Zone radii | 110, 70, 40, 20, 8 | CONFIRMED (`zone_radii`) | UNKNOWN |
| Zone damage per second | 1, 2, 4, 8, 16 | CONFIRMED (`zone_dps`) | UNKNOWN |
| Tick | 20 Hz | DOCUMENTED in `docs/GAME_RUNTIME.md` and `docs/GAMEPLAY_SYSTEMS.md` | UNKNOWN |
| Queue | Wait 2 seconds or reach 100 players, then fill up to 7 bots | CONFIRMED defaults in `MatchRules`. `default_rules()` can replace max players, bot fill, and queue wait from settings | UNKNOWN |
| Match clock | Countdown 3 seconds, dropping 8 seconds, zone shrink every 25 seconds, result hold 8 seconds | CONFIRMED in `MatchRules` | UNKNOWN |
| Starting health | 100 | DOCUMENTED in `docs/GAMEPLAY_SYSTEMS.md` | UNKNOWN |
| Hit radius | 1.25 | CONFIRMED | UNKNOWN |
| Pickup radius | 2.5 | CONFIRMED | UNKNOWN |
| Loot nodes | 36 | CONFIRMED | UNKNOWN |
| Pistol magazine, range, reload, cooldown | 12 rounds, range 28, reload 1.4 seconds, cooldown 0.35 seconds, ammo `light` | CONFIRMED | UNKNOWN |
| Rifle magazine, range, reload, cooldown | 30 rounds, range 70, reload 2.2 seconds, cooldown 0.12 seconds, ammo `medium` | CONFIRMED | UNKNOWN |
| Heals | `bandage` 20, `medkit` 60, health cap 100 | CONFIRMED amounts in `app/game/items.py`. The cap is DOCUMENTED in `docs/GAMEPLAY_SYSTEMS.md` | UNKNOWN |
| Vehicle | `buggy`, speed 12, 1 seat, two nodes per match | CONFIRMED. Marked in `app/game/items.py` as development numbers | UNKNOWN |
| Wallet | Starter 500 coin and 20 diamond. Skins `recruit` (free), `field_jacket` (200 coin), `night_ops` (15 diamond) | CONFIRMED in `app/services/cosmetics_service.py`. Match completion does not add coin or diamond | UNKNOWN |
| Stored results | Kills, win, and placement for humans. Bots are not written as results | DOCUMENTED in `docs/GAMEPLAY_SYSTEMS.md` | UNKNOWN |

## Authority

The tick in `app/game` decides position, damage, elimination, and the winner. Clients send `player.input` and `player.action`. Prediction and interpolation are not implemented. Teams exist as durable HTTP lobby rows. The live match does not revive teammates.

These statements are CONFIRMED as this project's design by `docs/GAME_RUNTIME.md` and `docs/GAMEPLAY_SYSTEMS.md`. They are NOT_SUPPORTED as a description of the original APK. No original match was played.

## Absent from this simulation

`docs/GAMEPLAY_SYSTEMS.md` records these as absent from the files that audit read: crouch, prone, fall damage, armor, hit locations, weapon attachments, vehicle health, team revive, spectating, and loading collision from a published map package. Original behavior for each of those is UNKNOWN.
