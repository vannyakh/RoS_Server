#!/usr/bin/env bash
# Lobby cycle, then back out of the first-time Supply screen, tap START and wait.
# Writes logs/start.png, logs/battle.png, logs/match_server.txt, logs/match_script.txt.
# Usage: bash tools/cycles/match_cycle.sh [wait_after_start_s=60]
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
export PY=${PY:-../.venv/Scripts/python.exe}
A="/c/LDPlayer/LDPlayer9/adb.exe -s ${ADB_SERIAL:-emulator-5554}"
WAIT=${1:-60}
timeout 400 bash tools/cycles/lobby_cycle.sh 30 | tail -1
for i in $(seq 1 24); do
  sleep 15
  [ "$($A logcat -d 2>/dev/null | grep -a -c 'hall2')" -gt 0 ] && { echo "[hall2 after $((i*15))s]"; break; }
done
sleep 15
$A shell input tap 150 35; sleep 5; $A shell input tap 150 35; sleep 6   # back x2 -> main lobby
L=$(wc -l < logs/server.log)
$A logcat -c
$A shell input tap 1280 805                                              # START
sleep 8; $A exec-out screencap -p > logs/start.png
sleep "$WAIT"; $A exec-out screencap -p > logs/battle.png
tail -n +"$L" logs/server.log | grep -a -v "client msgs\|saLog\|BASEAPP RECV\|BASEAPP SEND\|ACKed\|Client seq" > logs/match_server.txt
$A logcat -d -v time 2>/dev/null | grep -a "<SCRIPT>" | cut -c1-400 > logs/match_script.txt
$A shell pidof com.netease.chiji >/dev/null || echo "[game process is gone]"
echo done
