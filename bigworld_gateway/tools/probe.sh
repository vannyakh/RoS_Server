#!/usr/bin/env bash
# Run a read-only Python payload in the game via Frida (emulated realm) and print its output.
# Usage: bash probe.sh client/frida/payloads/<payload>.py [outfile]
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
A="/c/LDPlayer/LDPlayer9/adb.exe -s ${ADB_SERIAL:-emulator-5554}"
F=/storage/emulated/0/Android/data/com.netease.chiji/files
OUTF=${2:-py_out_probe.log}
$A shell "rm -f $F/py_out.log"
$A push "$1" $F/py_payload.py >/dev/null
timeout 60 "${PY:-python}" -u client/scripts/run_frida.py client/frida/neox_py_eval.js --attach --realm emulated 2>&1 | grep -E "payload|rror|Process not found"
$A shell "cat $F/py_out.log" > "$OUTF"
cut -c1-900 "$OUTF"
