# LDPlayer debug cycle: launch RoS, optional START tap, capture SCRIPT + Mercury logcat and screenshots.
# Requires: LDPlayer + adb, ros_server_v2/start.cmd already running.
param(
    [switch]$TapPlay,
    [switch]$TapStart,
    [switch]$RequireLobby,
    [switch]$ZoneTest,
    [int]$WaitMatchSeconds = 90,
    [int]$LobbyWaitSeconds = 120,
    [string]$Serial = "",
    [string]$Owner = "ld_debug_match"     # LDPlayer lock owner (tools/ldplayer_lock.ps1)
)

$ErrorActionPreference = "Stop"
$V2 = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$LockScript = Join-Path $V2 "tools\ldplayer_lock.ps1"
& $LockScript acquire -Owner $Owner -Task "ld_debug_match" | Out-Host
if ($LASTEXITCODE -eq 1) { throw "LDPlayer is locked by another agent; see tools\ldplayer_lock.ps1 status" }
trap { & $LockScript release -Owner $Owner | Out-Null; break }
$Root = Split-Path $V2 -Parent
$Logs = Join-Path $V2 "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

# Use v2 adb_common so ROS_PC_IP matches ros_server_v2/config.cmd (AGENTS one-IP rule).
. (Join-Path $V2 "client\scripts\adb_common.ps1")
$serial = if ($Serial) { $Serial } else { Resolve-RosSerial -Target ldplayer }
if (-not $serial) { throw "LDPlayer not found. Start LDPlayer9 first." }

$adb = $RosAdb
$pkg = $RosPackage
$A = @("-s", $serial)

Write-Host "=== ld_debug_match serial=$serial pc=$RosPcIp ==="

# Tap coordinates below are measured on a 1600x900 LDPlayer screen; scale them to the real size.
$size = (& $adb @A shell wm size) -join " "
$ScreenW, $ScreenH = 1600, 900
if ($size -match "(\d+)x(\d+)") { $ScreenW, $ScreenH = [int]$Matches[1], [int]$Matches[2] }
Write-Host "screen ${ScreenW}x${ScreenH}"
function Tap([int]$x, [int]$y, [string]$what) {
    $sx = [int]($x * $ScreenW / 1600); $sy = [int]($y * $ScreenH / 900)
    & $adb @A shell input tap $sx $sy | Out-Null
    Write-Host "Tapped $what ($sx,$sy)"
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $V2 "client\scripts\setup_emulator.ps1") -Serial $serial | Out-Host

& $adb @A shell "settings put global auto_time 0" | Out-Null
& $adb @A shell "su -c 'date -u 042012002022.00'" 2>$null | Out-Null

& $adb @A shell "am force-stop $pkg" | Out-Null
& $adb @A logcat -G 16M 2>$null | Out-Null
& $adb @A logcat -c | Out-Null
& $adb @A shell "monkey -p $pkg -c android.intent.category.LAUNCHER 1" | Out-Null

$serverLog = Join-Path $Logs "server.log"
$serverTail0 = ""
if (Test-Path $serverLog) { $serverTail0 = Get-Content $serverLog -Raw -ErrorAction SilentlyContinue }

Write-Host "Waiting for menu (notice fetch in server.log)..."
$menuOk = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 3
    if (-not (Test-Path $serverLog)) { continue }
    $tail = (Get-Content $serverLog -Tail 80 -ErrorAction SilentlyContinue) -join "`n"
    if ($tail -match "notice_pc_hw|server_list_ad") { $menuOk = $true; Write-Host "  menu HTTP seen after $($i * 3)s"; break }
}
function Save-AdbScreenshot([string]$outPath) {
    $tmp = Join-Path $env:TEMP "ros_ld_debug_cap.png"
    if (Test-Path $tmp) { Remove-Item -Force $tmp }
    & cmd /c "`"$adb`" -s $serial exec-out screencap -p > `"$tmp`""
    if (Test-Path $tmp) { Move-Item -Force $tmp $outPath }
}

if (-not $menuOk) { Write-Warning "server.log did not show notice/server_list yet (DNS or patch blocked?)." }

if ($TapPlay -or $TapStart) {
    Start-Sleep -Seconds 12
    # The Events/notice popup opens over the menu after login and swallows the PLAY tap.
    # Popup: dark header bar at the top right, light panel below. Menu: dark metal floor there.
    $probe = Join-Path $Logs "ld_debug_screenshot_title.png"
    Save-AdbScreenshot $probe
    if (Test-Path $probe) {
        Add-Type -AssemblyName System.Drawing
        $bmp = [System.Drawing.Bitmap]::FromFile($probe)
        $px = { param($x, $y) $bmp.GetPixel([int]($x * $bmp.Width / 1600), [int]($y * $bmp.Height / 900)).GetBrightness() }
        # measured: popup 0.92 / 0.93 / header 0.14; plain menu 0.58 / 0.67 / 0.02; splash all 1.0
        $popup = ((& $px 1300 700) -gt 0.8) -and ((& $px 700 780) -gt 0.8) -and ((& $px 1100 90) -lt 0.3)
        $bmp.Dispose()
        if ($popup) { Tap 1536 90 "notice popup close"; Start-Sleep -Seconds 3 }
    }
    Tap 790 655 "PLAY"
}

Write-Host "Waiting ${LobbyWaitSeconds}s for lobby (server enterHall / logcat hall)..."
$lobbyOk = $false
for ($i = 0; $i -lt [math]::Ceiling($LobbyWaitSeconds / 15); $i++) {
    Start-Sleep -Seconds 15
  if (Test-Path $serverLog) {
    $tail = (Get-Content $serverLog -Tail 120 -ErrorAction SilentlyContinue) -join "`n"
    if ($tail -match "enterHall|onEnterHallTeam|Scheduled enterHall") {
        $lobbyOk = $true; Write-Host "  gateway lobby after $($i * 15 + 15)s (server.log)"; break
    }
  }
    $buf = & $adb @A logcat -d 2>$null | Out-String
    if ($buf -match "hall2|hall\.scn|scene\\hall2") {
        $lobbyOk = $true; Write-Host "  lobby scene after $($i * 15 + 15)s (logcat)"; break
    }
}
if (-not $lobbyOk) {
    if ($RequireLobby) { throw "Lobby not confirmed (use -RequireLobby only when hall2/enterHall expected)." }
    Write-Warning "Lobby not confirmed; START tap may miss."
}

Save-AdbScreenshot (Join-Path $Logs "ld_debug_screenshot_menu.png")

$lineBefore = 0
if (Test-Path $serverLog) { $lineBefore = (Get-Content $serverLog).Count }

if ($TapStart) {
    Tap 1280 805 "START"     # same spot as match_cycle.sh
    Write-Host "Waiting ${WaitMatchSeconds}s for match..."
    Start-Sleep -Seconds 8
    Save-AdbScreenshot (Join-Path $Logs "ld_debug_screenshot_start.png")
    Start-Sleep -Seconds ($WaitMatchSeconds - 8)
    Save-AdbScreenshot (Join-Path $Logs "ld_debug_screenshot_match.png")
}

if ($ZoneTest) {
    $trigger = Join-Path $V2 "server\trigger_battle.txt"
    @(
        "zone 0.2 away"
    ) | Set-Content -Path $trigger -Encoding ASCII
    Write-Host "Wrote $trigger (zone 0.2 away); needs active match + client packets to consume triggers."
    Start-Sleep -Seconds 30
    Save-AdbScreenshot (Join-Path $Logs "ld_debug_screenshot_zone.png")
}

& $adb @A logcat -d -v time 2>$null |
    Select-String -Pattern "<SCRIPT>" |
    ForEach-Object { $_.Line.Substring(0, [Math]::Min(400, $_.Line.Length)) } |
    Set-Content (Join-Path $Logs "ld_debug_script.txt") -Encoding UTF8

& $adb @A logcat -d -v time 2>$null |
    Select-String -Pattern " M \(" |
    ForEach-Object { $_.Line.Substring(0, [Math]::Min(330, $_.Line.Length)) } |
    Set-Content (Join-Path $Logs "ld_debug_mercury.txt") -Encoding UTF8

if (Test-Path $serverLog) {
    Get-Content $serverLog -Tail 200 | Set-Content (Join-Path $Logs "ld_debug_server_tail.txt") -Encoding UTF8
}

$gamePid = (& $adb @A shell "pidof $pkg" 2>$null).Trim()
if ($gamePid) { Write-Host "Game running pid=$gamePid" } else { Write-Warning "Game process not running." }

Write-Host "Artifacts in $Logs (ld_debug_*)"
& $LockScript release -Owner $Owner | Out-Host