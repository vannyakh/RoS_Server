# Resource loading: what the server controls

Task RO-101. Plain split between what the gateway (`bigworld_gateway/server/ros_server.py`) controls and what the original client APK does on its own.

## Server controls

- **Which messages are sent and when.** Login stream about 7 KB in 12 UDP fragments (`FRAG_BODY=700`), built in under 1 s (see STARTUP_FLOW.md). Supply catalogue 17,098 B in 25 fragments, sent only when the client asks.
- **Data values.** Server clock (`syncServerTime`, `GAME_DATE`), feature switches (`onSetSwitches`), owned items, outfit, currencies, hall theme id, box prices and prize pools.
- **Which client screens get pushed.** Indirectly: switches and "already shown" state decide whether the client opens popups such as Supply at login (SUPPLY_RESTORATION.md).
- **Server CPU per login.** About 0.2-0.3 s to build `createBasePlayer` and the first login bundle in one process.

## Client APK controls (server cannot change)

- **Scene and asset loading.** `scene\hall\hall.scn` blocks the client game thread for about 35-40 s on LDPlayer with 4 cores and 41-54 s with 2 cores (LOBBY_FINDINGS). Saved logs show 38-61 s from `Account.handshake` to the lobby UI. The gateway is idle (keepalive ACKs only) during that time.
- **Textures, models, UI atlases, icons.** Packed in the APK/NPK files. The server sends ids only; the client loads the files.
- **Rendering and frame rate.** GPU work, shaders, effects and resolution are client-side. **Server work cannot fix low GPU FPS.** Emulator settings (CPU cores, GPU mode, resolution, frame cap) and the host GPU decide it.
- **Device-clock checks.** `supplement_utils.getCurrentMonthSupplementID` uses `time.time()` on the device. Only the device date or a client change affects it.
- **The 40 s inactivity timeout.** The client drops the connection when the scene load passes it (LOBBY_FINDINGS). Server keepalives did not help.

## Practical guidance

- To shorten startup on LDPlayer: give the emulator more CPU cores and do not attach Frida probes while the lobby loads (LOBBY_FINDINGS "Slow lobby load").
- Cutting server messages saves milliseconds, not the 40 s scene load. Any cut needs a device test (STARTUP_FLOW.md).
- A black or empty screen caused by the device clock is not a missing server resource. Check the device date and the `SysEnableMonthSupply` switch first.
