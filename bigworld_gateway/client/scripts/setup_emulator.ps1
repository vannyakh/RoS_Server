# Prepares the LDPlayer test emulator to talk to the local RoS mock servers.
#  - turns off Private DNS (DNS-over-TLS hides/bypasses DNS redirection)
#  - installs certs\<hash>.0 (local test CA) into the system trust store
#  - DNATs all emulator DNS (udp/53) to the PC's dns_server.py
# Run: powershell -ExecutionPolicy Bypass -File setup_emulator.ps1   (add -Undo to revert)
param([switch]$Undo, [string]$Serial = "")   # -Serial emulator-5556 to pick one LDPlayer instance

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

# Install custom loginapp.pubkey so client encrypts login with our key
$pubKey = "$script:RosServerDir\server_keys\loginapp.pubkey"
if (Test-Path $pubKey) {
    Push-RosLoginPubKey -Serial $serial
}
"Emulator configured."
