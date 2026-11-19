# Plan: run the game on the Note10+ (SM-N976N, not rooted) against the private server

## Status (2026-11-18)
- Phone <-> PC works over USB with Gnirehtet (`tools_dl/gnirehtet`, run with `-d 192.168.1.18`); firewall rule "RoS Private Harness" is in place.
- Game passes patching, shows login screen, server list "Private-Server".
- PLAY fails with "Slow connection" from the mpay login SDK: HTTPS to 192.168.1.18:443 is dropped.
  Likely cause: targetSdk=30 -> user-installed CAs are ignored; emulator works because its system store has the test CA (rooted).

## Goal
Make the app trust a user-installed CA (`server/certs/ca.crt`), without root.

## What already exists
- `decompile/patched/signed/ros_patched_unsigned-aligned-debugSigned.apk`: original APK with domains rewritten to `.lan` (hosts patch), debug-signed. JDK + `uber-apk-signer.jar` in `decompile/tools`.
- `decompile/xapk/com.netease.chiji.apk` (original) and both OBBs.
- NOT present: `apktool.jar` (needs download, ~23 MB, github.com/iBotPeaches/apktool releases).

## Steps
1. **Back up** from the phone to the PC (new folder, outside the repo): OBB dir `/sdcard/Android/obb/com.netease.chiji` (3.9 GB) and `/sdcard/Android/data/com.netease.chiji` (41 MB; holds `loginapp.pubkey`).
2. **Get apktool** (download, user approval needed) into `decompile/tools/`.
3. **Decode** the host-patched APK with apktool.
4. **Patch**: add `res/xml/network_security_config.xml` with `<certificates src="system"/>` + `<certificates src="user"/>`, and `android:networkSecurityConfig="@xml/network_security_config"` on `<application>`.
5. **Rebuild**, zipalign + sign with `uber-apk-signer` (debug key; same as the emulator build).
6. **Install on phone**: `adb uninstall com.netease.chiji` (signature changes), `adb install` patched APK, restore OBB + data folders from backup (or push `loginapp.pubkey` again via `adb_common.ps1`).
7. **User step on phone** (security setting, done by the user): Settings > Biometrics and security > Other security settings > Install from device storage > CA certificate > `ros_harness_ca.crt` (already in /sdcard/Download; re-push from `server/certs/ca.crt` if missing).
8. Start Gnirehtet relay, launch game, press PLAY, watch `server.log` for the login on port 25000.
9. If it works: copy changed files to `ros_server_v2/`.

## Risks / fallbacks
- Uninstall may delete OBB/data on Android 12 -> step 1 backup covers it.
- Game may have its own certificate pinning in native code (then only the emulator path works; keep using it).
- If the SDK calls are plain HTTP for some hosts and TLS for others, only TLS ones need the CA.
- Play Protect may warn about the debug-signed app: choose "Install anyway".
