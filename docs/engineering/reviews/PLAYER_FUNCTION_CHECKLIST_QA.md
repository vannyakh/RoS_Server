# Player function checklist — QA report (for CTO)

**TASK ID:** RO-128 (proposed — not in registry until CTO assigns)  
**AGENT:** qa-engineer (independent pass)  
**PHASE:** 09 — Player / Solo BR  
**STATUS:** `review` (code + unit evidence; **0/109 VERIFIED** on LDPlayer)

**OBJECTIVE:** Classify every owner checklist row for the **original APK + `bigworld_gateway/`** path. Secondary note: JSON `app/game` where unit tests exist (not counted as VERIFIED for mobile).

**TESTS EXECUTED:**
```text
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/player tests/compatibility/player -q --tb=line
→ 5 passed (2026-11-27)
```

**TEST RESULTS:** Gateway player entity unit tests pass. No LDPlayer run in this pass (RO-113 still **BLOCKED** — Network Error(15)).

**COMPATIBILITY EVIDENCE:** None for original-server behavior. Historical notes in `bigworld_gateway/docs/LOBBY_FINDINGS.md` only.

**RECOMMENDATION (CTO):**
1. Register **RO-128** — *Player function checklist QA & LDPlayer re-verification* — assign `qa-engineer`, `files_allowed`: `docs/engineering/reviews/PLAYER_FUNCTION_CHECKLIST_QA.md`, `docs/PLAYER_*.md`, `docs/testing/player_function/**`.
2. Keep **RO-113** blocked until emulator DNS/proxy matches `config.cmd` `ROS_PC_IP`; then re-run sections 2–8 on device.
3. Do not mark any row `VERIFIED` without log/screenshot per `RESTORATION_STATUS.md`.

**KNOWN ISSUES:**
- LDPlayer never reached match in last RO-113 run → spawn through inventory rows are code-audit only.
- Gateway lacks authoritative firearm PvP loop (combat MISSING).
- Position ClientInterface msg 3 layout unknown (RO-057).

---

## Summary

| Section | Rows | VERIFIED | IMPLEMENTED (code/unit) | PARTIAL | MISSING | NOT_CHECKED | BLOCKED |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Account & character | 9 | 0 | 3 | 5 | 0 | 0 | 1 |
| Player spawn | 7 | 0 | 3 | 3 | 0 | 0 | 1 |
| Movement & controls | 13 | 0 | 0 | 4 | 4 | 5 | 0 |
| Aircraft & parachute | 8 | 0 | 6 | 1 | 0 | 0 | 1 |
| Weapon system | 12 | 0 | 0 | 5 | 5 | 2 | 0 |
| Health & survival | 10 | 0 | 2 | 4 | 2 | 0 | 2 |
| Inventory & loot | 11 | 0 | 1 | 6 | 2 | 2 | 0 |
| World interaction | 8 | 0 | 0 | 2 | 2 | 4 | 0 |
| Animation & audio | 11 | 0 | 0 | 0 | 0 | 11 | 0 |
| Results & persistence | 11 | 0 | 2 | 7 | 1 | 0 | 1 |
| Network & performance | 9 | 0 | 2 | 4 | 0 | 1 | 2 |
| **Total** | **109** | **0** | **19** | **41** | **16** | **25** | **8** |

*BLOCKED = cannot execute on device until RO-113 network path passes.*

---

## 1. Account & character (0/9 verified)

- [ ] **Load persistent player ID** — IMPLEMENTED (`GatewayService.resolve`, SQL `players.id`) — *not re-tested LDPlayer*
- [ ] **Create default character** — IMPLEMENTED (`set_character`, starter cosmetics)
- [ ] **Select male or female character** — PARTIAL (20001/20002; female not re-tested)
- [ ] **Change nickname** — PARTIAL (API + hall; no fresh mobile)
- [ ] **Load avatar** — PARTIAL (portrait fields; FilePicker incomplete)
- [ ] **Load player level and EXP** — PARTIAL (read path; match EXP not from battle end)
- [ ] **Synchronize currency** — PARTIAL (JSON vs gateway ledger codes)
- [ ] **Load equipped cosmetics** — PARTIAL (`equipAppearance`; gaps historically)
- [ ] **Save profile after reconnect** — BLOCKED (depends on stable session; LDPlayer drops)

## 2. Player spawn (0/7 verified)

- [ ] **Spawn in preparation area** — IMPLEMENTED (RO-061 space countdown; unit)
- [ ] **Initialize correct character model** — PARTIAL (BattleGroundAvatar create; device open)
- [ ] **Initialize health** — IMPLEMENTED (`PlayerRuntimeState`, zone play hp props)
- [ ] **Synchronize position and rotation** — PARTIAL (forcedPosition land; msg 3 unknown)
- [ ] **Display player name** — IMPLEMENTED (nickname on avatar create)
- [ ] **Synchronize equipped skins** — PARTIAL (appearance lists; historical aborts)
- [ ] **Reset previous battle inventory** — IMPLEMENTED (`reset_battle_loadout()` on session)

## 3. Movement & controls (0/13 verified)

- [ ] **Joystick movement** — PARTIAL (client-led; limited server echo)
- [ ] **Walk** — PARTIAL (client physics dominant)
- [ ] **Sprint** — MISSING (gateway); JSON single speed only
- [ ] **Jump** — PARTIAL (ground jump server not answered; aircraft jump separate)
- [ ] **Crouch** — PARTIAL (`changePose` echo in legacy Match)
- [ ] **Prone** — PARTIAL (same)
- [ ] **Swim** — MISSING
- [ ] **Vault supported obstacles** — MISSING (RO-082/083)
- [ ] **Camera rotation** — NOT_CHECKED (client-local)
- [ ] **Free look** — NOT_CHECKED (client-local)
- [ ] **Movement animation** — NOT_CHECKED (client)
- [ ] **Collision validation** — MISSING (verifyClient* log only)
- [ ] **Prevent invalid movement** — MISSING

## 4. Aircraft & parachute (0/8 verified)

- [ ] **Enter aircraft state** — IMPLEMENTED (RO-062 plane; unit)
- [ ] **Display jump button** — PARTIAL (inJumpArea; live open)
- [ ] **Jump from aircraft** — IMPLEMENTED (RO-063 requests; unit)
- [ ] **Free fall** — IMPLEMENTED (fall phase props; unit)
- [ ] **Deploy parachute** — IMPLEMENTED (`chooseParachute`/glider; unit)
- [ ] **Control descent** — PARTIAL (client glide; server limited)
- [ ] **Land on terrain** — IMPLEMENTED (forcedPosition + props; unit)
- [ ] **Transition to ground movement** — BLOCKED (RO-113; no live chain)

## 5. Weapon system (0/12 verified)

- [ ] **Pickup weapon** — PARTIAL (`PropsModule`, legacy Match)
- [ ] **Equip primary weapon** — PARTIAL (gun slot 1)
- [ ] **Equip secondary weapon** — PARTIAL (slot 2)
- [ ] **Switch weapons** — PARTIAL (`dtsCurWeapon` updates; no full module)
- [ ] **Aim down sights** — NOT_CHECKED
- [ ] **Hip-fire** — MISSING (no gateway hit fire)
- [ ] **Fire mode switching** — MISSING
- [ ] **Reload** — MISSING (gateway)
- [ ] **Consume ammunition** — MISSING (gateway)
- [ ] **Attach weapon accessories** — MISSING
- [ ] **Drop weapon** — PARTIAL (RO-079 backlog)
- [ ] **Synchronize firing animation** — NOT_CHECKED (client)

## 6. Health & survival (0/10 verified)

- [ ] **Initialize health** — IMPLEMENTED (zone + `PlayerRuntimeState`)
- [ ] **Receive damage** — MISSING (firearms); PARTIAL (zone poison)
- [ ] **Apply armor protection** — MISSING (gateway)
- [ ] **Apply helmet protection** — MISSING (gateway)
- [ ] **Use healing items** — MISSING (gateway); IMPLEMENTED JSON `app/game`
- [ ] **Cancel healing when required** — MISSING (gateway)
- [ ] **Apply fall damage** — MISSING
- [ ] **Apply zone damage** — IMPLEMENTED (RO-064 zone module; unit)
- [ ] **Apply vehicle damage** — MISSING
- [ ] **Eliminate player correctly** — PARTIAL (`set_eliminated`, zone fatal → results)

## 7. Inventory & loot (0/11 verified)

- [ ] **Open backpack** — NOT_CHECKED (UI client)
- [ ] **Pickup ammunition** — PARTIAL (prop pickup path; limited types)
- [ ] **Pickup equipment** — PARTIAL
- [ ] **Equip backpack** — MISSING
- [ ] **Equip helmet** — MISSING (gateway)
- [ ] **Equip armor** — MISSING (gateway)
- [ ] **Stack consumables** — PARTIAL (`battle_inventory` stacks on non-gun)
- [ ] **Validate backpack capacity** — MISSING
- [ ] **Drop items** — PARTIAL (RO-079)
- [ ] **Loot eliminated bots** — MISSING
- [ ] **Open supply drops** — MISSING

## 8. World interaction (0/8 verified)

- [ ] **Open doors** — PARTIAL (`openElement`)
- [ ] **Close doors** — PARTIAL (`closeElement`)
- [ ] **Enter vehicle** — MISSING (RO-091)
- [ ] **Exit vehicle** — MISSING
- [ ] **Drive vehicle** — MISSING
- [ ] **Interact with supported objects** — PARTIAL (limited props/doors)
- [ ] **Update minimap** — NOT_CHECKED (client)
- [ ] **Place map marker** — NOT_CHECKED

## 9. Player animation & audio (0/11 verified)

All **NOT_CHECKED** — client rendering/audio; server may only reply on actions (RO-083 future).

- [ ] Idle / walk-run / jump-land / crouch-prone / weapon hold / shoot / reload / heal / death animation
- [ ] Footstep audio / weapon audio

## 10. Results & persistence (0/11 verified)

- [ ] **Update kill count** — PARTIAL (counters in results module; no combat kills)
- [ ] **Update alive participant count** — IMPLEMENTED (`aliveNum` bots+human; unit)
- [ ] **Record damage dealt** — PARTIAL (counter fields; not wired from combat)
- [ ] **Record survival time** — PARTIAL (timers in results)
- [ ] **Calculate placement** — PARTIAL (solo logic local)
- [ ] **Display elimination screen** — PARTIAL (wire exists; live open)
- [ ] **Display victory screen** — PARTIAL
- [ ] **Grant rewards exactly once** — PARTIAL (gateway report API; idempotence not proven)
- [ ] **Save match statistics** — PARTIAL (`record_match`)
- [ ] **Return to lobby** — PARTIAL (RO-127 testing; quit historical)
- [ ] **Start another clean match** — BLOCKED (RO-113)

## 11. Network & performance (0/9 verified)

- [ ] **Synchronize player to bots and clients** — PARTIAL (createEntity bots; no movement sync)
- [ ] **Handle delayed packets** — PARTIAL (Mercury stack; not characterized)
- [ ] **Handle duplicate requests** — PARTIAL (pickup idempotence gaps)
- [ ] **Handle disconnect** — PARTIAL
- [ ] **Recover session where supported** — BLOCKED (LDPlayer session stability)
- [ ] **Prevent stuck player states** — PARTIAL (lifecycle module new)
- [ ] **Maintain stable movement** — NOT_CHECKED (needs device)
- [ ] **Measure frame rate** — NOT_CHECKED (client)
- [ ] **Release player entities after match** — IMPLEMENTED (session.close, leave_aoi bots; unit)

---

## JSON simulator cross-reference (informational only)

For `app/game` + WebSocket, many combat/movement/inventory rows reach **IMPLEMENTED** in `GAMEPLAY_FUNCTION_AUDIT.md`. That does **not** upgrade APK checklist rows to VERIFIED.

---

## CTO next actions

| Action | Owner |
| --- | --- |
| Add **RO-128** to `tasks.json`, assign `qa-engineer`, status `assigned` | **cto** |
| Unblock **RO-113** (emulator DNS/proxy) | **devops-engineer** + owner |
| After RO-113 pass, re-run this checklist sections 2–8 with screenshots | **qa-engineer** |
| Share human+bot `PlayerRuntimeState` for combat (RO-085+) | **gameplay-test-engineer** |