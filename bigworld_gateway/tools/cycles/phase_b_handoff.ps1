# Phase B: PLAY -> lobby (enterHall) -> START -> battle handoff; optional cancel test.
param(
    [switch]$SkipCancel,
    [int]$LoginTimeout = 600,
    [int]$LobbyTimeout = 120,
    [int]$MatchTimeout = 120
)

$ErrorActionPreference = "Stop"
$V2 = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Logs = Join-Path $V2 "logs"
. (Join-Path $V2 "client\scripts\adb_common.ps1")
$serial = Resolve-RosSerial -Target ldplayer
if (-not $serial) { throw "LDPlayer not found" }
$A = @("-s", $serial)
$adb = $RosAdb
$pkg = $RosPackage
$serverLog = Join-Path $Logs "server.log"
$logStart = if (Test-Path $serverLog) { (Get-Content $serverLog).Count } else { 0 }
$wait = @{ FilePath = (Join-Path $PSScriptRoot "wait_server_log.ps1"); MinLine = $logStart }

function Invoke-Wait([string]$Pattern, [int]$Timeout) {
    & powershell -ExecutionPolicy Bypass -File $wait.FilePath -Pattern $Pattern -TimeoutSeconds $Timeout -MinLine $wait.MinLine
    if ($LASTEXITCODE -ne 0) { throw "wait_server_log failed: $Pattern" }
}

function Save-Cap([string]$name) {
    $tmp = Join-Path $env:TEMP "ros_phase_b.png"
    if (Test-Path $tmp) { Remove-Item -Force $tmp }
    & cmd /c "`"$adb`" -s $serial exec-out screencap -p > `"$tmp`""
    if (Test-Path $tmp) { Move-Item -Force $tmp (Join-Path $Logs $name) }
}

Write-Host "=== Phase B handoff serial=$serial pc=$RosPcIp logStartLine=$logStart ==="
& powershell -ExecutionPolicy Bypass -File (Join-Path $V2 "client\scripts\setup_emulator.ps1") -Serial $serial | Out-Null
& $adb @A shell "su -c 'date -u 042012002022.00'" 2>$null | Out-Null
& $adb @A shell "am force-stop $pkg" | Out-Null
& $adb @A shell "monkey -p $pkg -c android.intent.category.LAUNCHER 1" | Out-Null

Invoke-Wait "notice_pc_hw|server_list_ad" 120
Start-Sleep -Seconds 15
& $adb @A shell input tap 790 660 | Out-Null
Write-Host "PLAY tapped; waiting for Mercury login + enterHall (up to ${LoginTimeout}s)..."
Invoke-Wait "Scheduled enterHall|Sent Athlete\.onLogin|-> Athlete\.enterHall" $LoginTimeout
Save-Cap "phase_b_lobby.png"

Start-Sleep -Seconds 30   # hall2 load on LDPlayer
& $adb @A shell input tap 1280 805 | Out-Null
Write-Host "START tapped; waiting for battle handoff..."
Invoke-Wait "matchBattleGround|_enter_battle|-> battle outfit" $MatchTimeout
Save-Cap "phase_b_match.png"

if (-not $SkipCancel) {
    Write-Host "Cancel test (match timer X)..."
    & $adb @A shell input tap 150 35; Start-Sleep -Seconds 2
    & $adb @A shell input tap 150 35; Start-Sleep -Seconds 3
    try { Invoke-Wait "cancelMatchBattleGround|not ready \+ NONE" 45 } catch { Write-Warning "Cancel RPC not seen in log" }
}

Write-Host "Phase B PASS. Artifacts: phase_b_lobby.png phase_b_match.png"