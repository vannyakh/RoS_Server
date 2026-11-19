@echo off
rem ===== RoS private server config (edit this) =====
rem LAN IP of this PC (must match what the phone/emulator uses as DNS + game server)
if "%ROS_PC_IP%"=="" set ROS_PC_IP=192.168.245.137
rem Lobby test account shown in the hall
if "%TEST_ACCOUNT_NAME%"=="" set TEST_ACCOUNT_NAME=TestPlayer
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
rem 2022-04-20 too, so the monthly Supreme page (device clock) works: keep SysEnableMonthSupply ON
rem here. On a device with the real 2026 date, remove this line (server default turns it off).
if "%GAME_DATE%"=="" set GAME_DATE=2022-04-20 12:00:00
set LOBBY_SWITCHES_OFF=SysEnableHuiliuRecallSystem,EnableRecallPlayer,EnableNewRecallPlayer
