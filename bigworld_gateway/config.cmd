@echo off
rem ===== RoS private server config (edit this) =====
rem LAN IP of this PC (must match what the phone/emulator uses as DNS + game server)
if "%ROS_PC_IP%"=="" set ROS_PC_IP=192.168.1.21
rem Fixed lobby test account. Leave EMPTY for real new-player behaviour: a new device account
rem gets the in-game character screen (normal male/female human, starter outfit, no hero).
rem Set it (e.g. TestPlayer) only to skip that screen for quick tests.
if "%TEST_ACCOUNT_NAME%"=="" set TEST_ACCOUNT_NAME=
rem Server behaviour (working lobby route: base-only Athlete, method ids 0x80)
set REPLY_VARIANT=24
set CBP_TYPE=41
set CBP_PROPS=account
set SWITCH_TO=athlete
set AUTO_TRANSITION_HALL=on
set TRANSITION_DELAY=3
set HALL_DELAY=3
set ATHLETE_CELL=off
set TRANSITION_RESET=off
set LEAVE_OLD_AVATAR=off
set METHOD_BASE=0x80
set METHOD_EXT=byte
rem --- phone/session stability (verified 2026-11-18) ---
rem 6023 individual item-add calls freeze the game main thread; keep off (or send far fewer / slower)
set UNLOCK_ALL=off
rem server heartbeat packets caused REASON_CORRUPTED_PACKET relog loops; keep off
set HALL_HEARTBEAT=0
set FRAG_BODY=700
rem --- lobby date (2026-11-19) ---
rem Game data ends in 2022: the server clock runs from GAME_DATE. LDPlayer's own date is set to
rem 2022-04-20 too (setup_emulator.ps1 after each cold start).
if "%GAME_DATE%"=="" set GAME_DATE=2022-04-20 12:00:00
rem SysEnableMonthSupply OFF avoids Supreme/Helios art on the Looks tab on first Supply open.
rem To test the monthly Supreme page again, drop SysEnableMonthSupply from this list.
set LOBBY_SWITCHES_OFF=SysEnableHuiliuRecallSystem,EnableRecallPlayer,EnableNewRecallPlayer
rem Supply: full catalogue at login; strip IS_THIS_WEEK so weekly Supreme boxes do not own the UI.
rem Do not set SUPPLY_PREACK_WEEKLY_PUSH=1 (stores Supreme box 9778 and pins the wrong banner).
set SUPPLY_CATALOG_AT_LOGIN=1
set SUPPLY_CLEAR_WEEKLY_FLAGS=1
rem Complete Top-up IAP on the gateway (no real USD / mpay). off = check/limit replies only.
if "%GATEWAY_PRIVATE_TOPUP%"=="" set GATEWAY_PRIVATE_TOPUP=on
rem Special Distinction (Brave Book): free Buy Special on the gateway by default (diamond cost via GATEWAY_BRAVE_BOOK_PASS_DIAMONDS).
if "%GATEWAY_FREE_BRAVE_BOOK_PASS%"=="" set GATEWAY_FREE_BRAVE_BOOK_PASS=on
if "%GATEWAY_CURRENT_SEASON%"=="" set GATEWAY_CURRENT_SEASON=21
rem Match modules (space/plane/jump/zone/props) own entity creation; disable legacy spacet.
if "%BATTLE_SPACE%"=="" set BATTLE_SPACE=off
