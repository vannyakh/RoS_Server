#!/usr/bin/env bash
# Restart the game on LDPlayer and drive it into a match on map 700 (lobby -> START).
# Taps assume a 1920x1080 landscape screen and the first-login popups seen on this build
# (Supreme Supply page -> back x2, My Page -> close). Usage: bash tools/to_match.sh
cd "$(dirname "$0")/.."
ADB="${ADB:-/e/LDPlayer/LDPlayer9/adb.exe}"
w() { t=$(( $(date +%s) + $1 )); until [ $(date +%s) -ge $t ]; do sleep 1; done; }
rm -f server/trigger_battle.txt
$ADB shell "for p in \$(pidof frida-server); do kill -9 \$p; done" 2>/dev/null
$ADB shell am force-stop com.netease.chiji
n=$(grep -c athleteEnterHall logs/server.log)
$ADB shell monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
w 45; $ADB shell input tap 1843 108; w 2; $ADB shell input tap 950 790   # close notice, PLAY (login screen)
t=$(( $(date +%s) + 180 )); until [ "$(grep -c athleteEnterHall logs/server.log)" -gt "$n" ] || [ $(date +%s) -ge $t ]; do sleep 3; done
w 100                                   # hall scene load (~35 s) + popups
$ADB shell input tap 90 40;   w 6       # Supply page -> back
$ADB shell input tap 90 40;   w 7       # (second back lands on My Page)
$ADB shell input tap 1833 117; w 5      # close My Page
n=$(grep -c "\-> battle: resetEntities" logs/server.log)
$ADB shell input tap 1630 970           # START
t=$(( $(date +%s) + 60 )); until [ "$(grep -c "\-> battle: resetEntities" logs/server.log)" -gt "$n" ] || [ $(date +%s) -ge $t ]; do sleep 2; done
w 45                                    # map 700 load
grep "\-> battle" logs/server.log | tail -1
