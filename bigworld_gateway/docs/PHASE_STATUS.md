# Roadmap phase status (build 617289)

Living tracker for [SERVER_GAMEPLAY_ROADMAP.md](SERVER_GAMEPLAY_ROADMAP.md). Update after each harness iteration.

| Phase | Focus | Status | Blocker / next |
|-------|--------|--------|----------------|
| **A** Lobby | Account, shop, START UI prerequisites | **Mostly done** | `childBaseClientPropertyList`; occasional `on_enter` aborts; LDPlayer hall load ~70s |
| **B** Matchmaking → handoff | START → timer → map 700 | **Active** | Automated cycle taps START before `enterHall`; **BASEAPP RESEND** when session corrupt — restart server |
| **C** Core BR | Drop, zone, result → lobby | **In progress** | H1 `die_call` in code; **not verified** on device; needs stable Phase B |
| **D** Extended BR | Loot, guns, PvP | **Gated** | Pickup/equip partial in `battle_flow`; no map spawn table |
| **E** Meta | Portrait HTTP, voice | **Backlog** | Documented only |

## Phase B acceptance (current sprint)

1. `stop.cmd` + `start.cmd` (clean BaseApp).
2. `setup_emulator.ps1` + `sync_server_list.ps1`.
3. Launch game, tap PLAY, wait until server.log shows `Scheduled enterHall` or `enterHall`.
4. Tap START → log shows `matchBattleGround` → `_enter_battle` / `createBasePlayer`.
5. Cancel (timer X): `cancelMatchBattleGround` → `syncMatchState` NONE.

```powershell
cd c:\Users\Lufy\Desktop\Server\ros_server_v2
.\tools\cycles\phase_b_handoff.ps1
```

## Phase C acceptance (after B is green)

```powershell
.\tools\cycles\ld_debug_match.ps1 -RequireLobby -TapStart -WaitMatchSeconds 300 -ZoneTest
```

Log: `killed by the zone` → `match result`; result UI screenshot.

## Phase D first slice (when C passes)

- Env `LOOT_AUTO=on` or map 700 spawn table JSON
- `dtsBattlegroundPropAppearanceList` on avatar create
- Matrix rows: `pickup`, `equip_weapon`, `loot_crates`