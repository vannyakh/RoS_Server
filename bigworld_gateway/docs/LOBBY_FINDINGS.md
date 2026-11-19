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
- `portrait` lives in Athlete `childBaseClientPropertyList` (FIXED_DICT field `portrait`, STRING). The gateway sends it empty.
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

