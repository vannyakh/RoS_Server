# One agent at a time on LDPlayer and the gateway.
#   .\tools\ldplayer_lock.ps1 acquire -Owner lane3-match -Task "19.06 victory screen"
#   .\tools\ldplayer_lock.ps1 touch   -Owner lane3-match      # refresh during long runs
#   .\tools\ldplayer_lock.ps1 release -Owner lane3-match
#   .\tools\ldplayer_lock.ps1 status
# Exit 1 when someone else holds a fresh lock. A lock older than -StaleMinutes without a touch is free.
param(
    [Parameter(Mandatory = $true, Position = 0)][ValidateSet("acquire", "touch", "release", "status")][string]$Action,
    [string]$Owner = "",
    [string]$Task = "",
    [int]$StaleMinutes = 30
)

$lock = Join-Path (Split-Path $PSScriptRoot -Parent) "logs\LDPLAYER.lock"

function Read-Lock {
    if (-not (Test-Path $lock)) { return $null }
    try { return Get-Content $lock -Raw | ConvertFrom-Json } catch { return $null }
}

$cur = Read-Lock
$age = if ($cur) { ((Get-Date) - [datetime]$cur.touched).TotalMinutes } else { 0 }
$fresh = $cur -and $age -lt $StaleMinutes

switch ($Action) {
    "status" {
        if ($fresh) { "held by $($cur.owner) since $($cur.started) ($([int]$age) min since touch): $($cur.task)" }
        elseif ($cur) { "free (stale lock of $($cur.owner), $([int]$age) min old)" }
        else { "free" }
    }
    "acquire" {
        if (-not $Owner) { throw "-Owner is required" }
        if ($fresh -and $cur.owner -ne $Owner) {
            Write-Host "LDPlayer busy: $($cur.owner) since $($cur.started): $($cur.task)"
            exit 1
        }
        $now = (Get-Date).ToString("s")
        $started = if ($fresh) { $cur.started } else { $now }
        @{ owner = $Owner; task = $Task; started = $started; touched = $now } | ConvertTo-Json | Set-Content $lock -Encoding UTF8
        "acquired by $Owner"
    }
    "touch" {
        if (-not $fresh -or $cur.owner -ne $Owner) { Write-Host "not held by $Owner"; exit 1 }
        $cur.touched = (Get-Date).ToString("s")
        $cur | ConvertTo-Json | Set-Content $lock -Encoding UTF8
        "touched"
    }
    "release" {
        if ($cur -and $cur.owner -ne $Owner -and $fresh) { Write-Host "held by $($cur.owner), not $Owner"; exit 1 }
        if (Test-Path $lock) { Remove-Item -Force $lock }
        "released"
    }
}
