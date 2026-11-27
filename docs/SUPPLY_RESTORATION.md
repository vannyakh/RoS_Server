# Supply restoration status

Task RO-101. Status values: NOT_CHECKED, INVESTIGATING, FIXED, VERIFIED, BLOCKED. Nothing is VERIFIED without device proof on the original client. Data checks come from:

```powershell
.\.venv\Scripts\python.exe bigworld_gateway/tools/startup_trace.py --logs
```

## Data checked

Files: `bigworld_gateway/server/extract/supplement_info.json`, `supplement_props.json`, `supplement_ids.json`. They were dumped from the client (`supplement_utils.getAvailableSupplementDictByTime()` and `getAllPossiblePropID`, Frida payloads `supplement_dict*.py`, `supplement_props.py`).

- 264 boxes in each file. Every box has a prize pool (32-780 prop ids).
- Fields: `CURRENCY_ID`, `BUY_TIMES_PRICE`, `BUY_MULTIPLE_TIMES_PRICE`, `CURRENT_DISCOUNT`, `IS_IN_SALE`, `IS_THIS_WEEK`, `IS_LAST_WEEK`, `IS_PREVIOUS_BOX`, `KIND`, `SORT_KEY`.
- **No sale dates are stored.** Date ranges against the 2022-04-20 emulator clock and a 2026 clock cannot be checked from these files. LOBBY_FINDINGS (month_dates_probe) records that the last monthly box ends 2022.12.30.
- Currency and price shapes agree in every box: a list currency has a list price of the same length.
- Multi draw is 10 for every box (`athlete_requests.multi_count`). Box 2 has multi price `[0, 0]` (no 10x draw).
- 49 boxes have `IS_IN_SALE` false. The gateway does not check this flag on a draw (box 45 was drawn in `logs/server.stuck-20261120-2233.log`).
- `IS_THIS_WEEK` is true for boxes 9778 and 9779 (both KIND 7, monthly).
- Ticket currencies seeded at login with 999 each (`ATHLETE_SEED_TICKETS`): 6, 9, 11, 91, 202, 207, 214.

`KIND` maps one-to-one to the client kind names in `supplement_ids.json`:

| KIND | Client kind | Boxes | Currencies | Single / multi price |
|---|---|---|---|---|
| 1 | NORMAL_SUPPLEMENT | 7 | [2, 202] | [5, 50] / [50, 500] |
| 2 | TIME_LIMIT_SUPPLEMENT | 1 | [6, 11] | [10, 15] / [0, 0] |
| 3 | GUARANTEE_SUPPLEMENT | 48 | 9 or [91, 2] | 300 or [5, 120] / ... |
| 4 | GUARANTEE_SUPPLEMENT_VEHICLE | 32 | 2 | 20-200 / 180-1800 |
| 5 | WEAPON_SUPPLEMENT | 75 | 2 | 10-20 / 95-190 |
| 7 | MONTH_SUPPLEMENT | 79 | [214, 2] or 2 | [1, 20] or 20 / [10, 190] or 190 |
| 99 | KOF_SUPPLEMENT | 2 | 2 | 20 / 190 |
| 101-103 | ANNIVERSARY_CLOTH / WEAPON / VEHICLE | 16 | 207 | 2-25 / 19-240 |
| 202 | BLACK_FRIDAY_2020 | 4 | 2 | 20, 200 / 190, 1800 |

The data has no field that names the UI tab (Star, Supreme, Looks, Vehicle, Firearms). The mapping below is inferred and marked with its source.

## Per category

| Category | Boxes (inferred) | Status | Evidence |
|---|---|---|---|
| Star | Unknown: no kind or field names it | NOT_CHECKED | `bigworld_gateway/docs/PHONE_SETUP.md`: Star Supply shows "coming soon". No request or box id tied to it in logs |
| Supreme | KIND 7 MONTH_SUPPLEMENT (79), maybe KIND 1 | INVESTIGATING | LOBBY_FINDINGS calls the monthly box "Supreme"; `ros_server.py` comment "Supreme: 214/202" (214 = monthly, 202 = KIND 1). No draw of a KIND 7 box in any saved log. Monthly page black on a 2026 device (below) |
| Looks | KIND 3 GUARANTEE_SUPPLEMENT (currency 91) | INVESTIGATING | `ros_server.py` comment "Looks Supply: currency 91"; only KIND 3 boxes use 91. Draw on box 105 (KIND 3) in saved logs |
| Vehicle | KIND 4 GUARANTEE_SUPPLEMENT_VEHICLE | INVESTIGATING | Kind name. Multi draws on box 9331 in saved logs |
| Firearms | KIND 5 WEAPON_SUPPLEMENT | INVESTIGATING | Kind name. Multi draws on boxes 13 and 45 in saved logs |

Logged draws (all `logs/server*.log`): `openMultipleSupplyBox` on boxes 1, 13, 45, 105, 9331 and `openSupplyBox` on box 2. A logged request and reply is not device proof that the result screen rendered correctly, so nothing is VERIFIED.

## Why Supply opens at startup

Two client pushes can open Supply right after the lobby loads. Both depend on "already shown" state the gateway does not keep correctly.

1. **Monthly Supreme push.** `hasAlreadyShowMonthSupply` (INT32, comment "whether the monthly special purchase was shown") is a field of the Athlete property `childClientPropertyList2` (`extract/entities_out/161_401513ba.bin`, `ichildtable.def`). The gateway sends that property with .def defaults, so it is 0 at every login. In `logs/server.prev6.log` and `logs/server.prev7.log` the client sends `setHasAlreadyShowMonthSupply` right after `requestEnterWorldOpenUI` and then `queryAvailableSupplement` about 3 s later, with no tap in between. The gateway has no handler for `setHasAlreadyShowMonthSupply`, so the flag stays 0 and the push repeats. This push only runs while `SysEnableMonthSupply` is on (on in `config.cmd` for the 2022 emulator).
2. **Weekly push.** `UIMgr.gotoThisWeekSupplyPackage` opens Supply until `hasAlreadyShowSupplyID` equals this week's box (LOBBY_FINDINGS, update 5). The gateway sends `onUpdateAlreadyShowSupplyID(saved id or 0)` (`_lobby_data_calls`, ~line 2346). `saved_accounts.json` has no `supply_push` key and no saved log contains `setHasAlreadyShowSupplyID`, so 0 is sent every time. The data has two this-week boxes (9778, 9779). Also, the `.def` declares `setHasAlreadyShowSupplyID` with **no arguments**, but the gateway handler reads an INT32 (`rd.i32()`, ~line 1838). If the client ever sends it, the read fails and nothing is saved.
3. **First-time draw tutorial.** LOBBY_FINDINGS ("Draw tutorial") records a first-time "Supreme Supply" tutorial after `enterHall` whose buttons send requests the gateway does not answer. Not re-checked since.

`enterHall(False)` (`HALL_POPUPS=off`) does not stop these: LOBBY_FINDINGS notes popups still appear with False.

Across saved logs the first `queryAvailableSupplement` comes 3 s after the lobby UI in 4 sessions (auto-open pattern) and 7-215 s after it in the others (user tap).

## Supreme Supply black content area

Cause (source evidence):

- `supplement_utils.getCurrentMonthSupplementID` uses the **device clock** (`time.time()`), not the server clock sent by `syncServerTime` (LOBBY_FINDINGS update 5, `month_supply.py` probe). The last monthly box ends 2022.12.30. On a device dated 2026 it returns None, and `UIMonthlySupplyPackage.Awake` fails, leaving the page blank.
- The gateway turns the page off by default with `onSetSwitches("SysEnableMonthSupply", 0)` (`LOBBY_SWITCHES_OFF` default, `_lobby_data_calls` ~line 2342). Then the Supreme tab does nothing instead of crashing.
- `bigworld_gateway/config.cmd` overrides `LOBBY_SWITCHES_OFF` without `SysEnableMonthSupply`, keeping the page on, because LDPlayer is set to 2022-04-20. LOBBY_FINDINGS records that with that date the page opens without a script error. If the emulator date resets to the real date (for example after a restart, before `date -u 042012002022.00` is run again) while `config.cmd` still keeps the switch on, the page goes black again.
- **Automated fix:** `bigworld_gateway/client/scripts/setup_emulator.ps1` now runs `settings put global auto_time 0` and `date -u 042012002022.00` after DNS/CA setup (skip with `-SkipLobbyDate`). Re-run after every LDPlayer cold start.

What the server can do:

- Keep `SysEnableMonthSupply` off whenever the device date is not in 2022 (the server cannot read the device clock; it can only choose the switch).
- Send the monthly push state so the page is not pushed at every login (see recommendations in the RO-101 report).

What needs the device or a client change:

- Showing the monthly page with real content needs a device date before 2022-12-30 (or a client patch of `getCurrentMonthSupplementID`). The server clock alone cannot fix it.

## Looks Supply lag / wrong Supreme banner (gateway tuning)

Symptoms on LDPlayer: **LOOKS SUPPLY** selected but the centre preview is empty or **Previous** (Aurora) is slow to update, while the right panel still shows the weekly **Supreme** event (`THE SUN KNOWS EVERYTHING`).

Likely cause: login used to send `onQueryAvailableSupplement({})` until the client requested the full catalogue; the weekly push (`IS_THIS_WEEK` boxes 9778/9779, KIND 7) can auto-open Supreme before the Looks tab refreshes.

**`bigworld_gateway/config.cmd` (LDPlayer 2022 date)** sets:

- `SUPPLY_CATALOG_AT_LOGIN=1` — same cached pickle as `queryAvailableSupplement` at login.
- `SUPPLY_CLEAR_WEEKLY_FLAGS=1` — clears `IS_THIS_WEEK` on boxes 9778/9779 in the sent catalogue so Supreme/Helios is not the default art.
- `SysEnableMonthSupply` in `LOBBY_SWITCHES_OFF` — turns off the monthly Supreme overlay that shares the Supply UI.

Do **not** use `SUPPLY_PREACK_WEEKLY_PUSH=1`: it stores Supreme box **9778** in `alreadyShowSupplyID` and can pin Helios on first open.

Clear `supply_push` in `saved_accounts.json` (or delete the file) after changing these flags, then restart the gateway (`supply_cache.warm()` runs at import).

## Open questions (need a read-only probe or device test)

- What value `hasAlreadyShowMonthSupply` must hold to suppress the push (month number, box id, or flag). Do not guess; read the client code with a read-only Frida probe first.
- Which boxes the Star and Supreme tabs list.
- Whether the empty `onQueryAvailableSupplement({})` stub at login affects the first Supply screen opened by a push before the full catalogue arrives.
