# Gameplay systems

Audit date: 2026-11-11. This page records two different bodies of evidence.

| Body | What was read | What it proves |
| --- | --- | --- |
| This server | `app/game/rules.py`, `app/game/items.py`, `app/game/state.py`, `app/game/collision.py`, `app/game/simulate.py`, `app/core/config.py` | The independent rules the process runs today |
| Sibling client research | `research/GAMEPLAY_SYSTEMS.md` and `research/reports/PHASE-01-REPORT.md` | The original client was not observed past the patch gate |

Every number below is an independent design that exists in this repository. A test that matches these numbers shows the server agrees with itself. It does not show original Rules of Survival compatibility. Original movement, weapon, armor, vehicle, and zone numbers remain **Unknown**.

## Evidence labels

- **Confirmed:** present in the files listed above.
- **Inferred:** a reading of that code, not a second source.
- **Unknown:** not in those files and not observed on the original client.

## ROS-R01 Match flow

Confirmed. The tick default is 20 Hz (`game_tick_rate`). A human enters the in-memory queue with `lobby.join`. The queue starts a match when the oldest human has waited `queue_wait` seconds (default 2) or the queue reaches `max_players` (default 100). Up to `bot_fill` bots (default 7) fill empty seats. Bots are not queued humans.

Phases, in order: `countdown` (3 seconds), `dropping` (8 seconds), `playing`, then `ended`. During `playing`, the zone clock is 25 seconds per shrink. When the phase is `ended`, the clock runs until `result_time` (8 seconds), then the match is dissolved. The last living player is the winner. A match that started with one id and no living player ends with no winner. Results stored for humans are kills, win, and placement. Bots are not written as results.

Players spawn on the plane at `z` 40 during countdown. `jump` during `dropping` starts a parachute descent: `z` falls at `fall_speed` (10 per second) and move input steers at `glide_speed` (8 per second). The player keeps status `dropping` until `z` reaches 0, then becomes `alive`; other actions are refused with `Still parachuting`. Bots jump the same way. Everyone still on the plane or in the air is landed when `playing` starts. Health at match start is 100.

## ROS-R02 Movement

Confirmed. Input `move_x` and `move_y` are scaled so the vector length is at most 1. On foot, speed is 5 map units per second. Position is clamped to the square from 0 to `map_size` (200). If the next point lies inside an axis-aligned blocker, `slide` keeps the axis that is still free, or leaves the player in place when both axes are blocked. The player is a point. There is no crouch, prone, or fall damage.

`jump` is the plane exit. It does not raise `z` during `playing`.

Unknown. Original walk, run, crouch, prone, and fall rules.

## ROS-R03 Combat

Confirmed. A shot requires a weapon, rounds in the magazine, no reload in progress, no fire cooldown, a non-zero aim, and the shooter not seated in a vehicle. The aim is normalized. A target counts when it is alive, off the plane, in front of the aim, inside the weapon range, and within `hit_radius` 1.25 of the aim line. The closest such target takes the weapon damage after worn gear: armor removes 20/30/40 percent at level 1/2/3, then a helmet removes 10/15/20 percent. Health at 0 eliminates the target with cause `shot`, and the shooter gains one kill. There is no hit location and no head multiplier. A landed player who is eliminated drops a crate: every inventory stack and worn gear piece becomes a loot node at that spot with a shared `crate_id`. Damage dealt and distance moved on the ground are kept per match for the results table.

Unknown. Original damage, armor, and hit locations.

## ROS-R04 Weapons

Confirmed. The equipped table is only `pistol` and `rifle`.

| Weapon | Damage | Range | Magazine | Reload seconds | Cooldown seconds | Ammo item |
| --- | --- | --- | --- | --- | --- | --- |
| pistol | 22 | 28 | 12 | 1.4 | 0.35 | `light` |
| rifle | 16 | 70 | 30 | 2.2 | 0.12 | `medium` |

Reload moves ammo from the stack into the magazine, up to the magazine size. A full magazine or an empty ammo stack refuses the reload. Switching weapons stores the current magazine. A new match gives each player a pistol and 24 light ammo, with the pistol magazine already full.

Unknown. Original weapon catalog, attachments, and statistics.

## ROS-R05 Inventory

Confirmed. The live match inventory is an in-memory item-id count. A player may hold 2 primary weapons and 1 pistol (`desert_eagle` or `pistol`; the starter pistol fills the pistol slot). Other stacks stop at 200, plus 100/200/300 with a level 1/2/3 backpack; a pickup takes what fits and leaves the rest on the node. Gear (`armor_N`, `helmet_N`, `backpack_N`) is worn on pickup only when it is a higher level than the worn piece, and the old piece is dropped where the new one lay. `use` accepts `bandage` (heal 20, 2 s), `energy_drink` (35, 2.5 s), `medkit` (60, 3.2 s) and `first_aid` (80, 5 s). It starts a timed channel (`healing`, `heal_left`, scaled by `heal_time_scale`); the item is spent and health added when it ends. Using again, shooting, or being hit cancels it with the item kept. Health never passes 100 and a full-health player is refused. `attach` fits `scope_4x` (range x1.25, primary weapons with medium or heavy ammo) or `ext_mag` (+10 rounds, primary weapons with light or medium ammo) to the equipped weapon, one of each; fitted parts return to the pack when the weapon is discarded and drop with a death crate. `discard` removes one from a stack, puts it on the ground as a loot node, and clears the equipped weapon when the last copy of that weapon is discarded. Durable HTTP inventory is a separate store. This match inventory is not written as equipment slots.

Unknown. Original backpack capacity and equipment rules.

## ROS-R06 Map

Confirmed. The live match square is 200 by 200. Blockers are optional rectangles on the match. The published map catalog is a separate content system. The tick does not load terrain, doors, or collision from a published map package.

Unknown. Original terrain, buildings, roads, and spawn points. The client OBB packages were not extracted.

## ROS-R07 Loot

Confirmed. Each match places `loot_count` (90) nodes, the whole weighted table in `app/game/items.py` (`LOOT_TABLE`): ten weapons (pistol, desert_eagle, smg, vector, rifle, m14ebr, shotgun, aa12, sniper, awm), three ammo types, four heal items, the two attachments, and armor, helmet and backpack at levels 1 to 3 (weights 3, 2, 1). Positions are random in the map with a margin of 10, seeded by the match id. Pickup succeeds only for an untaken node inside radius 2.5.

Unknown. Original loot tables and spawn probabilities.

## ROS-R08 Vehicles

Confirmed. Two `buggy` nodes are placed per match, seeded by the match id. Speed is 12. Seats are 1. Boarding takes the nearest unoccupied buggy inside the pickup radius. The occupied buggy moves with the player. Shooting is refused until the player exits. These values are marked in `app/game/items.py` as development numbers.

Unknown. Original vehicle types, seats, and damage. Vehicles have no health in this simulation.

## ROS-R09 Zone

Confirmed. Radii are 110, 70, 40, 20, then 8. Damage per second outside the current circle is 1, 2, 4, 8, then 16. The first circle is centered on the map. Later circles are placed at random inside the previous circle and clamped so they stay on the map. Outside damage uses `zone_dps * dt` and can eliminate with cause `zone`. Players on the plane are not damaged.

Unknown. Original phase timing, radius, and zone damage.

## ROS-R10 Multiplayer

Confirmed. Authority stays on the server. Clients send `player.input` and `player.action`. The tick writes positions, health, and the winner. The live socket contract is `docs/NETWORK_PROTOCOL.md`. One account has one current socket. Teams exist as durable HTTP lobby rows. The live match does not revive teammates. Spectating is not implemented. Client prediction is not implemented.

The original client has no confirmed gameplay connection. It stopped on the patch list. Its protocol is not this JSON contract.

## ROS-R01b Warm-up and training

Confirmed. `warmup_island` (default off, so the old countdown on the plane is unchanged) turns the countdown into a ground warm-up: players spawn within `island_radius` (20) of the centre without a weapon and can walk. When it ends they board the plane with the starter kit. The snapshot reports `starts_in`. Training (`engine.join_training`) is a one-player match with `mode` `training`: no zone damage or shrink, no winner, no stored result, `training_dummies` (4) stationary targets that respawn at their spot when shot, and a respawn with a fresh kit when the player dies. The kit is a rifle, an M14EBR, a pistol, ammo, heals, a scope pair and an extended mag, so attachments can be tried. Independent design; the original warm-up length and training rules are Unknown.

## ROS-R10b Squads

Confirmed. `engine.set_team` puts queued players in a squad before the match; with `team_size` above 1, players without a team are grouped in queue order. Bots have no team. Knock-down, bleed-out, revive and friendly fire follow `docs/NETWORK_PROTOCOL.md`: knock health 40, bleed 30 seconds, crawl speed 1.5, revive 5 seconds to 30 health. Independent design numbers; original values are Unknown. The default `team_size` is 1, so solo play is unchanged.

## ROS-R11 Progression

Confirmed. A finished human result carries kills, win, and placement into the pending result list. Experience, currency rewards, and rank from that result are not applied by this simulation.

Confirmed. A separate account wallet starts a new player at 500 coin and 20 diamond and grants the `recruit` skin. `field_jacket` costs 200 coin. `night_ops` costs 15 diamond. Those prices are an independent catalog in `app/services/cosmetics_service.py`. Match completion does not add coin or diamond.

Unknown. Original ranking and rewards.

## Not implemented

Confirmed by absence from the files read for this audit:

- Crouch, prone, and fall damage
- Hit locations
- Weapon attachments
- Vehicle health
- Team revive and spectating
- Loading collision from a published map
- Original client packet formats

## Agent rule

Change a number in this page only in the same change as `app/game` and its tests. Keep the new number labeled as an independent design.
