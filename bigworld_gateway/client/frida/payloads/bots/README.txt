RO-068 / RO-069 bot entity probes
=================================

_ro068_probe_indices.py
  Offline (no device). Prints Robot create/update property indices, kill-related
  client method indices, and a sample enterAoI+createEntity hex for type 58.
  Run from repo root:
    .\.venv\Scripts\python.exe bigworld_gateway/client/frida/payloads/bots/_ro068_probe_indices.py

robot_entities_check.py
  Live NeoX Frida payload (same OUT pattern as entities_state.py). Lists Robot*
  entities and Globals.spaceEntity.aliveNum. Use after RO-069 spawns bots:
    bash tools/probe.sh bigworld_gateway/client/frida/payloads/bots/robot_entities_check.py

Evidence write-up: bigworld_gateway/docs/BOT_ENTITIES.md
