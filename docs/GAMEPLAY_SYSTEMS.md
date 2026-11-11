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

Players spawn on the plane at `z` 40 during countdown. `jump` during `dropping` lands that player. Everyone still on the plane is landed when `playing` starts. Health at match start is 100.

## ROS-R02 Movement

Confirmed. Input `move_x` and `move_y` are scaled so the vector length is at most 1. On foot, speed is 5 map units per second. Position is clamped to the square from 0 to `map_size` (200). If the next point lies inside an axis-aligned blocker, `slide` keeps the axis that is still free, or leaves the player in place when both axes are blocked. The player is a point. There is no crouch, prone, or fall damage.

`jump` is the plane exit. It does not raise `z` during `playing`.

Unknown. Original walk, run, crouch, prone, and fall rules.

## ROS-R03 Combat

Confirmed. A shot requires a weapon, rounds in the magazine, no reload in progress, no fire cooldown, a non-zero aim, and the shooter not seated in a vehicle. The aim is normalized. A target counts when it is alive, off the plane, in front of the aim, inside the weapon range, and within `hit_radius` 1.25 of the aim line. The closest such target takes the weapon's flat damage. Health at 0 eliminates the target with cause `shot`, and the shooter gains one kill. There is no armor, no hit location, and no head multiplier.

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

Confirmed. The live match inventory is an in-memory item-id count. A player may hold 2 weapon ids. Other stacks stop at 200. `use` accepts `bandage` (heal 20) and `medkit` (heal 60), will not pass 100 health, and does nothing at full health. `discard` removes one from a stack and clears the equipped weapon when that weapon is discarded. Durable HTTP inventory is a separate store. This match inventory is not written as equipment slots.

Unknown. Original backpack capacity and equipment rules.

## ROS-R06 Map

Confirmed. The live match square is 200 by 200. Blockers are optional rectangles on the match. The published map catalog is a separate content system. The tick does not load terrain, doors, or collision from a published map package.

Unknown. Original terrain, buildings, roads, and spawn points. The client OBB packages were not extracted.

## ROS-R07 Loot

Confirmed. Each match places `loot_count` 36 nodes. The table repeats entries by weight: pistol 4, rifle 4, light ammo 30 quantity across 8, medium ammo 30 quantity across 8, bandage 2 across 8, medkit 1 across 4. Positions are random in the map with a margin of 10, seeded by the match id. Pickup succeeds only for an untaken node inside radius 2.5.

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

## ROS-R11 Progression

Confirmed. A finished human result carries kills, win, and placement into the pending result list. Experience, currency rewards, and rank from that result are not applied by this simulation.

Unknown. Original ranking and rewards.

## Not implemented

Confirmed by absence from the files read for this audit:

- Crouch, prone, and fall damage
- Armor and hit locations
- Weapon attachments
- Vehicle health
- Team revive and spectating
- Loading collision from a published map
- Original client packet formats

## Agent rule

Change a number in this page only in the same change as `app/game` and its tests. Keep the new number labeled as an independent design.
