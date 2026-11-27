# Prepares the LDPlayer test emulator to talk to the local RoS mock servers.
#  - turns off Private DNS (DNS-over-TLS hides/bypasses DNS redirection)
#  - installs certs\<hash>.0 (local test CA) into the system trust store
#  - DNATs all emulator DNS (udp/53) to the PC's dns_server.py
# Run: powershell -ExecutionPolicy Bypass -File setup_emulator.ps1   (add -Undo to revert)
param([switch]$Undo, [switch]$SkipLobbyDate, [string]$Serial = "")   # -Serial emulator-5556 to pick one LDPlayer instance

. "$PSScriptRoot\adb_common.ps1"
$adb = $script:RosAdb
$PC_IP = $script:RosPcIp
$serial = Resolve-RosSerial -Target ldplayer -Serial $Serial
if (-not $serial) { throw "LDPlayer not found (emulator-5554). Start LDPlayer first." }
$adbArgs = @("-s", $serial)
$caFile = Get-ChildItem "$script:RosServerDir\certs\*.0" | Select-Object -First 1

& $adb @adbArgs root | Out-Null
& $adb @adbArgs wait-for-device
Write-Host "Emulator serial: $serial"
Start-Sleep 2

# Some LDPlayer builds keep adbd unprivileged after "adb root"; run root commands through su then.
$asRoot = ((& $adb @adbArgs shell "id -u") -join "").Trim() -eq "0"
function Invoke-RootShell([string]$cmd) {
    if ($asRoot) { & $adb @adbArgs shell $cmd } else { & $adb @adbArgs shell "su -c '$cmd'" }
}
if (-not $asRoot) { Write-Host "adb shell is not root; using su" }

if ($Undo) {
    Invoke-RootShell "iptables -t nat -D OUTPUT -p udp --dport 53 -j DNAT --to-destination ${PC_IP}:53 2>/dev/null; umount /system/etc/security/cacerts 2>/dev/null; settings put global private_dns_mode opportunistic"
    Invoke-RootShell "settings put global auto_time 1"
    "Reverted."
    exit
}

Invoke-RootShell "settings put global private_dns_mode off"
& $adb @adbArgs push $caFile.FullName "/data/local/tmp/$($caFile.Name)" | Out-Null
# /system is read-only (system-as-root), so overlay the cacerts dir with a tmpfs copy (lost on emulator reboot).
$n = $caFile.Name
Invoke-RootShell "D=/system/etc/security/cacerts; if [ ! -f `$D/$n ]; then mkdir -p /data/local/tmp/cacerts_bak; cp `$D/* /data/local/tmp/cacerts_bak/; mount -t tmpfs tmpfs `$D; cp /data/local/tmp/cacerts_bak/* `$D/; cp /data/local/tmp/$n `$D/; chmod 644 `$D/*; chcon u:object_r:system_file:s0 `$D/*; fi; ls -l `$D/$n"
Invoke-RootShell "iptables -t nat -C OUTPUT -p udp --dport 53 -j DNAT --to-destination ${PC_IP}:53 2>/dev/null || iptables -t nat -A OUTPUT -p udp --dport 53 -j DNAT --to-destination ${PC_IP}:53; iptables -t nat -L OUTPUT -n | grep 53"
$check = ((Invoke-RootShell "iptables -t nat -L OUTPUT -n | grep -c ${PC_IP}:53") -join "").Trim()
if ($check -eq "0" -or -not $check) { throw "DNS redirect was not applied (no root on the emulator?)" }

# RO-113: stale HTTP proxy breaks hall HTTPS before createHallTeam (Network Error 15).
Write-Host "Clearing emulator HTTP proxy (gateway PC_IP=$PC_IP)..."
Invoke-RootShell "settings put global http_proxy :0"
Invoke-RootShell "settings delete global http_proxy 2>/dev/null; settings delete global global_http_proxy_host 2>/dev/null; settings delete global global_http_proxy_port 2>/dev/null"
$proxyHost = ((Invoke-RootShell "settings get global http_proxy") -join "").Trim()
Write-Host "http_proxy after clear: $proxyHost"

# Install custom loginapp.pubkey so client encrypts login with our key
$pubKey = "$script:RosServerDir\server_keys\loginapp.pubkey"
if (Test-Path $pubKey) {
    Push-RosLoginPubKey -Serial $serial
}

# Supreme / monthly Supply (UIMonthlySupplyPackage) uses the Android clock, not server time.
# Match GAME_DATE in config.cmd (default 2022-04-20). See bigworld_gateway/docs/LOBBY_FINDINGS.md.
if (-not $SkipLobbyDate) {
    Write-Host "Setting emulator date to 2022-04-20 UTC (monthly Supply UI)..."
    Invoke-RootShell "settings put global auto_time 0"
    Invoke-RootShell "settings put global auto_time_zone 0"
    Invoke-RootShell "date -u 042012002022.00"
    $androidDate = ((Invoke-RootShell "date") -join "").Trim()
    Write-Host "Emulator date: $androidDate"
}

"Emulator configured."
