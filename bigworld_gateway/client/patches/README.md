# Client patches (APK mods)

Every change to the game APK is a **patch version**: one folder `vNNN_<date>_<name>/` with a `PATCH.md`
(built from, what changed, MD5 of the signed APK) and the patch inputs (smali, icons, scripts, logs).

**No game binaries in this repo.** The repo is public; the APK/OBB are NetEase files. `*.apk`, `*.obb`,
`uber-apk-signer.jar`, the JDK and `neox_rotor_key.txt` are gitignored. Share built APKs and the rotor key
through the team's private drive. Put the APK in its version folder as `game.apk` (ignored by git).

| Folder | What |
|---|---|
| `VERSIONS.md` | one line per version |
| `v001…v005/` | history of the builds so far |
| `new_patch.ps1` | register a signed build as the next version (writes PATCH.md + VERSIONS.md) |
| `install_patch.ps1` | install `vNNN/game.apk` on LDPlayer / phone, records it in `CURRENT.local.md` |
| `../patch_tools/` | NeoX npk/marshal tools, host patcher, URL scanner, signer script |
| `../apk_build/rewrite_hosts.py` | `.lan` → `*.vokdev.com` same-length rewrite (public build) |
| `../smali_patch/` | TrustAll smali + network_security_config (phone trusts the test CA) |

## Build a new patch

1. Get the original client: `RULES+OF+SURVIVAL_1.610637.617289_APKPure.xapk` (see `../apk/README.md`), unzip
   `com.netease.chiji.apk`. Or start from the latest `game.apk` on the private drive.
2. Decode: `java -jar apktool.jar d game.apk -o dec` (apktool 2.9+).
3. Make the change in `dec/` (hosts: `python -I ../apk_build/rewrite_hosts.py dec`; smali: copy from `../smali_patch/`).
4. Build: `java -jar apktool.jar b dec -o out_unsigned.apk`
5. Sign: `.\client\patch_tools\sign_apk.ps1 -Unsigned <dir>\out_unsigned.apk` → `<dir>\signed\`
6. Register: `.\client\patches\new_patch.ps1 -Apk <dir>\signed\out_unsigned-aligned-debugSigned.apk -Name my-change -From v005 -Changes "what changed"`
   Then copy the patch inputs (smali, images, script) into the new folder and commit the folder.
7. Install: `.\client\patches\install_patch.ps1 -Version v006 -Target ldplayer`
8. Upload `game.apk` to the private drive under the same version name.

Same input + same steps = same APK, so the MD5 in `PATCH.md` checks a teammate's rebuild.

## Script (NeoX) patches

`patch_tools/npk_decrypt.py` / `neox_marshal.py` / `patch_scripts.py` read `script.npk` (in the OBB) with the
build's rotor key in `patch_tools/neox_rotor_key.txt` (private, ask the team). Patched `.nxs` files load as loose
overrides; see `../../docs/CLIENT_DECOMPILE.md`.
