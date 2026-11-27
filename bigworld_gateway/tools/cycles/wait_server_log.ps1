# Poll server.log for a regex until timeout. Only scans lines after -MinLine (avoids stale matches).
param(
    [Parameter(Mandatory)] [string]$Pattern,
    [int]$TimeoutSeconds = 300,
    [int]$PollSeconds = 5,
    [string]$LogPath = "",
    [int]$MinLine = 0
)
$V2 = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$LogPath = if ($LogPath) { $LogPath } else { Join-Path $V2 "logs\server.log" }
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-Path $LogPath) {
        $lines = Get-Content $LogPath -ErrorAction SilentlyContinue
        if ($MinLine -gt 0 -and $lines.Count -gt $MinLine) {
            $lines = $lines[$MinLine..($lines.Count - 1)]
        }
        $tail = $lines -join "`n"
        if ($tail -match $Pattern) {
            Write-Host "MATCH $Pattern"
            exit 0
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
Write-Error "Timeout waiting for $Pattern in $LogPath (after line $MinLine)"
exit 1