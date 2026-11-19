# Note10+ (SM-N976N, not rooted) — working setup (verified 2026-11-18)

Result: phone logs in with Guest, loads the lobby (hall in ~32 s), hero + currencies + Depot/Store/Supply/Lucky Club open.

## Pieces
1. **Firewall** (admin PowerShell): `server\..\..\setup_firewall.ps1` equivalent -> rule "RoS Private Harness" (TCP 80,443,20001,25000; UDP 53,20001,25000; Private profile).
2. **DNS/route via USB** (router DNS order was wrong: router IPv6 DNS fe80::1 came first):
   Gnirehtet reverse tethering — https://github.com/Genymobile/gnirehtet/releases/tag/v2.5.1 (gnirehtet-rust-win64-v2.5.1.zip, 0.9 MB)
   `set ADB=C:\LDPlayer\LDPlayer9\adb.exe` then `gnirehtet.exe run <serial> -d <PC_IP>` (accept the VPN prompt on the phone once).
3. **Patched APK** `client/apk/ros_phone_trustall_debugSigned.apk` = host-patched APK (.lan names) + network-security-config (user CAs) + `com.rosprivate.TrustAll` hook (smali in `client/smali_patch/`), signed with the debug key. Install: `adb install -r` (first time: `adb uninstall com.netease.chiji` deletes OBBs + Android/data -> re-push OBBs from the XAPK and `files/.../loginapp.pubkey`).
4. **CA on the phone**: install `server/certs/ca.crt` as *CA certificate* (Settings > Biometrics and security > Other security settings > Install from device storage). Verify with the phone browser: `https://unisdk.update.easebar.lan/` must open without a warning.
5. Server (`start.cmd`) — fixes made during this session:
   - HTTPS handshake moved into the worker thread (a stalled client used to block all HTTPS).
   - `/api/devices/init` reply now includes `device.id` (Guest login).
   - Lobby data at login: `onUpdateLuckyCarnivalData`, `gmsyncRedPoints`.

## Lobby data fixed (2026-11-18, verified on phone)
- Login sends `onUpdateLuckyCarnivalData`, `gmsyncRedPoints`, `onAccumulateChargeUpdate`, `syncMonthPayRebateSpecialAwardInfo` (awards={}, status=[0]*32) -> lobby startup errors gone.
- Athlete props `freeYuanbao` / `payYuanbao` (env ATHLETE_FREE_YUANBAO / ATHLETE_PAY_YUANBAO, default 50000 each) -> diamonds show 100000 in Supply/Store.

## Session stability (verified)
- Relog loop every 20-90 s was caused by the server heartbeat (REASON_CORRUPTED_PACKET "illegal wastage count"), not by the inactivity timer. HALL_HEARTBEAT=0 -> stable 4+ min in the lobby.
- UNLOCK_ALL=calls (6023 onAddDtsAppearanceItem) freezes the game; default off. Unlock needs a lighter method.
- The root ros_server.py may be edited by another agent (Antigravity); diff against this copy.

## Supply screens (2026-11-18)
- Looks/Vehicle/Firearms Supply read `onQueryAvailableSupplement({sid: {CURRENCY_ID:[..], BUY_TIMES_PRICE:[..], BUY_MULTIPLE_TIMES_PRICE:[..], CURRENT_DISCOUNT, IS_*, KIND, SORT_KEY}})`. Data comes from the client's own tables (`supplement_utils.getAvailableSupplementDictByTime()`, dumped via Frida on the emulator) -> `server/extract/supplement_info.json`; sent at login. Screens now open with no script errors.
- DRAW 1x/10x press still sends no recognizable message; session relogs (REASON_CORRUPTED_PACKET) interfere. Base-method msg ids: exposed idx -> msg via eff=57 formula is only partly confirmed (249 sub 0x8c = finishRetAct527TaskFromClient(INT32); 253 sub 0x56 = recordDtsResPath(STRING)).

## Known gaps
- Coins / tickets / stars wallets show 0 (currencyList ids not mapped yet).
- Depot items all locked (no owned appearance/items seeded), hero texture bluish (appearance lists empty).
- Star Supply shows "coming soon"; Supply `getSupplementData(None)` -> ExtraGiftParam error when opening UIMonthlySupplyPackage.
- DRAW 1x/10x buttons send nothing (Looks Supply); needs investigation (UIMonthlySupplyPackage/ExtraGiftParam error on open).
- START does nothing yet (no match request handling).
