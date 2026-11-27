RO-056 framing probes (read-only). Run from bigworld_gateway:
  bash tools/probe.sh client/frida/payloads/framing/ro056_entities_check.py logs/ro056_entities.log
Requires an in-match client after trigger_battle.txt `space` (or automatic BATTLE_SPACE spacet).

captures/
  ro056_entities_leave_space.log  — 2026-11-26 resume: after leave 20001 + space;
                                    ent20001.circleStage=1, Globals.spaceEntity set.
  lobby / match screenshots used while restoring START handoff (evidence only).
