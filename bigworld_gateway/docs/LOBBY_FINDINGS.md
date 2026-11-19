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

## Update 2026-11-19 (3): items, diamonds and outfit saved in RoS_Server

- RoS_Server keeps the original-client state per gateway identity: `gateway_items` (prop_id, number), `gateway_identities.outfit` ({body, wear}) and the diamond balance as currency `yuanbao` in the normal ledger (`currency_transactions`, reasons `gateway:start`, `gateway:draw:<box>`, `gateway:buy:<prop>`). New players start with `GATEWAY_STARTING_YUANBAO` (default 100000).
- API (X-Gateway-Key): `GET /api/v1/gateway/accounts/{uid}/state`, `POST .../purchase` {price, props, reason} (charge + add items in one transaction, 409 if too few diamonds), `PUT .../outfit` {body, wear}.
- Gateway: login loads the state once (`ros_server.LOGIN_STATE`) and puts it in the Athlete props (`freeYuanbao`, `dtsAppearancePackage` with `info={"ex_tm": 0}`, `dtsWearableAppearanceList` / `dtsShowWearableAppearanceList`, `dtsShowBodyAppearanceList`). Every draw/buy goes through `GateUDP._settle` -> `account_link.purchase`; equips call `account_link.set_outfit`. Without the link (no `GATEWAY_API_KEY` or API down) it falls back to session-only.
- Verified on LDPlayer: after draws (diamonds 99510, 45 items) and wearing War Boy - Yellow, a fresh login shows 99510 diamonds and the mask still worn.

