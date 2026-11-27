---
name: ros-lobby-method-encoding
description: RoS lobby entry solved server-side (base-only Athlete + 0x80 method ids); only emulator load-time/inactivity blocks it (2026-11-17)
metadata:
  node_type: memory
  type: project
  originSessionId: db1c3af5-d840-4375-80eb-c999d999ee05
  modified: 2026-11-18T02:01:55.927Z
---

Server->client entity METHOD calls use msg id 0x80|idx (var16 length); 0xC0|idx is the PROPERTY-update range. Idx 61 = extended (efficient = 62-(n+192)//255, then sub-byte). Env: METHOD_BASE=0x80 METHOD_EXT=byte in ros_server.py.

Working lobby route (iteration 15): SWITCH_TO=athlete ATHLETE_CELL=off TRANSITION_RESET=off LEAVE_OLD_AVATAR=off (base-only Athlete, no Avatar/tutorial). enterHall runs, scene\hall\hall.scn (level 20) loads. The prerequisites gate (Application.scene + Globals.player) only applies to cell/world entities, not the base-only lobby player.

Remaining emulator-only issue: hall.scn load blocks the client 68-83s; native InactivityTimeout is 10s until GameInit.updateInactivityTimeout (HALL 30s) -> REASON_INACTIVITY drop + relogin loop. Server keepalives don't help. Try the physical arm64 phone (fast load) or get user approval for a client-side setInactivityTimeout bump on the emulator.

Update 2026-11-18: lobby UI reached on LDPlayer after ~6 load/drop cycles (hall.scn 70s -> 40s, then scene\hall2\hall.scn loads in <1s). Character: saved_accounts.json char_type 30001=bot_base ROBOT, 10001=no model (empty), 20001=human male (works). START button tap produced no server message yet (match start not implemented).

**Why:** Hours were wasted on the scene/Globals.player gate and tutorial-map routes; a base-only Athlete avoids all of it.
**How to apply:** Do NOT attach frida/trace_entity_msgs.js for base-only runs: it crashes the client (SIGSEGV ~3s after createBasePlayer). Use frida/trace_method_decode.js or nothing. Related: [[antigravity-agent-conflict]]

Lobby UI bug (2026-11-18): first lobby button press (e.g. char tap -> Supply) then back throws AttributeError in UIMain.setModelVisible because UIMain.models[gid]['loader'] is None (self hero has empty dts*AppearanceList props). After that every enter_ui throws (UISupplyController.on_leave) so ALL lobby buttons are dead until relogin. Appearance data tables on client are not loaded (dts_appearance_utils.getBodyAppearanceData() raises in preprocessBodyAppearanceData), so valid appearance ids can't be listed from the client; pushing onSetDtsAppearanceGender/onUpdateDtsShow*List (ros_server._push_appearance, trigger via harness/push_now.flag) did not create the model/loader. Hero model only appears after leaving a sub-UI (displayAll).

Breakthrough 2026-11-18: UIMain.on_enter was aborting on AttributeError 'PlayerAthlete' has no attribute 'iLuckyCarnivalIsSuper' (set only by client method Athlete.onUpdateLuckyCarnivalData, a PYTHON pickle dict, op 10000). Fixed by ros_server._lobby_data_calls() sent before enterHall -> full lobby UI + hero + top menu appear. Remaining: UIMain.on_enter next aborts at UIMain.py:1651 -> showRedPoint (line 2708) 'NoneType' not iterable; left-menu buttons (Store/Supply/Depot/Top-up) and Lucky Club do nothing (probably unbound because on_enter aborted), but top-bar profile + Outfit page open. Outfit page empty: dts_appearance_utils data tables fail (KeyError 8 / legacyProperties). Pattern: look for first SCRIPT traceback after hall2 load, supply the missing Athlete attribute via the client method that sets it.

## Update 2026-11-19: portrait, FilePicker upload, draw tutorial

Found with read-only Frida payloads (`client/frida/payloads/portrait_*.py`, run via `neox_py_eval.js --realm emulated`).

**Portrait (hall avatar).** `UIMain._init_profile` calls `client_utils.getAvatarProtrait(widget, roleID=baseCharacterType, fileID=portrait)`:
- `portrait` empty or `'0'`: built-in image `ui/images/avatar/portrait/<baseCharacterType>_on.png`.
- otherwise `portrait` is a FilePicker file id: downloaded from `http://g89ros.fp.ps.easebar.com:80/file/<id>?fop=imageView/0/w/800/h/600/f/jpeg/q/50` and cached as `ui/images/tantan/<id>.png`.
- `portrait` lives in Athlete `childBaseClientPropertyList` (FIXED_DICT field `portrait`, STRING). Full list not sent at login (package2 stream bug); gateway uses `onSetPortrait("0")` in `_lobby_data_calls` + `_sync_lobby_portrait` after enterHall (`PORTRAIT_SYNC` / `PORTRAIT_DELAY`) so `getAvatarProtrait` uses built-in `ui/images/avatar/portrait/<baseCharacterType>_on.png`.
- char 30001 (robot placeholder) showed a grey avatar; switched the test account to 20001 (Human male), which renders in the Supply screen. The hall avatar with 20001 is not yet confirmed.

**Upload flow (not implemented yet).**
1. Athlete base `requestFilePickerToken()` -> client `onRequestFilePickerToken(STRING token, INT32)`.
2. `POST http://fp.ps.easebar.com:80/g89ros/file/new/` with `Authorization: <token>`; reply JSON `{"url": ".../<fileID>"}`.
3. `meetconfigs.MEET_URL` (currently `http://<PC IP>:443`, plain HTTP) + `/TanTanService/setPortrait?...`; reply JSON `{"Ret": 0, "Data": {"PORTRAIT": "<fileID>"}}`.
4. Client calls Athlete base `setPortrait(STRING fileID)`; server answers `onSetPortrait(STRING)` and stores it.

**Exposed base-method ids (solved).** The client's own table (EntityDescription(Athlete)+0x160 = 1748 base method descriptors, +0x178 = 1191 exposed indices; `client/frida/dump_base_methods.js`) is saved as `server/extract/athlete_base_exposed.json`. It equals the `.def` order plus 24 methods our def parse does not mark exposed. Ids: index < 57 -> msg `0xC0 + index`; otherwise `k = index - 57`, msg `0xF9 + (k >> 8)`, sub byte `k & 0xff`. Every logged request fits its argument types under this rule. `server/athlete_requests.py` decodes by name; the gateway logs each request as `<- Athlete.<name>`.

**Draw tutorial.** After enterHall the first-time "Supreme Supply" tutorial shows "Draw for free" / "Skip". Both send base requests (e.g. `F9 F5`) that the gateway does not answer, so the screen waits forever.

**Supply draws (working).** The Supply screen sends `queryAvailableSupplement` (`F9 F5`); the gateway answers `onQueryAvailableSupplement(extract/supplement_info.json)` and `onUpdateFreeLotteryTimeStampDict`. Box info shape: single-currency boxes (`Constant*` currency option) use scalar `CURRENCY_ID` / `BUY_TIMES_PRICE` / `BUY_MULTIPLE_TIMES_PRICE`; two-currency boxes use 2-element lists (a list for a single-currency box crashed `currency_utils.getCurrencyIcon` and left the buy buttons unbound). Result screens also read `NEXT_BUY_TIMES_PRICE`. `openSupplyBox` / `openSupplyBoxFree` / `openMultipleSupplyBox` roll prizes uniformly from `extract/supplement_props.json` (client `getAllPossiblePropID`), add won appearance items for the session, and do not charge currency.

**Still open.** Supreme Supply (monthly box) is blank: `UIMonthlySupplyPackage.Awake` gets `getCurrentMonthSupplementID() -> None` because the client's monthly boxes are dated years before the device clock. Avatar upload: the gateway answers `requestFilePickerToken` and `setPortrait` (stored in RoS_Server `gateway_identities.portrait`, sent back at login in `childBaseClientPropertyList`), but the FilePicker upload and TanTanService HTTP endpoints are not served yet.

## Update 2026-11-19 (2): buy, wear, diamonds, START

- **Draw arguments.** `openSupplyBox(sid, currencyID, coupons, isWatchAd)` and `openMultipleSupplyBox(sid, currencyID, coupons)`: the 2nd INT32 is the chosen currency, not a count. Single draw = 1 prize, multi = 10. Diamond (currency 2) draws are charged from the box price (`athlete_requests.draw_price`).
- **Diamonds.** Shown value = `freeYuanbao + payYuanbao`. Updated by client method `iCurrency.onYBUpdated(INT64 free, INT64 pay, INT32 src)`; `onCurrencyUpdated(2, ...)` and 0xC0 property updates do not change it. Draw-result screens also need `vipInfo` (`syncVipInfo({"level","exp","rewardStatus"})` at login).
- **Wardrobe buy.** Depot BUY -> `buyDtsHallProp(propID, coupons, logStr)`. Prices: `extract/hallprop_prices.json` (client `mall_utils`, 1064 props, all diamonds). Reply: `onYBUpdated` + `onAddDtsAppearanceItem` + `onBuyMallGood([id])`; the item shows under Owned.
- **Wear.** Tapping an owned item -> `equipAppearance(id)`. Reply: `onUpdateDtsWearableAppearanceList` + `onUpdateDtsShowWearableAppearanceList` (or `onUpdateDtsShowBodyAppearanceList` for body parts) + `onNotifyEquipedAppearance(id)`. Kind from `extract/hall_props.json` by_type. Session only (not stored).
- **START.** Sends `getOpenMaintenanceFightTipFlag` (answered `onGetOpenMaintenanceFightTipFlag(False, 0)`), then `createHallTeam(INT32 mode)` and `getReadyForBattleGround()`. Next replies needed: `onEnterHallTeam(...)`, `syncReadyState`, `syncMatchState`, then a battle space (not implemented).
- **Supreme Supply** first opens on the monthly page, blank because `getCurrentMonthSupplementID()` compares the device clock (2026) with monthly box dates; the other Supreme boxes show after re-entering the screen.


## Update 2026-11-19 (3): START -> team -> matching timer (working on LDPlayer)

Read with `client/frida/payloads/hallteam_dis.py` / `hallteam_dis2.py` / `hallteam_state.py` (client `entities\iHallTeam.py`).

- **Flow.** START: `getOpenMaintenanceFightTipFlag` -> `createHallTeam(INT32 mode)` (Ranked = 4) -> `getReadyForBattleGround()` (sent only after the client's own map/resource checks) -> `reqPayedPartnerRel`, `changeOccupation(0)`, `matchBattleGround(1)`. Timer X sends `cancelMatchBattleGround()`.
- **Replies (gateway).** `createHallTeam` -> `onEnterHallTeam(teamType, leaderGID, teamSize INT8, ARRAY<HALL_TEAM_MEMBER_CLIENT>, teamMapGroup, matchingRandom, matchingRandomSize)`; solo team, map group 1 (`DtsMapBaseType.MAP_4K`, map 700). `getReadyForBattleGround` -> `syncReadyState(gid, True, occupation)` + `syncMatchState(1, now, False, None)` + `syncMatchingProgress(1, 100, 0.0)`. Cancel / not ready -> `syncReadyState(gid, False, 0)` + `syncMatchState(0, 0, False, None)`.
- **Enums.** `const.BattleMatchState`: NONE 0, MATCHING 1, ENTERING 2, PRE_ENTERING 3. `syncMatchState` opens `UIBattleGroundsMatchTimer` for any state other than NONE.
- **Team member.** `HALL_TEAM_MEMBER_CLIENT` (49 fields, no Parent) = .def defaults plus entID, gid, nickname, level, characterType, inWorld, outfit lists, and `hallThemeID = 270000`. A 0 theme crashes `onEnterHallTeam` (line 121, `getHallThemeScore(0)` -> None.PROP_TYPE).
- **Note.** `bwdefs.resolve` ignores `<Parent>` in FIXED_DICT aliases (e.g. HALL_TEAM_MEMBER, the server-side type). Not needed for client methods so far.
- **Next.** Battle entry: answer `matchBattleGround` with ENTERING, then a battle space / cell player (prerequisites gate: Application.scene + Globals.player).

**Test tooling.** frida-server must not be running when the game starts: the DCTOOL device check crashes the game ~2 s after the notice fetch (breakpad, no tombstone). `tools/cycles/lobby_cycle.sh` now starts it after the menu. The Frida Python module is in `..\.venv` (`PY=../.venv/Scripts/python.exe` for `tools/probe.sh`). After an emulator reboot run `client/scripts/setup_emulator.ps1` again (DNS DNAT + CA are lost).

## Update 2026-11-19 (4): into a match on map 700 (working on LDPlayer)

- **Handoff.** `matchBattleGround(1)` -> `syncMatchState(2 ENTERING, now, False, None)`, then after `BATTLE_DELAY` (3 s) `resetEntities(False)` + `createBasePlayer(BattleGroundAvatar, type 120)` + `createCellPlayer(space 1, pos 0,0,0)`. The same as `BaseEntity.giveClientTo`. `PlayerAvatar.onBecomePlayer` loads `currentMapID` itself (`MapLoader`), so no scene message is needed. Code: `GateUDP._enter_battle`, `avatar_create_messages(map, char, name, entity)`.
- **Entity type.** Plain `Avatar` (43) breaks: `PlayerCommonAppear.onInit` needs `dtsBattlegroundPropAppearanceList`, which only `BattleGroundAvatar` has (Parent Avatar + iDtsEquip, iDtsProp, iDtsPackage, iDtsEquipAppearanceAvatar, iVoxelBuild; 107 base + 388 cell props). Env: `BATTLE_ENTITY`, `BATTLE_MAP` (700), `BATTLE_CHAR` (0 = account char), `BATTLE_ENTER=off` to stop at ENTERING.
- **Result.** Map 700 loads in about 15 s on LDPlayer with char 20001. HUD, minimap, compass, fist weapon. The joystick moves the character (client-side). Stayed connected 2+ minutes with no relogin. The client sends position updates as msgs 0xBC / 0xBD (not handled yet). Remaining script errors: `PlayerFPSound` has no `hurtLight` / `_flyClip` (cosmetic).
- **Not done yet.** No loot or other entities (DtsProp etc. would arrive via entity create / enterAoI), no plane and parachute start (spawn is at 0,0,0 on the ground), no zone, no bots, no death or results screen, no return to the lobby. "120 LEFT" is the client default.

## Update 2026-11-19 (5): lobby data vs. the 2026 clock

The client's date-gated data ends in 2022 (season 21: 2022.03.16-05.24; the last monthly Supreme box runs until 2022.12.30). On a 2026 clock: season pass "LEFT -1640 days", blank Supreme page, broken first Supply screen. Read with `server_time_probe.py`, `season_dates_probe.py`, `month_dates_probe.py`, `season21_probe.py`, `supply_guide_probe.py`, `push_probe.py`, `signcheck_probe.py`, `signin_awards_probe.py`.

- **Game clock.** `athlete_requests.game_now()`: `GAME_DATE` (UTC, default `2022-04-20 12:00:00`, `real` = PC clock), advancing from server start. Used for every timestamp sent to the client (match state, lucky carnival, free-lottery stamps).
- **Server time.** `syncServerTime(INT64 tenths of a second)` + `syncServerTimeZone(0,0,0)` first in `_lobby_data_calls`. `client_utils.getServerSysTime()` = origin + elapsed BigWorld time; without it the client uses the device clock. Verified: client reads 1650456143 (2022-04-20).
- **Device-clock code.** `supplement_utils.getCurrentMonthSupplementID` uses `time.time()`, not server time, so the monthly Supreme page (`UIMonthlySupplyPackage`, `Awake` crashes on None) can't be fixed from the server. `onSetSwitches(name, 0)` (= `setattr(shared.switches, ...)`) turns `SysEnableMonthSupply` off (`LOBBY_SWITCHES_OFF`). The page no longer opens or crashes, but the Supreme tab does nothing. Only a device date before 2022-12-30 would show it.
- **First Supply screen.** It was the weekly push (`UIMgr.gotoThisWeekSupplyPackage`) landing on the crashing monthly page. `setHasAlreadyShowSupplyID(id)` is stored (`saved_accounts.json` key `supply_push`) and sent back at login with `onUpdateAlreadyShowSupplyID`.
- **Daily sign-in (UIDtsSign).** Always due: `checkDtsSigninNotSameDay` compares `childBaseClientProperty.signAwardTime` with server time. It takes a while to load (dim screen first). "Claim" sends `requestDtsSigninAward`; the gateway answers `onRequestDtsSignInAward([award], level)` with awards by day `[200027, 203011, 200012, 203012, 291210]` (iterDtsSigninData; max const 7). Level and day are stored (`signin`). Works: "Congrats! 388 Gold".
- **enterHall(BOOL)** is `firstLoginToday` (`UIMgr.enterHallUI`). `HALL_POPUPS=off|daily|on` (default off). Note the sign-in popup still appears with `False`.
- **Bug: childBaseClientPropertyList.** A full element (76 fields) misaligns the client by +2 bytes within its first ~70 bytes (`SequenceDataType::createFromStream: Invalid size ... 0x80060000` at element offset 72, then EOFError on later PYTHON props, so login fails). Raw XML and parse agree (76 fields); `package2` is `DTS_APPEARANCE_REPERTORY_PACKAGE3`. Cause unknown. The gateway therefore sends the element only with a portrait, which is likely broken the same way. This blocks sending `signAwardTime` (no popup after claiming), the huiliu fields and the lucky times there.
- **Still open.** The Season Bounty tile opens the Activity panel (`UILimitWelfareController.on_enter`: `PlayerAthlete` has no `personalRecommendCanBuy`). More 2022 activities appear now (Recruit/Cosmic Supply popup, Activity tabs) and need their data methods. The season-pass "LEFT" days were not re-checked yet.
- **LDPlayer date = 2022-04-20 (2026-11-19).** The test CA and server cert were re-issued from the same keys, valid 2020-01-01 to 2036 (old ones in `server/certs_backup_2026/`). The Android trust-store file keeps the OLD subject hash name `834a6af3.0` (`openssl x509 -subject_hash_old`). Emulator: `settings put global auto_time 0`, `date -u 042012002022.00`. `config.cmd` keeps `SysEnableMonthSupply` on for this emulator. Login works, the monthly Supreme page opens with no script error, and draws work.
- **Slow lobby load.** `scene\hall\hall.scn` blocks the game thread about 35 s on LDPlayer, close to the 40 s inactivity timeout. Frida probes during that load push it over (52-62 s), causing a relog loop. Don't probe until the lobby is up.
- **Open.** The emote panel: `UIBattlegroundsInGameActionAndEmoji.fillActionItems` reports that `PlayerAthlete` has no `dtsInGameActionAppearanceIDs`.
- **Hall theme (2026-11-19).** `dtsHallThemeID` 0 has no theme data. Leaving the outfit/Depot screen restores the theme (`HallTheme.onShowOriTheme` -> `onThemeChange` -> `onUIChange`), fails with `'NoneType' object has no attribute 'DEFAULT_LIGHT'`, aborts `leave_ui` and leaves every UI hidden (a stuck screen with only the model). The gateway sends `onUpdateDtsHallThemeID(270000)` (`const.DEFAULT_HALL_THEME_ID`; RoS2 uses 279016; env `HALL_THEME_ID`) at login. Store -> Lobby Theme now shows The Countryside as "In Use".
- **Store multi-buy.** Lobby Theme "Selected n/4" -> BUY sends `buyMultipleMallGood(goods[], nums[], coupons[], logStr)`. The gateway prices each good (`mall_good_price` / `mall_good_prop`, `extract/mall_goods.json`), charges the total once and replies `onBuyMallGood(props)`. Verified: School Campus good 10002 -> prop 270002, 280 diamonds, "Congrats! Schoolgirl x1". Not yet verified: "Go" / applying the theme. Another agent's `harness/login_cycle.sh` restarted the game mid-test.
- **Lobby Theme BUY "Not enough Diamonds" (2026-11-26).** With RoS_Server linked, the multi-buy sent ledger reason `mall-multi:[10002]`; the API only takes `^[a-z0-9_.:-]+$`, answered 422, and the gateway replied `onBuyMallGoodFailed`, which the client always shows as "Not enough Diamonds!" with Need = price - balance (negative). Reasons now go through `account_link.ledger_reason` (multi-buy sends `mall-multi:10002-10003`). Using a theme is `equipAppearance(themeProp)`; the theme is now saved with the outfit on RoS_Server (`PUT .../outfit` `theme`) and the login burst sends the saved `onUpdateDtsHallThemeID` instead of always 270000.

## Update 2026-11-19 (6): gender switch, store goods, wardrobe preview, saved inventory

- **Gender switch.** ♂/♀ sends `setDtsAppearanceGender(INT32)`. `onSetDtsAppearanceGender` alone only flips the UI: the hall model comes from `baseCharacterType` (`UIMain.resetMainModel` -> `player.getCharacterType()`), and each type has a fixed GENDER (`legacyProperties.getCharactersData`: 20001 M, 20002 F, 10001/10002 M, 30001 F). The gateway also sends `updateBaseCharacter(20001/20002)` and stores the type; `dtsAppearanceGender` at login follows the character type.
- **Store.** The client only enables BUY for goods in `availableMallGoodsDict`, filled by `onQueryAvailableMallGoodsByType(UINT32 types, PYTHON)` / `onQueryAvailableMallGoods` / `onQueryAvailableMallGoodsForAppearanceMall`. Values are `mall_utils.createMallGoodsInfo` dicts `{NAME, CURRENCY_ID, PRICE, DISCOUNT, BUY_TIMES}`, dumped from the client into `server/extract/mall_goods.json` (1160 goods, per-location id lists via `GoodsLocationTypeToPropertieDataField`, good -> hall prop). Entity messages are var16: the full catalogue only fits without NAME. `buyMallGood` charges `PRICE * DISCOUNT // 100` (matches the price the client shows).
- **Wardrobe preview.** `tryOnAppearance` / `tryOffAppearance` / `cancelTryOnAllRequest` follow the shared `DtsAppearance.<type>.swap`: an item replaces whatever is in the same slot of its list and only the *show* list (`onUpdateDtsShow*AppearanceList`) changes. Slot rules: clothes = `getBattleGroundPropData(hall.PROP_TYPE.PROP_ITEM_ID).PROP_TYPE.SLOT` (cloth0/1/3/4); face/hair/decorations = hall prop CATEGORY (one body list); weapon skins = `getDtsWeaponAppearanceGunID`; vehicle skins = `getVehicleAppearanceVehicleID`; lobby theme = `dtsHallThemeID` (`onUpdateDtsHallThemeID`). Table: `server/extract/appearance_slots.json`. `equipAppearance` updates the equipped and shown lists for all of these.
- **SET (clothes suits).** `putOnAppearanceClothSuit(sid)` / `takeOffAppearanceClothSuit(sid)`; contents from `legacyProperties.getAppearanceSuitData(sid).PROP_TYPE` (`SUIT_ELEMENT_APPEARANCE_ID`, GENDER), 14 suits. Owned pieces are equipped, the rest previewed.
- **Saved inventory.** Without a RoS_Server link, owned items, outfit (all lists + theme) and diamonds are kept in `saved_accounts.json` (`inventory:<gid>`) and sent at login like the linked state.
- **Probes.** `tools/probe.sh` needs a Windows path (`C:/...`) for the payload, or adb pushes nothing and the previous payload runs. Several sessions probing one emulator overwrite each other's `py_payload.py`.

## Update 2026-11-19 (7): items, diamonds and outfit saved in RoS_Server

- RoS_Server keeps the original-client state per gateway identity: `gateway_items` (prop_id, number), `gateway_identities.outfit` ({body, wear}) and the diamond balance as currency `yuanbao` in the normal ledger (`currency_transactions`, reasons `gateway:start`, `gateway:draw:<box>`, `gateway:buy:<prop>`). New players start with `GATEWAY_STARTING_YUANBAO` (default 100000).
- API (X-Gateway-Key): `GET /api/v1/gateway/accounts/{uid}/state`, `POST .../purchase` {price, props, reason} (charge + add items in one transaction, 409 if too few diamonds), `PUT .../outfit` {body, wear}.
- Gateway: login loads the state once (`ros_server.LOGIN_STATE`) and puts it in the Athlete props (`freeYuanbao`, `dtsAppearancePackage` with `info={"ex_tm": 0}`, `dtsWearableAppearanceList` / `dtsShowWearableAppearanceList`, `dtsShowBodyAppearanceList`). Every draw/buy goes through `GateUDP._settle` -> `account_link.purchase`; equips call `account_link.set_outfit`. Without the link (no `GATEWAY_API_KEY` or API down) it falls back to session-only.
- Verified on LDPlayer: after draws (diamonds 99510, 45 items) and wearing War Boy - Yellow, a fresh login shows 99510 diamonds and the mask still worn.


## Update 2026-11-19 (8): battle flow groundwork (zone, plane, countdown) - in progress

Goal: countdown -> plane -> jump -> shrinking safe zone in a match on map 700. Nothing of this is visible in-game yet.

- **Where the data lives (client defs).** The safe zone is not on the player: `Globals.spaceEntity` is a `BattleGroundSpace` entity (client type 14) with `circleStage`, `whiteCircleCenter/Radius`, `blueCircleCenter/Radius`, `blueCircleStart*`, `mapID`, `gameStartTime`, `getOnPlaneTime`, `planeEntityIDs`, `aliveNum`. The plane is a `Plane` entity (client type 147: `movePath`, `moveSpeed`, `inJumpArea`, `mode`); the player's `planeID` points at it. Player props: `battleState`, `planeID`, `flightStage`, `leftPlayerNumOnPlane`, `isInPoisonArea`. Client methods: `onRequestCircleRestTime(INT32)`, `BattleGroundSpace.updateCircleRestTime/showCircleNotify/showCircleMessage/gameEnd`. Exposed server methods for the jump: `requestGetOffPlane`, `chooseParachute`, `chooseGlider`.
- **ClientInterface ids.** `extract/message_map.txt` seq minus 21 (see `RosGG/extract/message_map.txt`): `createEntity` 9 (var16), `enterAoI` 11 (id u32 + alias u8), `leaveAoI` 15 (var16), `detailedPosition`/`forcedPosition` 0x58/0x59.
- **createEntity works as a message.** `enterAoI` + `createEntity(id u32, type u16, pos 3f, dir 3 x int8, property data)` creates the entity on the client (`BigWorld.entities[20001]` is a `BattleGroundSpace`). It then fails in `enterWorld` (`maps_utils` data is None) because the property values did not arrive.
- **Property data framing: not solved.** With tagged data (count + index/value) or untagged all-properties data the client either consumes only 4 bytes or reports `CompressionIStream: Invalid compression type: <byte 2 of the data>`. So the data is: 1 unknown byte, then a compression-type byte, then the stream. The compression type values and what follows (pickled dict vs ordered stream) are unknown. Next step: find the createEntity handler in `libclient.so` (it is stripped; `disas_fn.py` finds no xref for the compression error string, so search by the other error strings, or probe with a Frida hook on a Python-side entity constructor).
- **A bad createEntity breaks the channel.** After a malformed message the client stops acking (gateway logs `BASEAPP RESEND` forever) and the match must be restarted. Leftover `trigger_battle.txt` files fire into the next match.
- **Tooling added.** `server/battle_flow.py` (message builders and `debug_command`), `server/trigger_battle.txt` (one command per line, consumed on the next client packet while in a match, module reloaded each time: `space`, `space0`, `ce`, `leave`, `raw`), `tools/to_match.sh` (restart game and drive it into a match; adb is at `E:\LDPlayer\LDPlayer9`, set `ADB=`), probes `battleflow_scan.py`, `battleflow_names.py`, `entities_state.py`, `bw_api_props.py`, `prop_index_map.py`, `pat_probe.py` under `client/frida/payloads/`. `tools/probe.sh` needs a Python with `frida` (system Python has it; the project venv does not).

## Update 2026-11-19 (9): createEntity solved - zone and plane entities exist on the client

Read with `docs/CREATE_ENTITY_FORMAT.md` (static analysis of `libclient.so`, confirmed on LDPlayer). Supersedes the "framing not solved" bullet in (8).

- **Property data** (after the 3 direction bytes): `[flag u8 = 0][compression u8 = 0][mask flag u8]`, then either `mask flag 0` + every property in order, or `mask flag 1` + a bitmask of ceil(N/8) bytes (bit i set = property i is not on the stream, client default) + only the unmasked values in list order. The earlier "Invalid compression type" errors were the mask-flag byte being read as part of the data.
- **Property list** = ALL_CLIENTS / OTHER_CLIENTS properties in .def parse order; a re-defined name keeps its first position and its last definition (BattleGroundSpace has 92 entries, Plane 8). `battle_flow.other_client_props`.
- **Verified on the client** (fresh match, no stream errors): `plane0` (default Plane), `plane` (mapID 700, speed 60, two-point `movePath`), `spacemap` (mapID only; `enterWorld` then fails in `set_gameStatus` with `KeyError: 0`, so `gameStatus` must be a valid state, 1 works), and `space` (mapID, gameStatus 1, aliveNum 100, circleStage 1, white/blue circle centre and radius, `planeEntityIDs=[20002]`). Afterwards `Globals.spaceEntity` is the BattleGroundSpace and `BigWorld.entities[20002]` is a Plane (`client/frida/payloads/entities_state.py`).
- **Test commands** in `server/trigger_battle.txt`: `plane0`, `plane`, `space0`, `spacemap`, `space <x> <z>`, `leave <eid>`, `ce <eid> <Entity> <hex>`, `raw <hex>`.
- **Not done yet:** the player's `planeID` / `battleState` / `flightStage` are own-client properties and still need property-update messages; the zone shrink needs the same (stage, circle values, `updateCircleRestTime`). The in-battle request decoder (door `openElement(INT32,INT8)` / `closeElement(INT32)` on the space entity, `DtsProp.tryPickUp(INT32,BOOL)`) is not written, so doors and loot still do nothing. Property-update and entity-method message ids are unverified on this client.
- **Emulator setup note.** After the emulator network resets (DNS DNAT gone, game stuck at "Retrieving patch lists 0.00%"), run `client/scripts/setup_emulator.ps1`. Do not start `frida-server` before the game launches.

## Update 2026-11-19 (10): in-battle requests, doors and loot (first working pass)

- **Client requests.** Cell-method calls on an entity arrive as msg `0x80 | k` (var16), payload = target entity id u32 + args, `k` = position in the target type's exposed cell-method list. Verified: `BattleGroundSpace.openElement(INT32 elem, INT8 state)` = `0x88`, `closeElement(INT32)` = `0x89`, `DtsProp.tryPickUp(INT32, BOOL)` = `0x81`. The message splitter (`_BASEAPP_EXT_MSGS`) now treats `0x80-0xBF` as var16 (they were unknown and cut the bundle). `battle_flow.decode_request` / `Match.handle` answer them while in a match.
- **Doors.** `openElement` -> reply `BattleGroundSpace.onElementOpen(INT32, INT8)` (client method 40), `closeElement` -> `onElementClose(INT32)` (41). The client sends these itself (door opens on its side with the OPEN button); state is kept in `Match.doors`. The meaning of `state` and the `openedElements` property are not used yet. Not yet confirmed visually that a door opens with the reply.
- **Loot.** `DtsProp` entities (`entity id >= 30000`, `mapID`, `propID`, `amount` set) are created with `loot <x> <y> <z> [n]`; the client shows them on the ground and in the Nearby pick-up list (a gun on the ground, M4A1 Rifle, Grenade). Valid prop ids from `shared.lib.gametoolslib.properties.getBattleGroundPropData` (`client/frida/payloads/prop_ids.py`, 411 ids: guns 1001+, ammo 1101+, helmets 2200+, vests 2300+, cold weapons 1301+, bombs 1401+). Tapping a Nearby item sends `tryPickUp(INT32 1, BOOL)`; the server removes the prop (`leaveAoI`) and the list updates.
- **Avatar replies need +3.** The client's method index for `BattleGroundAvatar` is the raw `.def` index + 3 (sending raw 748 for `onPickUpPropEntity` ran `onUpdateRos2WeaponReloadTimeScale`, raw 745). `battle_flow.client_methods` applies `+3` (env `CM_OFFSET_BATTLEGROUNDAVATAR`); not yet re-tested live (the test player was being moved by someone else). Space/Plane/DtsProp use offset 0 until measured.
- **Not done.** Picked items do not reach the player's inventory (`dtsItemPackage` update), no loot table / building spawn for the map, no door state replay for new players, no position tracking (msgs 0xBC/0xBD are logged, not decoded), no countdown/plane/jump/zone shrink. Tasks RO-057/060/065/066/067 cover these.
- **Gateway hot reload.** In a match the gateway reloads `battle_flow.py` when it changes (`BATTLE_RELOAD=off` to disable) and keeps the match's door/loot state.

## Update 2026-11-19 (11): inventory pickup and door replies verified

- **Pickup -> inventory works.** After `tryPickUp` the server sends `leaveAoI(prop)` + `BattleGroundAvatar.onAddDtsItem(ITEM_ID, [ITEM_DATA_CONVERT{uuid, number, info, layout}], INT8 0, INT32 0)` + `onPickUpPropEntity()`. `onAddItem` is the wrong method (it feeds the Athlete package style and `onAddItemToTemporary` needs `const.PackageItemSourceEnum`, missing in this build). Verified: `player.dtsItemPackage.itemList == {1101: {<uuid>: {'number': 1, 'info': {'ex_tm': 0}}}}`, `getUsedGridNum() == 1`, no script errors (`client/frida/payloads/pkg_items.py`).
- **Method index offsets are not constant.** Client index = raw `.def` index + 3 near the end of the BattleGroundAvatar table (`onPickUpPropEntity`), +2 around `onAddItem` (420). `battle_flow.CM_DELTAS` holds per-method corrections; unmeasured methods use the entity default (+3 for BattleGroundAvatar, 0 for others). Check each new avatar method by sending it and reading the client log ("Failed to get arg ... for method X" names the method that ran).
- **Doors.** The client's `onElementOpen/onElementClose` (BattleGroundSpace) look up the scene object and call `ChangeInteractModelState(OPEN/CLOSED)`, so the server's echo opens/closes the door. Replies for door 832 (`openElement(832,1)`, `closeElement(832)`) raise no client errors; a door visibly opening was not captured in a screenshot.
- **Still open.** Weapons picked up are not equipped (`dtsWeapon1/2` property updates, `onWearDtsWeapon`), picked-up amounts are always 1, the wardrobe/appearance items in the Nearby list are test noise from the prop id list, no automatic loot/door placement for map 700.

## Update 2026-11-20 (12): property updates work; weapons equip

- **Property update message** (docs/ENTITY_PROPERTY_UPDATE_FORMAT.md, confirmed live): id `0xC0|idx` (var8) for index <= 60, else `0xFD` (var16) + entity id u32 + 2-byte bit path (9-bit index for BattleGroundAvatar, more-bit 0, padding) + the whole value. Index = position in the client's update list: .def parse order, first position / last definition, every property with flags & 6 (includes BASE_AND_CLIENT); BattleGroundAvatar has 495. `battle_flow.prop_update`.
- **Verified:** `setp dtsWeapon4 1302` set `dtsWeapon4` 0 -> 1302. `wpn 1 1001` (`dtsWeapon1` = BATTLE_GROUND_WEAPON_ITEM with weaponID 1001, `dtsCurWeapon` = 1, then `onWearDtsWeapon(1)`) gave `dtsCurWeapon == 1`, `dtsWeapon1['weaponID'] == 1001`, no client errors. Not yet seen on screen (a Quit dialog was open).
- **Gun pickup now equips:** `Match.handle` checks the prop's client type (`server/extract/battle_prop_types.json`, 411 ids from `prop_ids.py`; 99 Gun ids) and puts a Gun into the first free slot (1, then 2) instead of the bag. Ammo and other items still go to the bag. Not yet tested live.
- **Emulator:** LDPlayer now runs with 4 CPU cores (`ldconsole modify --index 0 --cpu 4`). With 2 cores the lobby scene took 41-54 s, past the client's 40 s inactivity timeout, so the client looped on login. With 4 cores it loads in about 40 s; still close to the limit.

## Update 2026-11-20 (13): player requests decoded; pose, put-gun, quit replies (untested live)

- Client->server player calls use the same extended index scheme as server->client calls (BattleGroundAvatar: 369 exposed methods, eff 60, ids 0xBC+ carry a sub byte). The client's exposed table is 2 entries ahead of the raw .def list from somewhere between index 53 and 205 (`onRecvClientFPS(30)` arrived as 291 = raw 289). `battle_flow.decode_request` applies the shift (env `EXPOSED_SHIFT_FROM`, `EXPOSED_SHIFT`).
- Decoded in a live match: `jumpStart(BOOL)`, `jumpEnd(FLOAT)`, `changePose(INT8)` (const.PlayerPose STAND 0, SQUAT 1, CRAWL 2), `doPutGun`, `changeDtsWeapon`, `exchangeLongGun`, `syncDtsWeaponOperate`, `fire`/`fireEnd`, `onRecvClientFPS`, `setPerspectPlayers`.
- New replies (not yet confirmed in game): `changePose` -> property `pose` (index 125); `doPutGun` -> `isPutgun`; `requestLeaveSpaceBeforeWin` / `suicideFromClient` -> back to the lobby via `_transition_to_athlete` (in `ros_server.py`, needs a gateway restart). Jump has no server reply yet; why it sticks is not known.
- The last door OPEN press produced no request in the gateway log, and the screen did not change; the client may have been frozen at that moment. Not resolved.

## Update 2026-11-20 (14): crouch, prone and jump verified

- After a PC restart: start the FastAPI server, `ldconsole launch --index 0`, run `client/scripts/setup_emulator.ps1` and set the 2022 date again. LDPlayer keeps the 4-core setting; the lobby loaded in 37 s.
- **Crouch and prone work.** `changePose(1)` / `changePose(2)` -> server sets property `pose`; the character crouches and lies down on screen. Standing back up works the same way (`changePose(0)`).
- **Jump works** in this test: `jumpStart(True)` then `jumpEnd(FLOAT)`, character lands and stands. No stuck jump seen; the earlier stuck state is not reproduced.
- Some decoded names are still suspect where the client/.def offset is not exactly +2 (e.g. `onDtsTrackingWeaponFire` arriving with the same FLOAT as `jumpEnd`, likely `onGetFallDamage`; `getOnTrain`, `startUninstallC4` without a train or C4). The offset needs measuring per range.
- **Quit Game** (`requestLeaveSpaceBeforeWin` -> lobby) is in the running gateway but not yet tested: the player was being moved by keyboard during the test.

## Update 2026-11-20 (15): Quit Game returns to the lobby

- Settings -> Quit Game -> Confirm sends a BASE method, not a cell method: msg `0xFD` (var16) with sub byte `0x7B` = `BattleGroundAvatar.requestLeaveDynamicSpace` (raw base index 181; exposed base table has 203 entries, eff 61, client index = raw + 3). It was ignored before because the in-battle handler only decoded cell calls (0x80-0xBF).
- `ros_server.py` now treats `0xFD 7B` in a match as leave and runs `_transition_to_athlete` (resetEntities + Athlete + onLogin/enterHall). Verified live: lobby reached in 22 s, no relogin. Env `BATTLE_LEAVE_SUB` overrides the sub byte.
- Harmless client script errors on the way out: `PlayerAthlete has no attribute hp`, `BattleGroundAvatar has no attribute checkHoldBreath`.

## Update 2026-11-20 (16): battle item catalog and icons for the admin console

- `client/frida/payloads/prop_catalog.py` reads the client's battle prop table (411 items: id, type, name, description, icon paths, weight, capacity). Saved as text in `server/extract/battle_props.json` and `../data/reference/original_battle_props.json` (served by `GET /api/v1/admin/original/props`).
- Icons: the NPK index stores only path hashes (`C_file.string_id(path)`, e.g. `ui/images/dts_item/package/icn_dts_guns_10.png` -> `aa4f54f4`), so files are read through the client instead: `C_file.get_res_file(path, '')` returns the PNG bytes. `export_icons.py` writes `<files>/ros_icons/<id>.png` on the device (295 of 408; the 113 misses are mostly appearance items, likely in sprite atlases). Pull with `adb pull`, then upload to the asset library (kind `prop`, key = id). The images stay in the server's git-ignored asset storage; none are committed.

## Update 2026-11-20 (14): pre-start countdown on screen; game-status values and map parameters read from the client

- **Countdown works.** `BattleGroundSpace` created with `gameStatus 1` makes the client show "Starting in N s!", `aliveNum` as "N LEFT" and the safe-zone circle on the minimap (LDPlayer, `space` trigger). The gateway now sends it by itself once per match, `BATTLE_SPACE_DELAY` (20) seconds after the avatar is created (`BATTLE_SPACE=off` disables it; log line `space entity (pre-start countdown)`). The N shown (79 s on the first try) is the client's own value from `mapData.PREPARE_TIME` and `gameStageStartTime`; where it comes from is not traced yet.
- **Game status values** (`BattleGroundGameStatusEnum`, read from the `AutoRoyaleSpace` module): READY 0, PREPARE 1, BEFORE_FIGHT 2, FIGHT 3, END 4. `set_gameStatus(0)` raised `KeyError: 0` on our space entity, `1` works. `set_gameStatus` reads `mapData.PREPARE_TIME`, `gameStageStartTime`, `MAP_MODE_PARAM`, `teamSize`, `MATCH_MIN_NUM`. `set_waitBornStatus` / `refreshWaitBornStatus` (`WaitBornStatus` SELECTING 0, LOADING 1, LOCK 2, FINISH 3) is the born-position selection step. `PlaneAuctionStage` WAIT 0, PREPARE 1, START 2, END 3.
- **Map table** (`maps_utils`). `getBattleGroundParamData(id)` answers for 700, 701, 702, 703, 722, 800 (`BattleGroundParam`) and 710 (`AutoRoyaleParam`); other ids hit a map class without `BATTLE_GROUND_PARAM` (20 = `HallMap`, 200 = `BattleMap`, 600/100 = `DungeonMap`, 300 = `VehicleArenaMap`, 400 = `RacingMap`). Map 700 `FIRST_WHITE_CIRCLE_TIME` 90, `INIT_WHITE_CIRCLE_RADIUS` 38000, `INIT_BLUE_CIRCLE_RADIUS` 32000, `CIRCLE_BOUND_BOX (-22429.98, -20648.09, 8450.52, 10375.44)`. 703 has `FIRST_WHITE_CIRCLE_TIME` 5 (a quick mode). `MAP_CLASS_TYPE` has `BattleGroundTrainMap` (space type 101) and `BattleGroundTutorialMap` (22).
- **Not found.** The map id or position of the small warm-up island seen in the original (minimap with one island, "Starting in 56 s", then the plane). None of the ids above is obviously it; it may be a region of the same scene reached by the spawn position. Next probe: read `BigWorld.player().mapData` (PREPARE_TIME, spawn/born positions) on a live map 700 and the scene's born points.
- **Probes added** (read-only, `bash tools/probe.sh <file>`; start `frida-server` only after the game has launched and stop it again): `client/frida/payloads/space_wait_probe.py`, `space_enum_probe.py`, `space_param_probe.py`.

## Update 2026-11-20 (15): countdown ticks; plane stage and fall reached on the client

- **Game clock.** The countdown counts `gameStageStartTime` (space, FLOAT) against `BigWorld.serverTime`. `serverTime` was stuck at 1.0 because nothing sent `setGameTime` (ClientInterface id 3, fixed u32 ticks): `serverTime = ticks / 10 + 1`, and it does not advance on its own. The gateway now sends `setGameTime` about once a second in a match (`_keepalive`, ticks = seconds since the avatar was created x 10; `BATTLE_GAMETIME=off` disables) and creates the space with `gameStageStartTime` = the current `serverTime` (`spacet`). Result on LDPlayer: "Starting in N s!" counts down from 79. A 2022 timestamp for `gameStageStartTime` made the number a scramble (wrong clock base).
- **Status** `gameStatus` 1 PREPARE shows the countdown; **2 BEFORE_FIGHT removes the banner** (`spaces 2 <stage>`, which leaves and recreates the space entity). The countdown number stops at 5 until the server changes the status.
- **Plane stage.** With the Plane entity created (`plane`) and the player's `planeID` set to its id (`setp planeID 20002`, INT32) the avatar goes into its on-plane pose and the minimap shows the flight path. After `gameStatus 2`, `planeID 0`, a forced position high above the map (`tp x y z`, ClientInterface 0x59, fixed 36 bytes: entity id, spaceID, vehicleID, position, direction; layout unverified but accepted) and `fallPhase` 2 (CAN_FALL, INT8) the client shows the plane HUD ("0 Onboard", skydive button, PARAGLIDER / PARACHUTE choice) and the player falls under the client's own physics. `const.FallPhase`: NORMAL 0, BEFORE_FALL 1, CAN_FALL 2, BEFORE_OPEN_PARACHUTE 3, CAN_OPEN_PARACHUTE 4, PARACHUTE_OPENED 5; `const.PlayerState`: Normal 0, Wounded 1, Died 2, Leaved 3, Parachute 4, InVehicle 5; `const.FlightStage` Launch 0, Fly 1, Ground 2 ...; `const.GlidePhase` HIGH_SPEED_GLIDE 6, FREE_GLIDE 7, LOW_SPEED_GLIDE 8; `JumpFlightParam` heights HEIGHT_CAN_OPEN_PARACHUTE 5000, HEIGHT_MUST_OPEN_PARACHUTE 500.
- **Automatic sequence.** `battle_flow.FLIGHT_STEPS` runs after the countdown (`BATTLE_PREPARE` 79 s after the space entity was sent; `BATTLE_FLIGHT=off` disables): plane + planeID, then BEFORE_FIGHT, then release, lift, CAN_FALL. `setp` now encodes INT8 / INT32 / FLOAT by the property's type. **Not done:** the plane does not carry the player along its path; the jump button press (the request name it sends was not seen in the gateway log) is not answered; no `fallPhase` / `battleState` progression to the parachute (3 to 5) or landing; no height-based glide / parachute prompts; the warm-up island. The player teleport target (698, 19300, -373) is a fixed point, not the plane position.
- **Probes added:** `flight_state_probe.py`, `server_time_probe2.py`, `space_status_dis.py`, `space_time_probe.py` (read-only, `bash tools/probe.sh`, `frida-server` only after the game has launched).

## Update 2026-11-21 (16): landing after the skydive works

- The client's position message is msg 3: 8 header bytes, then x, y, z as float32 (`Match.on_position`). The client keeps its own physics and stops at the terrain (at (698, -677, -373) after the fixed FLIGHT_START drop).
- After a fall of at least `LAND_MIN_FALL` (1000) and `LAND_STILL_SECS` (1.0 s) with no vertical movement, the server sends `fallPhase 0` and `flightStage 2`. Verified on LDPlayer: the skydive/plane HUD is replaced by the ground HUD (joystick, fist, stance buttons) and the player stands on map 700.
- Still open: the skydive pose (raised arms) stays on screen after landing; no parachute open (`fallPhase` 3 to 5) on the way down; the jump button sends nothing we log; FLIGHT_START is a fixed point, not the plane path; loot, zone shrink, bots, death and results screen.

## Update 2026-11-21 (17): fall phase 3 shows the skydive HUD; parachute open not solved

- The client sends `fall()` (exposed cell method, index 305 in `BattleGroundAvatar`) once it is free-falling. `Match.handle` answers with `fallPhase 3` (`FALL_REPLY_PHASE`); the client then shows the skydive HUD (speed in km/h, altitude bar with a parachute marker). Verified on LDPlayer.
- `changeFallPhase(INT8)` / `changeGlidePhase(INT8)` are applied to the matching property if the client sends them, but no run produced one: with nobody tapping, the player free-falls to the ground and `Match.on_position` lands it. What triggers the parachute (tap, or height-based client call) is not known. `setp fallPhase 5` mid-fall is not tested yet (test run was interrupted by a relogin).
- **Network change.** The PC's Wi-Fi IP changed (192.168.245.137 -> 192.168.8.72). Symptom: game stuck at "Retrieving patch lists 0.00%", no DNS or HTTP request in the logs. Fix: `$env:ROS_PC_IP` = new IP, run `client/scripts/sync_server_list.ps1`, start the server with that env, run `client/scripts/setup_emulator.ps1`, then delete the old DNAT rule on the emulator (`iptables -t nat -D OUTPUT -p udp --dport 53 -j DNAT --to-destination <old ip>:53`), since the old rule is matched first. `config.cmd` still has the old IP as default.
- Leftover `server/trigger_battle.txt` files fire into the next match; delete after an interrupted test.
- **Normal heroes only (hero_rules.py).** A player is the normal male (20001) or female (20002) hero. `createCharacter`, the saved `char_type`, `ATHLETE_CHAR`, the gender switch and the My Page `characterType` all go through `hero_rules.normalize_hero()`: 10001/10002 (no hall model on LDPlayer), the 30001 robot placeholder and unknown values become the hero of the saved gender. `MALE_CHAR`/`FEMALE_CHAR` overrides were removed. The tutorial Avatar still uses `AVATAR_CHAR` (30001) for load time. Verified by unit tests only; not yet re-checked on LDPlayer.

## Update 2026-11-21 (18): mailbox works; lobby audit

Read with `client/frida/payloads/mail_rank_dis.py`, `mail_ui_keys.py`, `mail_detail_dis.py`, `mail_enum.py` (client `entities\iChat.py`, `ui\UISystemMail.py`).

- **Lobby audit (LDPlayer).** Requests the gateway did not answer: `requestMails` (Mail, "Empty!"), `getFriendList` (Invite/Friends, "Nothing"), `requestLBSPlayerRank` / `requestLBSRankList` (data tab), `getHighestProficiencyWeapons` / `getAthleteRosMatchTeamBriefData` (My Page). Settings is client-only.
- **Mail (working, verified in game).** `server/lobby_mail.py`, mails in `server/lobby_mail.json` (editable), per-account read/claimed/deleted ids in `saved_accounts.json` `mail:<gid>`. The gateway reloads `lobby_mail.py` on every mail request (`MAIL_RELOAD=off` to disable).
  - `requestMails` -> `onMailUpdate(PYTHON mails, PYTHON topMails)`; mail dict `mailID, type, title, sender, when, unread` (+ `deadline` only if it expires: with the key present the list always shows "LEFT ..."). The timestamp key is `when` (`KeyError: 'when'` in `refreshMailList` otherwise). `topMails` = list of pinned ids.
  - `SysMailTypeEnum` (shared.shared_const): TXT 0, PROPS 1 (gift icon), NPC 2, TXT_PRIVATE 3, PROPS_PRIVATE 4, LEGION 5, QUIZ 6, ROS2_* 1000-1004.
  - `requestMailDetail(INT32)` -> `onLoadMailDetail(INT32, STRING content, PYTHON {"props": [[propID, count], ...]})`; item icons show under the text.
  - Claim -> `getAwardFromMail(INT32)` -> `onGetAwardFromMail(PYTHON {propID: count})` (a list of pairs raises `unhashable type: list`; an empty dict raises IndexError in `generateArgsForUIItemDisplay`, and both leave the lobby UI hidden). The client then sends `requestMails`. Verified: "AKM - Hellfire", "Tang Sanzang Frame", "S9 Training Medallion" result screen; items saved to the account (`_settle`, reason `gateway:mail:<id>`).
  - The client shows a Claim button on every mail. Claim on a mail with nothing left removes it (no reply, the client refreshes the list itself).
- **Test notes.** Script errors are logcat lines tagged `<SCRIPT>`. The weekly Supreme Supply push opens on every login; wait until its page has loaded before pressing back, or the tap is ignored. After a gateway restart the running client keeps its dead session (taps send nothing): relaunch the game.
- **Still open.** My Page weapon / match-team replies (`getHighestProficiencyWeapons`, `getAthleteRosMatchTeamBriefData`).

## Update 2026-11-21 (19): leaderboard, Activity panel, friend lists

Read with `client/frida/payloads/rank_dis.py`, `rank_panel_dis.py`, `rank_types.py`, `rank_cols_dis.py`, `welfare_attrs2.py`.

- **Leaderboard ("data" tab, ui.UIRankPanel) works, verified in game.** `server/lobby_rank.py` (reloaded on each request). Opening sends `updatePlayerLBSData(admin, sub)`, `requireRankInfo(INT32 type)` and `requireRankList(INT32 type, INT32 bufVersion, INT32 bufLength, BOOL nextBatch)`; Rank tab = type 35, Win = 37, Kill = 52.
  - List reply by `rank_list_utils.RANK_LIST_TYPE_DTS_{FORCE,WINNING,KILLING}_LIST`: `onRequireBattleGround{Force,Winning,Killing}RankList(INT32 start, ARRAY rows, INT32 version, INT32 rankType)`. `RankList.onGetRankData` replaces the buffer when the version changes and start == 0, appends when start == len(buffer).
  - Row = RANK_DATA (gid GID, nickname STRING, nationalFlag STRING, value INT32) + identifyTagID INT32 + Force (winRate, topFiveRate, killDeathRate FLOAT) / Win (winRate FLOAT, topFiveCount UINT32, topFiveRate FLOAT) / Kill (killCombo UINT16, killDeathRate, headshotRate FLOAT). Parent fields first (confirmed). Rates are fractions; the client shows value * 100 %.
  - Own row: `onGetPlayerBattleGroundRank(INT32 type, PY_DICT {"rank", "col-3".."col-6"})`; missing `col-N` raises KeyError in `*Component.infoInitFunc` and the row keeps "00000" placeholders. Columns: Rank tab points / win rate / top-5 rate; Win tab wins / win rate / top-5 count; Kill tab kills / most kills / KDR. The Rewards column is computed by the client.
  - Players listed: the accounts this server knows (now only the current player, stats from RoS_Server's profile or zeros). LBS (regional) requests get `onUpdatePlayerLBSData` echo and `onGetLBSRank([])`.
- **Activity panel opens (verified).** `UILimitWelfareController.on_enter` aborted on `isTelkosmeOpen`, set only by `syncTelkomseOpenStatus(BOOL)`; the gateway now sends `False` in `_lobby_data_calls`. Latest Event (Lucky Carnival, Season Bounty, Weekend Rush, Amazing $0.99, Drone, Paraglider) and Event (Limited Supply Box packs) render with no script error. The events' own pages are not checked yet.
- **Friend lists.** `getFriendList(UINT8 type)` (types 1, 2, 5 at login) -> `onGetFriendList(type, [] , {})`; no other players yet.

## Update 2026-11-21 (20): Top-Up grants diamonds; outfit shows in matches

Read with `client/frida/payloads/topup_dis.py`, `topup_confirm_dis.py`, `paygoods_table.py`, `match_appear.py`, `idress_dis.py`, `equip_parts_prop.py`, `equip_utils_dis.py`, `wear_propitem.py`.

- **Top-Up (verified, no payment).** A pack tap runs `Athlete.requsetPayGoods` -> base `requestRealNameAuthenCheckBeforeRequsetingPayGoods(STRING goodsID)`. Only the server's `onRequestRealNameAuthenCheckBeforeRequsetingPayGoods(goodsID, BOOL)` reply makes the client start the SDK / Google Play payment (`_requsetPayGoods`); the gateway never sends it. `server/lobby_topup.py` credits `AMOUNT + NORMAL_PRESENT` from the client's PayGoods table (`server/extract/pay_goods.json`, 121 packs, e.g. `com.netease.h45na.6` 60, `.12` 120+5, `.648` 6000+1380) and replies `onYBUpdated` + `onConfirmPayOrder(True, sn, ingot, ingot_send, [goodsID])` + `onAddHistoryPayGoodsIDs`. Saved like other diamonds (local `saved_accounts.json`, or RoS_Server `purchase` with a negative price when linked; refused -> nothing granted). `TOPUP_GRANT=off` disables it. `pay_utils.isPaying` expires by itself (PAYING_REQUIRE_CD). The "Limited extra 50%" badge (EXTRA) is an event bonus and is not granted. Verified: 100000 -> 100060 (60) -> 100185 (120+5), no billing activity in logcat.
- **Outfit in the match (verified).** The match model is dressed by `iDress.initDress` from `iDtsEquip.curr_equip_parts` = `equip_utils.getCurrentEquipPartsFromEquips(getCurrentEquips(avatar), characterType, battlegroundPropID2AppearanceIDDict)`; `getCurrentEquips` reads the INT32 cell props `dtsHelmet, dtsVest, dtsPackage, cloth0, cloth1, cloth3..cloth6`. `dtsWearableAppearanceList` alone changes nothing. A clothing skin is its own battle prop (hall `PROP_TYPE.PROP_ITEM_ID` == item id, e.g. 111900 "RWC-White"), so `avatar_create_messages(outfit=...)` puts each worn item into its slot from `extract/appearance_slots.json` (`["wear", "cloth0", gender]`), plus the four appearance lists and `dtsAppearanceGender` (base prop; the .def default 2 = female). `OUTFIT_IN_MATCH=off` disables it. The prop -> skin dictionary comes from `dtsBattlegroundPropAppearanceList` (not sent yet; needed for skins on picked-up battle clothes).

## Update 2026-11-21 (21): plane -> jump -> freefall

Read with `client/frida/payloads/plane_dis*.py`, `plane_users.py`, `plane_phase_dis.py`, `game_status_enum.py`, `fall_state.py`, `map_info.py`.

- **Enums.** `BattleGroundGameStatusEnum`: READY 0, PREPARE 1 (shows "Starting in N s", mapData.PREPARE_TIME = 80 on map 700), BEFORE_FIGHT 2, FIGHT 3, END 4. `const.FallPhase`: NORMAL 0, BEFORE_FALL 1, CAN_FALL 2, BEFORE_OPEN_PARACHUTE 3, CAN_OPEN_PARACHUTE 4, PARACHUTE_OPENED 5. `const.PlayerState` (battleState): Normal 0, Wounded 1, Died 2, Parachute 4, InVehicle 5, Swim 11. `const.PlaneWorkMode`: PEOPLE 1, PROP 2, REBORN 4.
- **Boarding (verified).** Zone (`BattleGroundSpace`, gameStatus BEFORE_FIGHT) + `Plane` createEntity, then the player properties `fallPhase` = CAN_FALL, `leftPlayerNumOnPlane`, `planeID` = plane id. `PlayerAvatar.set_planeID` -> `BigWorld.entities[planeID]` -> `getOnPlane` (camera on the plane, UIBattlegroundsFall: "1 Onboard", Paraglider/Parachute, Jump). planeID must be set after the plane has loaded and the loading screen is gone: set too early, `getOnPlane` does nothing; a plane entering the world during the loading screen runs getOnPlane -> enterObserverMode -> script error and the client hung (ANR).
- **Jump (verified).** Jump = cell `requestGetOffPlane()` (exposed index 77, arrives unshifted; the decoder's +2 shift now starts at 180, between 151 and 207). Reply: `planeID` 0, `battleState` Parachute, `fallPhase` BEFORE_OPEN_PARACHUTE -> freefall UI (speed, altitude bar).
- **Freefall with BEFORE_OPEN_PARACHUTE ignores the terrain.** With `fallPhase` 3 sent at the jump, the client falls through the ground (stopped at a world floor near y -620). The server must step `fallPhase` by height: client message 2 (position report) starts with x, y, z floats. `battle_flow.Match.on_message` (called for every in-match client message) opens the parachute at ground + 150 m (CAN_OPEN, OPENED) and lands at ground + 3 m (NORMAL, battleState Normal, hasLanded, forcedPosition a little above the ground so normal physics settles on the real terrain, zone -> FIGHT). Not yet seen end to end.
- **Positions.** `forcedPosition` (0x59, 36 bytes: id, spaceID, vehicleID, pos 3f, dir 3f) moves the own player (verified). `detailedPosition` (0x58) is 30 bytes, not the standard 28; plane movement (the Plane uses an AvatarFilter fed by server positions) is not streamed yet, so the plane is parked over the player. Map 700: MAP_RANGE (-20000, -20000, 20000, 20000); the spawn (0, 0, 0) settles on ground at y -468.5; the avatar's first position reports are the raw (0, 0, 0) before that.
- **Auto timeline (now off by default, `AUTO_BOARD=on`).** `AUTO_BOARD`, `BOARD_DELAY` 3 s, `PLANE_HEIGHT` 500, `PARACHUTE_HEIGHT` 150, `LAND_HEIGHT` 3. The plane spawns when the first non-origin position report arrives after the HUD is up; planeID is re-sent every 5 s while reports still show the ground. Trigger commands for tests: `board`, `fpos x y z`, `sprop name int`, `setp8 name int`.
- Superseded by section (22) after merging the team's update (14)-(17).

## Update 2026-11-26 (22): full drop verified (merged with the team's flight sequence)

- **Merge.** The team's update (`f4b1ed7`, sections 14-17: game clock `setGameTime`, countdown, `FLIGHT_STEPS`, `fall()` -> fallPhase 3, landing by position message 3) and sections 18-21 run together. The flight backbone is `FLIGHT_STEPS`; my height timeline (`Match.on_message`) is off by default (`AUTO_BOARD=on` enables it instead).
- **Boarding fix.** `FLIGHT_STEPS`: `plane` at +0 s, BEFORE_FIGHT space at +1 s, then at +3 s `planeID` 0 -> plane id, `leftPlayerNumOnPlane` 1, `fallPhase` 2. With planeID in the same step as the plane (the old step 0) the player stayed on the ground.
- **Jump button releases the player.** The automatic release after 2.5 s is gone (`FLIGHT_AUTO_RELEASE=on` restores it). `requestGetOffPlane` (the "jump sends nothing we log" in section 15/16 was the decoder shift, fixed in section 21) answers `planeID` 0, `forcedPosition` to `FLIGHT_START`, `fallPhase` CAN_FALL; the client falls on its own physics and stops at the terrain; `on_position` lands it.
- **Verified on LDPlayer (2026-11-26, after an emulator reboot):** match -> 79 s countdown -> camera on the plane ("Onboard", Jump button) -> Jump -> drop from (698, 19300, -373) -> "landed at (698, -677, -373)" -> ground HUD. Twice, once with the trigger, once fully automatic.
- **Still open.** The camera stays zoomed out after the first landing in a session; the jump point is the fixed `FLIGHT_START`, not the plane's position; the plane is not flown along `movePath` (`detailedPosition` 0x58 is 30 bytes, layout unknown); zone shrink (`circleStage`, circles, `updateCircleRestTime`, FIGHT).
- **Emulator reboot.** `ldconsole reboot` did not reboot (uptime unchanged); `ldconsole quit --index 0` + `launch --index 0` did. Then `client/scripts/setup_emulator.ps1` and `su -c 'date -u 042012002022.00'`.

## Update 2026-11-26 (23): skydive HUD and parachute work

- **Server-driven fall phases** (`Match._parachute_phase`, called from `on_position`). After the Jump the client does not always send `fall()`, so the server steps `fallPhase` by height, as fractions of the drop from the jump point to `FLIGHT_GROUND` (-677, the measured terrain under `FLIGHT_START`): 2 % -> BEFORE_OPEN_PARACHUTE + `battleState` Parachute (skydive HUD, 162 km/h); `CHUTE_BUTTON` 0.6 -> CAN_OPEN_PARACHUTE (the parachute button replaces the skydive button); `CHUTE_AUTO` 0.95 -> PARACHUTE_OPENED as a fallback.
- **The canopy needs the client's button.** `fallPhase` 5 sent by the server only changes the HUD icon (speed stays 162 km/h). The button (`UIBattlegroundsFall.doOnBtnOpenParachuteClick` -> `PlayerMachineMgr.onTrigger(TRIGGER_OPEN_PARACHUTE)`) opens the canopy on the client and sends `changeFallPhase(5)`. Verified on LDPlayer: parachute open, 21 km/h, landing, ground HUD.
- After the canopy is open the client sends `fall()` once more just before touchdown; the server now ignores it (`chute_open`), so the skydive state does not come back.
- Reports sent before the `forcedPosition` arrives carry the old position; the stepping starts only once a report is near the jump height (`fall_started`).
- **Hot reload.** Position reports now call `battle_flow.Match.on_position(match, ...)` through the module (a match object can predate a reload and keep the old method). Test command `drop` repeats the Jump release in the current match.

## Update 2026-11-26 (24): safe zone shrinks; property path fix

Read with `client/frida/payloads/zone_dis.py`, `circle_param.py`, `zone_state.py`.

- **Client side.** `BattleGroundSpace.updateBlueCircle` animates the blue circle toward each new `blueCircleRadius` / `blueCircleCenter` (0.05 s steps), so the server only sends the interpolated circle about once a second while it shrinks. `updateCircleRestTime(INT32)` (client method 45) drives the HUD zone timer, which counts down by itself; the minimap arc shows the shrink progress. `showCircleNotify(STRING)` / `showCircleMessage(INT8, STRING)` are not used yet.
- **Map 700 stages** (`maps_utils.getBattleGroundParamData(700)`): initial blue (-7507, -4674) r 32000; stages (wait s, shrink s, radius) = (270, 180, 16000), (150, 150, 10000), (120, 120, 6000), (120, 80, 3000), (90, 60, 1500), (90, 60, 750), (90, 60, 300), (120, 120, 0); DAMAGE 1, 1, 1, 1, 2, 3, 5, 7 per INTERVAL (5, 3.3, 2, 1 ... s).
- **Server timeline** (`Match.zone_start` / `zone_tick`, `battle_flow.py`): starts after the landing (`ZONE_AUTO`, default on): gameStatus FIGHT, stage 1, blue = initial circle, white = next radius placed toward the player and inside the blue; wait -> shrink (blue interpolated toward white, ~1 s steps, `blueCircleStart*` at shrink start) -> next stage; closes after stage 8. `ZONE_TIME_SCALE` (default 1.0) or the test command `zone <scale>` speeds it up.
- **Bug fixed: property path length.** `prop_update` always wrote a 2-byte bit path for property indices > 60. The path is index bits + 1 "more" bit padded to whole bytes: 2 bytes for BattleGroundAvatar (495 properties), **1 byte for BattleGroundSpace (95)**. With 2 bytes every zone value arrived shifted by one byte (radius x 256, centres near 0). Player updates are byte-identical to before.
- **Hot reload.** `_adopt(match)` moves a match object created before a reload onto the current `Match` class at every entry point (`on_message`, `on_position`, `handle`, `debug_command`).
- **Verified on LDPlayer:** client values after the fix: white (698, -373) r 16000, blue (-7507, -4674) r 32000, timer 27 s; at 10x speed all 8 stages ran; the zone timer counts down; the minimap draws the white and blue rings around the player at the small stages.
- **Still open.** The full map (UIDtsMap) shows no circles; no zone damage (the server has no health model yet); no circle notifications; the 3D blue wall was not checked.

## Update 2026-11-26 (25): the plane flies its route; jump from where it is

- **No client-side flight.** `Plane` has an `AvatarFilter` and only follows server positions; `movePath` / `moveSpeed` are not used to move it (the plane stayed at (0, 0, 0)).
- **detailedPosition layout (verified).** ClientInterface 0x58, fixed 30 bytes: entity id u32, position 3 x float32, direction 3 x float32 (roll, pitch, yaw), then 2 bytes of unknown meaning sent as 0 (`battle_flow.detailed_position`; `DPOS_TAIL=front` tries the 2 bytes after the id). The filter interpolates between updates. Test command `dpos <eid> <x> <y> <z> [yaw]`.
- **Flight.** `FLIGHT_STEPS` step 0 is now `flight`: the Plane is created at the start of `FLIGHT_ROUTE` (default `-16000,-14000,7000,6000`, through FLIGHT_START's area, at y 19300) with `mode` 1 (PEOPLE: the RoS transport jet model) and `movePath` = the route. `Match.flight_tick` sends `detailedPosition` every 0.2 s at `FLIGHT_SPEED` (500 units/s, about a minute across). The boarded player rides along (attached to the plane); the minimap scrolls with it.
- **Jump.** `requestGetOffPlane` releases the player at the plane's current position (`Match.release_from_plane`; a second press is ignored). At the end of the route a player still aboard is released automatically.
- **Verified on LDPlayer:** countdown -> jet flying over the island (minimap distance 1367 m -> 996 m in 6 s) -> Jump at (-2319, 19300, -2103) -> skydive -> parachute button at 60 % -> canopy (button pressed) -> landed in Echo Valley (-3275, -550, 1198) -> zone stage 1 centred there (270 s wait).
- **Note.** The Top-Ups (04:32:09-11) and the Supreme draws seen in these test sessions were made by hand in the LDPlayer window in parallel with the tests, not by the server or the test scripts.

## Update 2026-11-26 (26): zone damage

- **Server health model.** `Match.hp` starts at `MAX_HP` (100) when the flight is created. `hp_messages` sends `maxHp`, `hp` and `actualHP` together.
- **Damage** (`Match._zone_damage`, called from `zone_tick`):
  - When the player crosses the blue circle, the server sends `isInPoisonArea` (1 on leaving, 0 on re-entering).
  - While the player is outside, the server takes the stage's DAMAGE every INTERVAL (map 700 table, scaled by `ZONE_TIME_SCALE`), sends the HP props, and calls `showPoisonEffect`.
  - At 0 hp the server sends `battleState` 2 (Died) and logs `killed by the zone`.
- **Test command.** `zone <scale> away` places each white circle on the side of the map away from the player, so the blue circle passes over them.
- **Verified on LDPlayer** (`zone 0.2 away`, read with `hp_state.py`):
  - Leaving the zone in stage 2: `left the safe zone (hp 100)`.
  - Client values over time:
    - `hp 83`, `isInPoisonArea 1`, `battleState 0`
    - then `hp 0`, `battleState 2`
  - The server logged `killed by the zone` in stage 5. The green poison vignette shows at the screen edges. The zone went on to close after stage 8.
  - No client script errors in logcat.
- **Still open.**
  - There is no death or results screen. The client sits in the poison view with hp 0 (`onBattleGroundDie` and the match-end flow are not sent yet).
  - The HUD HP bar was not visible in this run (terrain and HUD were not loaded on LDPlayer after the long session).
  - The `showPoisonEffect` method index was not checked separately from the `isInPoisonArea` vignette.

## Update 2026-11-26 (27): match-end client methods (RE, def + `battle_flow.client_methods`)

Static only (no Frida). Source: `server/extract/entities_out/099_25abc9c1.bin` (`BattleGroundAvatar` ClientMethods) and `battle_flow.client_methods('BattleGroundAvatar')` (raw .def index + default `+3`, adjusted per `CM_DELTAS`).

| Client method | Wire index (this build) | Arguments (def) |
|---------------|-------------------------|-----------------|
| `onBattleGroundDie` | **266** | `PYTHON` — killer info dict (use empty `{}` when no killer, same shape as `onBattleGroundResult`’s second PY_DICT) |
| `onBattleGroundResult` | **267** | `INT32 gameType`, `INT8 teamSize`, `INT32 rank`, `INT32 total`, `INT32 bannerID`, `PY_DICT results`, `PY_DICT killerInfo` |
| `showPoisonEffect` | **659** | (no args in typical use; already sent from `_zone_damage`) |

**Recommended send order when HP reaches 0 (Harness H1):**

1. `prop_update` `battleState` = `2` (`Died`) — already in `_zone_damage`.
2. `client_call('BattleGroundAvatar', 'onBattleGroundDie', AVATAR_ID, blob(pickle.dumps({}, 2)))`.
3. `result_call(...)` → `onBattleGroundResult` (see `battle_flow.result_call`; `RESULT_GAME_TYPE`, `BANNER_*`, rows keyed by gid).
4. Optional polish: `BattleGroundSpace.gameStatus` = `GS_END` (4) and/or `client_call('BattleGroundSpace', 'gameEnd', SPACE_ID, …)` — not measured live yet.

**Note:** `Match.finish()` already calls `result_call` on zone death (§26) but **does not** send `onBattleGroundDie`; LOBBY_FINDINGS §26 “no results screen” likely means step 2 (or wrong result timing) is missing—not that `result_call` is absent from the server code path.

Re-run Frida `client/frida/payloads/result_dis.py` after lobby load to confirm UI handler names if indices drift after `CM_DELTAS` edits.

**Harness iteration 16 (2026-11-26):** `battle_flow.die_call()` sends `onBattleGroundDie` with `{}` when `Match.finish()` runs and `hp <= 0`, then existing `result_call()`. Live result UI still **unverified** on LDPlayer (harness shell lacked adb; parent run of `ld_debug_match.ps1` hit screenshot bug, fixed via `cmd /c exec-out` redirect like `harness_loop.ps1`).

## Update 2026-11-26 (28): wardrobe ITEMS tab (item skins: backpacks, helmets, vests, parachutes)

- **Was broken.** ITEMS-tab skins are `BattleGroundPropAppearanceType` (274 ids). The server had no list for them: `tryOnAppearance 103929: no shown list`, and `equipAppearance` only sent `onNotifyEquipedAppearance`.
- **Client rule** (`DtsAppearance.BattleGroundPropAppearanceType`, read with `client/frida/payloads/bgprop_appearance.py`):
  - Two skins share a slot when `dts_appearance_utils.getBattleGroundPropAppearanceAllPropIDs` sets overlap (`isForSameBattleGroundProp`).
  - Equip swaps; it never takes the item off. It also drops `isSameTypeFlyDecorate` items, but none of the 274 are fly decorates.
  - Prop sets: 1/2/3 helmet levels, 8/9/10 backpack levels, 100 parachute, 5/6/7, 2300001-3, 2400001, and one item with {2100001, 2101001, 2101011}.
  - Gender = `getBattleGroundPropAppearancePropGender`.
- **Server.**
  - `extract/appearance_slots.json` items get `["bgprop", "<prop ids>", gender]`.
  - `Outfit.LISTS` adds `bgprop`.
  - Lists: `dtsBattlegroundPropAppearanceList` / `dtsShowBattlegroundPropAppearanceList` (login).
  - Methods: `onUpdateBattlegroundPropAppearanceList` / `onUpdateDtsShowBattlegroundPropAppearanceList`.
  - `unloadAppearance` removes the item from both lists.
  - The match avatar gets `dtsBattlegroundPropAppearanceList`.
- **Not done.**
  - `dtsOutGameBag` (the bag carried on the hall model) is not tracked. The client resets it to 0 when the equipped bag is replaced.
  - `HeadFrameAppearanceType` equip is still `type not tracked`.
  - **Verified on LDPlayer:** try-on of Parasitoid lv 3 (103931) logs `tryOnAppearance 103931 (bgprop) -> shown [103931]`; the client shows the Try mark and the backpack model; the login outfit now includes `bgprop`.
  - Equip from the UI was not tested: the account owns no backpack, and buying one needs puzzle shards (balance 0). Offline checks of equip, try-off and save/load passed.

## Update 2026-11-26 (28): lobby profile card (portrait, level) verified

Read with `client/frida/payloads/profile_card.py`, `profile_card2.py`, `profile_avatar_state.py`, `portrait_size.py`, `meethttp_dis.py`, `level_dis.py`, `level_table.py`.

- **Card fields.** `UIMain._init_profile`: `baseNickname`, then `getAvatarProtratiAndFrame(p_profile, baseCharacterType, headFrameTag, online=True, fileID=portrait)`, then `updateLevel` (badge = `dtsLevel`, bar = `dtsExp / ExpLevelTable[dtsLevel].levelExp`).
- **No built-in portraits in this build.** `getAvatarProtrait` loads `ui/images/avatar/portrait/<char>_on.png` only for `fileID` '' or the literal `'""'`. With `'""'` the avatar ImageView stays 0x0 (`getVirtualRendererSize`), so the file is missing. `''` makes the caller look the photo up by gid (`getAvatarPortraitByGID`, online). `'0'` is ignored by `getAvatarPortraitByFPID` (it needs `len(fileID) >= 16`). Section 1's "'0' -> built-in" was wrong for this build.
- **Fix: serve the portrait over FilePicker.** `portrait_file_id()` default is `rosdefaultportrait01` (`PORTRAIT_BUILTIN` overrides). The client downloads it with `filePicker.download_file` from `g89ros.fp.ps.easebar.com/file/<id>`. `RoSHTTPHandler` now answers `/file/<id>` with `server/portraits/<id>.png|.jpg`, else `server/portraits/default.png` (a plain silhouette drawn with Pillow, not game art). The client caches it as `res/ui/images/tantan/<id>.png`.
- **Level / exp.** `dtsLevel` / `dtsExp` live in `childBaseClientPropertyList` (stream bug, not sent). `onAddDtsExp(INT32 dtsExp, INT32 dtsLevel, BOOL newLevelup)` (`iDtsLevelSystem`) sets both and calls `UIMain.updateLevel`. The gateway sends it with `onSetPortrait` 12 s after enterHall (`_sync_lobby_portrait`, log `profile sync ...`). Level per account in `saved_accounts.json` `level:<gid>` `{"level", "exp"}` (RoS_Server profile level when linked); also `baseLevel`, `requireBaseInfo`, `queryPersonalInfo`. Level table (1..300, `levelExp` 120 at level 1) in `server/extract/level_exp.json`.
- **Verified on LDPlayer (08:41 gateway):** `[FILEPICKER] 'rosdefaultportrait01' -> default.png`, the silhouette shows in the top-left card, badge 1.
- **Death screen still unverified.** The test match reached the landing (zone stage 1), but the gateway was restarted by another session at 08:54 before the `die` trigger was read.

## Update 2026-11-26 (29): Recruit Guide panel no longer locks the lobby

- **Cause.** The Recruit Guide tile (`UIMain.onClickPanelActivity4`) opens `ui.ros2.UIR2FlowActivity`.
  - Its `on_enter` -> `refreshDownloadStatus` -> `reqDLCSize` -> `BigMapDownloader.queryDLCTotalSize` fetches `https://h45na.update.easebar.com/pl/npk_version_na_ros2_inner_android.plist`.
  - The server answered with its JSON "patch up-to-date" reply, `Plist.from_url` raised `PatcherException`, and `on_enter` stopped halfway. The panel stayed half-open and the lobby took no more taps.
- **Fix.** The server serves `server/real/npk_version_na_ros2_inner_android.plist` (`static_map` in `ros_server.py`).
  - Same layout as the main list: `md5,size,path` lines, a `##########` line, then a JSON line.
  - It lists only `neox.xml` (already on the device), so the DLC size is 0.
- **Verified on LDPlayer:** the panel shows the 6 ROS 2.0 steps ("Not started yet", 0 %). Opened and closed it twice; the lobby still takes taps (the Activity tile opens); no script errors in logcat.
- **Not done.** The ROS 2.0 DLC steps have no server data (the progress stays at 0 %).

## Update 2026-11-26 (30): VIP Privilege screen

- **Cause.** `syncVipInfo` sent a flat `{"level": 0, "exp": 0, "rewardStatus": {}}`. The client keys `player.vipInfo` by card type (`const.Vip.TYPE_SILVER` 0, `TYPE_GOLD` 1), so:
  - `dts_vip_utils.hasRewardAvailable` (`vipInfo.iteritems()` -> `info["rewardStatus"]`) raised `'int' object has no attribute '__getitem__'`.
  - `getFirstAvailableLevel` raised `KeyError: 0`.
  - The half-drawn screen showed overlapping text ("VIP2VIP 2", scribbled card numbers).
- **Layout (read with Frida from `UIVipPrivilege` / `dts_vip_utils`).** Each of `vipInfo[0]` and `vipInfo[1]` holds:
  - `level` (max: silver 10, gold 8; gold may not exceed silver)
  - `rewardStatus` `{level: 0 NA / 1 AVAILABLE / 2 DONE}`
  - `num`: top-up total, compared with `TOP_UP_NUM` for the progress bar
  - `redPoint`: bool
  - `activeTime`: card start; the timer shows `activeTime + 30 days - now`
- **Rewards.** `legacyProperties.iterVipData` gives 18 rows (`REWARD_PROPS`, `TOP_UP_NUM`, `VIP_TYPE`), saved as `server/extract/vip_levels.json`.
- **Server.**
  - `server/lobby_vip.py` builds `vipInfo`. Levels come from `VIP_SILVER_LEVEL` / `VIP_GOLD_LEVEL` (default 0); `VIP_CARD_DAYS` (default 30).
  - `getVipReward(INT32 type, INT32 level)` / `getAllVipReward()` grant `REWARD_PROPS` (as mail claims do), mark the level DONE (`saved_accounts.json` `vip:<gid>`), then resend `syncVipInfo` + `onGetVipReward(type, level)` / `onGetAllVipReward({prop: 1})`.
- **Verified on LDPlayer.** Opened from Depot > Lobby Theme > Future Sight > "Acquire Silver VIP 7":
  - Both cards show VIP 0.
  - Silver shows "Top Up 60 to Claim Silver VIP 1" (page 1/10); gold shows "Top Up 60 to Claim Gold VIP 1" (page 2/8).
  - Paging, switching cards and closing all work, and the lobby still takes taps. No script errors.
- **Not tested.** Claiming a reward (needs `VIP_SILVER_LEVEL` > 0). Top-ups do not raise the VIP level yet.
- **Separate bug seen.** The top bar's **Benefits** panel raised `KeyError: 0` and locked the lobby. Fixed in update 31.

## Update 2026-11-26 (31): Benefits (Activity Points) panel

- **Cause.** `ui.UIDailyActivity.on_enter` reads the client-only fields `player.activityProgressList`, `activityStateList`, `dailyActivityRewardStateList` and `weeklyActivityRewardState`.
  - Only the `iDailyActivity.sync*` client methods fill them. The server never called those methods, so the fields stayed `{}`.
  - `_update_activity_progress` raised `KeyError: 0`, the panel never finished opening, its X did nothing, and the lobby stayed locked until a relaunch.
- **Fix** (enterHall, next to `syncVipInfo`). The server sends fresh-day values, as the client's own `resetDailyActivityState` builds them:
  - `syncDailyActivity(0)`
  - `syncDailyActivityRewardState([0]*4)` (30/60/90/120 points)
  - `syncWeeklyActivity(0)`
  - `syncWeeklyActivityRewardState([0]*2)` (300/600 points)
  - `syncActivityProgress([0]*14)` and `syncActivityState([0]*14)`
  - 14 = `properties.iterDailyActivityData` rows (ids 0-13: log in daily, share, survive 5/10/30 min, kills, vehicle, supplies, 1 km, open a Supply Box). `DAILY_ACTIVITY_COUNT` overrides it.
  - States are `const.RewardState` (0 UnmetNeeds, 1 MetNeeds, 2 GotReward).
- **Verified on LDPlayer:** the panel shows the activity list (0/1, 0/3 ...) and the daily and weekly tiers. Scrolling and the Level Packs tab work, and X closes back to a working lobby. No script errors.
- **Not done.** Activity progress is not tracked (always 0), and `getDailyActivityReward` / `getWeeklyActivityReward` are not handled.

## Update 2026-11-26 (32a): World entities — vehicles and supply drop (lane 5, RE + code, not yet seen on device)

Sources: `server/extract` defs read with `bwdefs` / `battle_flow.other_client_props`, the client script string tables in
`../decompile/script/strings/` (module per file, first line = module path), and `extract/message_map.txt`. No device run yet
(LDPlayer lock busy). Code: `server/battle_world.py`, one-line hooks in `battle_flow.py` (tagged `# lane 5`).

### Vehicles
- **Entity types.** `LandCar`, `LandBoat`, `LandMotor`, `LandBike`, `LandExpress`, `LandCraft`, `LandGlider`, `LandHelicopter`,
  `LandHoverCar`, `LandSnowboard`, ... (all `iLandVehicle`, client types 120+ in `client_entity_types.json`). Boats
  (15.20) are `LandBoat`.
- **createEntity list** (ALL_CLIENTS, `.def` order): `LandCar` has 73 entries. The model comes from **`tpsVehicleID`**
  (`iVehicleEntity.vehicleData` = `legacyProperties.getVehicleData(tpsVehicleID)`; `prerequisites` preloads
  `VEHICLE_BODY_MESH`, wheel meshes and the broken model from it). **`characterType`** selects
  `getLandVehicleData(characterType)` (the "landVehicleID" used for skins: `landVehicleID2AppearanceIDDict`).
  State: `hp/actualHP/maxHp/vHasHp/wheelHp`, `fuelAmount/capacity/fuelFull/comsumeFuel` (15.16), `maxSpeed/basicMaxSpeed/topSpeedClient`,
  `bActive/enabled` (the avatar's `canGetOnLandVehicle` requires `bActive`), `driverID`, `hasDriver`, `usedHangSockets`
  (`ARRAY<VEHICLE_SOCKET_INFO {sockname STRING, id UINT32}>`), `curAppearanceID` (15.19 vehicle skin), `canDriveInWater/OutWater`.
- **Requests the client sends** (BattleGroundAvatar exposed cell methods; raw exposed index, the decoder's +2 shift applies):
  `reqGetOnLandVehicleAsDriver(ENTITY_ID)` 237, `reqGetOnLandVehicleAsPassenger(ENTITY_ID)` 238, `reqGetOffLandVehicle(ENTITY_ID)` 241,
  `reqSwitchToDriveLandVehicle(ENTITY_ID)` 242, `reqSwitchDriveState()` 243, `reqSwitchToSeat(INT32)` 244, `vehicleHit(...)` 60
  (collision, 15.13), `getOnVehicle/enterVehicle/getOffVehicle` 279/280/284 (other vehicle kinds).
  The client sends them from `iLandDrive.reqGetOnLandVehicleAsDriver` etc. (a short `WaitForSeconds` coroutine first);
  the vehicle's own `reqDriver/reqPassenger/reqGetOff` cell methods are not exposed (server-internal).
  Exposed on `LandCar` itself: `openDoor/closeDoor`, `playTrumpet`, `onAccStart/onAccEnd`, `hitScene(VECTOR3, FLOAT)`,
  `getStepInWater/OutWater`, `onBoomComsumeFuel`, `resetPositionAndDirection`.
- **What makes the client sit in the car** (from the string tables, logic not disassembled yet):
  - avatar props `vehicleEntID`, `inLandVehicle`, `isLandDriver` -> `iLandDrive.refreshDriveState` -> `onSwitchToDriver` /
    `onSwitchToPassger` (driving HUD, camera); `onSwitchToOffVehicle` on the way out.
  - vehicle client methods `onAddAvatarSocket(STRING sockname, ENTITY_ID)` (binds the avatar to the seat socket, `msgEnterHangOnCar`,
    `onGetOn`), `onDelAvatarSocket`, `onAvtSwitchToSock` (15.06), `onPlayerEnter/Leave`, `onControlledBy(ENTITY_ID, BOOL)`
    (`beCntrl` when the id is the player -> `selectControl` -> `becomeClientControl` loads the first-person physics comps,
    `VehiclePhysicAssemble`), `onUncontrolledBy`, `onSyncPos(VECTOR3)` (server correction past `VEHICLE_POS_DIST_CORRECT_THRESHOLD`),
    `onTireIsBroken(INT32)`, `preShutDownVehicle`, `die(...)` (15.17), `damage(...)` (15.14).
  - ClientInterface **`controlEntity`** (message_map seq 111 -> wire id 0x5A, fixed 5: entity id u32 + bool) is the BigWorld switch
    that lets a client move a non-player entity. `enterAoIOnVehicle` (0x0D, fixed 9) and `setVehicle` (0x13) also exist.
  - While driving, the client should report the vehicle with `avatarUpdateExplicit` (client msg 3, entity id first);
    `battle_world.on_vehicle_update` logs those reports (15.12).
- **Server reply in `battle_world.get_on`** (order): vehicle `driverID`/`hasDriver`/`usedHangSockets`, `onPlayerEnter`,
  `onAddAvatarSocket(socket, 10003)`, avatar `vehicleEntID`/`inLandVehicle`/`inVehicle`/`isLandDriver`/`isDriver`, then for the driver
  `controlEntity(vid, 1)` + `onControlledBy(10003, 1)`. `get_off` reverses it and `forcedPosition`s the player beside the car.
- **Open (probe `client/frida/payloads/world_entities_probe.py`, read-only):** valid `tpsVehicleID` / `characterType` ids
  (defaults 1/1 are placeholders, env `VEHICLE_TPS`, `VEHICLE_CHAR`), `const.VEHICLE_DRIVER_SOCKET` (default `"driver"`, env
  `VEHICLE_DRIVER_SOCKET`), the seat socket names (`VEHICLE_SEATS_INFO.SOCKET_NAMES`), `const.PlayerState.InVehicle`, and the
  `LandCar` client-method index offset (`CM_OFFSET_LANDCAR`, 0 assumed). Map 700 vehicle spawn points are server data (not found in
  the client); the car is placed `VEHICLE_OFFSET` (60, 0, 60) from where the player lands.

### Supply drop
- **Aircraft = `Plane`** with `mode` not `PlaneWorkMode.PEOPLE` / `REBORN`: `Plane.getPreloadModel` / `enterWorld` then use
  `rc.AIRDROP_PLANE_MODEL` (`tps/car/airplane_airdrop`) and skip the boarding logic (`leaveWorld` only calls `getOffPlane` for
  PEOPLE/REBORN). The transport flight uses mode 1 (PEOPLE). Airdrop mode value is a guess (2, env `AIRDROP_PLANE_MODE`) until the probe.
- **Crate = `DtsPlayerHeritage`** (the loot-box entity, also used for death boxes). ALL_CLIENTS list (15): `mapID, socketHint,
  moveSpeed, items (PY_DICT), name, drop, dropping, heritageMode, appearanceID, ownerID, teamID, isStarDiamondNpc, playerID, trainID,
  trainPosition`. `drop` = 1 -> `AIR_DROP_MODEL` `character/female_battlegrounds/supplybox/supplybox_ros.gim`
  (gold variant for wild mode; `heritageMode` CHRISTMAS_DROP picks a seasonal model) and `onLoadAirDrop`; `dropping` = 1 ->
  `createParachute` (`parachute_04.gim`) + `AvatarDropFilter`; `set_dropping(0)` removes the parachute. The descent is server-driven
  (detailedPosition of the crate).
- **Opening:** proximity (`onPlayerEnter` -> `iDtsProp.nearGroundChest`, which also counts `SearchAirDrop` for missions) shows the
  pick-up list from `items` (`HeritageListControlComponent.__doRefreshHeritageItemList` iterates `items.iteritems()`, keyed by item
  uuid); a tap sends `DtsPlayerHeritage.tryPickUp(UUID, INT32, BOOL)` (exposed 1) / `tryPickUpForTeammate`. Client methods
  `updataItemAmount`, `resetItems` refresh the list. The value layout of `items` is not read yet (`AIRDROP_ITEM_FORMAT`).
- **Timeline in `battle_world`:** zone start + `AIRDROP_DELAY` (60 s x zone time scale) -> plane created on a route through a drop
  point `AIRDROP_OFFSET` from the player, `AIRDROP_PLANE_HEIGHT` above it -> detailedPosition every 0.2 s -> at mid-route the crate
  is created at the plane -> lowered at `AIRDROP_FALL_SPEED` -> on the ground `dropping` 0 -> plane `leaveAoI` at the end of the route.
  Loot is the fixed list `AIRDROP_ITEMS` (prop ids from `battle_props.json`). Map icons (`UIDtsMap.updateAirdropIcons`) not checked.
- **Property updates over 255 bytes** (the pickled `items`) can't use the var8 `0xC0|idx` form; `battle_world.prop_update_long`
  uses the 0xFD bit-path form instead (unverified for small property lists).
- **Switches.** Automatic spawns are opt-in: `WORLD_VEHICLES=on`, `WORLD_AIRDROP=on` (off by default so other lanes' matches are unaffected).
- **Triggers** (`server/trigger_battle.txt`, work without the switches): `car [dx dz]`, `airdrop`, `geton <vid> [p]`, `getoff <vid>`.

## Update 2026-11-26 (32): ITEMS sub-tabs, gliders/planes saved, Data Import

- **Sub-tabs.** Depot > ITEMS has eight sub-tabs; each lists only owned or on-sale items.
  - action: in-game emotes
  - helmet, box, parachute, last tab (ring icon), backpack: `BattleGroundPropAppearanceType` (`bgprop`)
  - glider: `JetWingsAppearanceType`
  - plane: `ShowAircraftAppearanceType`
- **Why choices came back as default after a restart.**
  - Gliders and planes were `type not tracked`, so they were never saved.
  - Item skins, clothes and lobby theme were already saved (`saved_accounts.json` `inventory:<gid>.outfit`).
  - In-game emotes need no saving: `dtsInGameActionAppearanceIDs` already holds every action.
- **Client rule** (`DtsAppearance.JetWings/ShowAircraftAppearanceType`): equip sets `dtsJetWingsAppearanceID` / `dtsShowAircraftAppearanceID` to the id and calls `onUpdateDtsJetWingsAppearanceID` / `onUpdateDtsShowAircraftAppearanceID`; unload sets 0.
- **Server.**
  - `Outfit.SINGLES` adds `jetwings` and `aircraft` to the saved outfit; `equipAppearance` / `unloadAppearance` handle them.
  - Login sets the two Athlete props.
  - The match avatar gets `dtsShowAircraftAppearanceID` and `lastJetWingsID`.
- **Data Import** (Depot button): `requestLoadOtherServerItemList()`. The client waits on "Importing..." for `onLoadOtherServerItemList(INT8)` (1 success, 2 fail, 3 cool-down; `iDtsAppearancePackage`). The server now answers 1, and the client shows "Import complete".
- **Test data.** `server/lobby_mail.json` mail 3, "ITEMS tab test pack", holds 23 items: one item skin per slot, 2 gliders, 2 planes, 1 `PlayerSfx`, 1 `Paint`. Claimed on LDPlayer; they appear in the helmet, parachute, glider, plane and backpack tabs. The box and ring-icon tabs stay empty (neither `PlayerSfx` nor `Paint` belongs there).
- **Verified on LDPlayer:** equipped Glider Wing (104935), Wingman - Marionette (106057) and Melon Helmet III (107902). After a full game relaunch:
  - The login state has `jetwings`, `aircraft` and `bgprop`.
  - The ticks show in the glider, plane and helmet tabs.
- **Not done.** The box and ring-icon tab types are unknown. Head frames (`HeadFrameAppearanceType`) are still `type not tracked`.

## Update 2026-11-26 (33): Other players — first createEntity of a non-player BattleGroundAvatar (lane 6)

- **Design:** [MULTIPLAYER_DESIGN.md](MULTIPLAYER_DESIGN.md). Code: `server/match_room.py`. Hooks in `ros_server.py` are tagged `# lane 6`.
- **The full 219-property createEntity crashes the client.** `ROOM_CE=full` sent mask flag 0 and every `battle_flow.other_client_props("BattleGroundAvatar")` value. The client logged "Pickler::unpickle: Failed to unpickle", then "PythonDataType::createFromStream: Not enough data", then "IntegerDataType ... Not enough data", then SIGSEGV in NeoXMain (logs/lane6_crash_logcat.txt). So the client's createEntity list for BattleGroundAvatar is **not** the parse-order ALL/OTHER_CLIENTS list that works for Space, Plane and DtsProp. The likely cause is the Avatar interface (`<Implements>`) order. Until the real list is read from the client, the bitmask (`ROOM_CE=mask`) has the same risk.
- **Workaround (`ROOM_CE=empty`, default):** createEntity with only the flag and compression bytes. The client builds its default dictionary from an empty stream (CREATE_ENTITY_FORMAT.md §2). Property updates follow with the update-list index, which is verified on the own BattleGroundAvatar.
