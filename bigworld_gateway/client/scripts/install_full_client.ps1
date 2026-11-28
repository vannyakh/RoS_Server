# One-command client setup for a phone or LDPlayer: patched APK, OBB, changed client files, login key.
#
# The changed art / UI / scripts are loose files inside the game folder, not part of any APK. Pack them
# once from a device that has them, then install the bundle on any other device.
#
#   Pack:     .\install_full_client.ps1 -Export -Serial <source> -Bundle <file.tar>
#   Install:  .\install_full_client.ps1 -Serial <target> -Apk <game.apk> -ObbDir <dir> -Bundle <file.tar>
#   Check:    add -CheckOnly to compare the device with the bundle without changing anything.
#
# Keep the bundle, APK and OBB outside this repository (publisher assets are never committed).
# A signature mismatch stops the install; -AllowUninstall lets it uninstall first, which ERASES the
# game's data on that device. The test CA must still be installed by hand on a phone, and a phone
# still needs to reach this PC (DNS or gnirehtet, see docs\PHONE_SETUP.md).
param(
    [string]$Serial = "",
    [string]$Bundle = "",
    [string]$Apk = "",
    [string]$ObbDir = "",
    [string]$BackupDir = "",
    [switch]$Export,
    [switch]$CheckOnly,
    [switch]$AllowUninstall
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
. "$PSScriptRoot\adb_common.ps1"

$GameDir = "/sdcard/Android/data/$RosPackage/files/netease/h45na"
$ObbRemote = "/sdcard/Android/obb/$RosPackage"
$Trees = "res Documents/res script"      # effect_cache is a per-GPU shader cache and is left out
$ListCmd = "cd $GameDir && find $Trees -type f ! -name loginapp.pubkey -exec md5sum {} +"

function Invoke-Adb {
    & $RosAdb -s $Serial @args
    if ($LASTEXITCODE -ne 0) { throw "adb failed ($LASTEXITCODE): $($args -join ' ')" }
}

function Get-DeviceText([string]$Command) {
    $out = & $RosAdb -s $Serial shell $Command
    return (($out | ForEach-Object { "$_".TrimEnd() }) -join "`n").Trim()
}

function Get-FileList {
    # Filtered here: Android 9's find does not let "*" cross "/" in -path.
    @((Get-DeviceText $ListCmd) -split "`n" | Where-Object { $_ -and $_ -notmatch "/effect_cache/" })
}

function Compare-Bundle([string]$Manifest) {
    $want = @(Get-Content -LiteralPath $Manifest -Encoding UTF8 | Where-Object { $_ })
    $have = @{}
    foreach ($line in Get-FileList) { $have[$line] = $true }
    $missing = @($want | Where-Object { -not $have.ContainsKey($_) })
    Write-Host ("[=] bundle files: {0}, missing or different on device: {1}" -f $want.Count, $missing.Count)
    $missing | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" }
    return $missing.Count
}

if (-not $Serial) { throw "Give -Serial. Devices: $((Get-RosDevices).Serial -join ', ')" }
if (-not $Bundle) { throw "Give -Bundle <file.tar>." }
if ((Get-DeviceText "echo ok") -ne "ok") { throw "Device $Serial does not answer adb." }

$Bundle = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Bundle)
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
if ($Bundle.StartsWith($repo + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "The bundle holds game assets; keep it outside the repository."
}
$Manifest = "$Bundle.md5"
$tmp = "/sdcard/Download/ros_client_bundle.tar"

if ($Export) {
    New-Item -ItemType Directory -Force (Split-Path $Bundle) | Out-Null
    Invoke-Adb shell "cd $GameDir && tar -cf $tmp --exclude=effect_cache $Trees"
    Invoke-Adb pull $tmp $Bundle
    Invoke-Adb shell "rm $tmp"
    $list = Get-FileList
    [IO.File]::WriteAllLines($Manifest, [string[]]$list, (New-Object Text.UTF8Encoding($false)))
    Write-Host "[+] $($list.Count) files -> $Bundle (list: $Manifest)"
    return
}

if (-not (Test-Path -LiteralPath $Bundle) -or -not (Test-Path -LiteralPath $Manifest)) {
    throw "Bundle or its .md5 list not found; create them with -Export."
}
if ($CheckOnly) {
    if ((Compare-Bundle $Manifest) -gt 0) { exit 1 }
    return
}
if (-not (Test-Path -LiteralPath $Apk)) { throw "Give -Apk <patched game.apk>." }
$obbs = @(Get-ChildItem -LiteralPath $ObbDir -Filter "*.obb")
if ($obbs.Count -eq 0) { throw "No *.obb files in -ObbDir." }

# 1. APK (only when the installed one differs)
$want = (Get-FileHash -LiteralPath $Apk -Algorithm MD5).Hash.ToLower()
$base = ((Get-DeviceText "pm path $RosPackage") -split "`n")[0] -replace "^package:", ""
$have = if ($base) { ((Get-DeviceText "md5sum $base") -split "\s+")[0] } else { "" }
if ($have -eq $want) {
    Write-Host "[=] APK already installed."
} else {
    Write-Host "[+] Installing APK..."
    & $RosAdb -s $Serial install -r $Apk
    if ($LASTEXITCODE -ne 0) {
        if (-not $AllowUninstall) {
            throw "APK install failed. If the signature differs, rerun with -AllowUninstall (erases game data)."
        }
        Invoke-Adb uninstall $RosPackage
        Invoke-Adb install $Apk
    }
}
Invoke-Adb shell "am force-stop $RosPackage"

# 2. OBB (only files whose size differs)
Invoke-Adb shell "mkdir -p $ObbRemote"
foreach ($obb in $obbs) {
    $size = Get-DeviceText "stat -c %s $ObbRemote/$($obb.Name) 2>/dev/null"
    if ($size -eq "$($obb.Length)") { Write-Host "[=] $($obb.Name) already there."; continue }
    Write-Host "[+] Copying $($obb.Name) ($([math]::Round($obb.Length / 1GB, 1)) GB)..."
    Invoke-Adb push $obb.FullName "$ObbRemote/$($obb.Name)"
}

# 3. The game's first start unpacks (and replaces) res/, so it must happen before the files are copied.
if (-not (Get-DeviceText "ls $GameDir/res/version 2>/dev/null")) {
    Write-Host "[+] First start of the game (accept any prompts on the device)..."
    Get-DeviceText "monkey -p $RosPackage -c android.intent.category.LAUNCHER 1" | Out-Null
    $deadline = (Get-Date).AddMinutes(4)
    while (-not (Get-DeviceText "ls $GameDir/res/version 2>/dev/null")) {
        if ((Get-Date) -gt $deadline) { throw "The game has not unpacked its files. Open it once, then rerun." }
        Start-Sleep -Seconds 5
    }
    Start-Sleep -Seconds 30
    Invoke-Adb shell "am force-stop $RosPackage"
}

# 4. Back up what is there, then copy the changed files
if (-not $BackupDir) { $BackupDir = Join-Path (Split-Path $Bundle) "backups" }
New-Item -ItemType Directory -Force $BackupDir | Out-Null
$backup = Join-Path $BackupDir ("{0}_{1}.tar" -f $Serial, (Get-Date -Format "yyyyMMdd_HHmmss"))
Invoke-Adb shell "mkdir -p $GameDir/res $GameDir/Documents/res $GameDir/script"
Invoke-Adb shell "cd $GameDir && tar -cf $tmp --exclude=effect_cache $Trees"
Invoke-Adb pull $tmp $backup
Write-Host "[+] Previous files saved to $backup"
Invoke-Adb push $Bundle $tmp
Invoke-Adb shell "cd $GameDir && tar -xf $tmp && rm $tmp"

# 5. Login key and test CA
Push-RosLoginPubKey -Serial $Serial
$ca = Join-Path $RosServerDir "certs\ca.crt"
if (Test-Path $ca) { Invoke-Adb push $ca "/sdcard/Download/ros_harness_ca.crt" }

if ((Compare-Bundle $Manifest) -gt 0) { throw "Some files did not arrive; see the list above." }
Write-Host "[+] Done. Open the game on $Serial." -ForegroundColor Green
