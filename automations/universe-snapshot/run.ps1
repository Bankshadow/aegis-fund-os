# Daily point-in-time universe snapshot.
#
# Records every profile in `dynamic_grid/universe_snapshot.py` for today and
# appends the outcome to a log. Read-only against a public endpoint: there is no
# exchange, broker, order, cancel, transfer or withdrawal path in this file, and
# it writes nothing outside `data/universe/snapshots/` and its own log.
#
# Re-running on a date already recorded is a no-op and spends no request, so the
# task is safe to fire more than once a day (catch-up runs included).
#
# Exit 0 = every profile is recorded for today. Exit 1 = at least one failed.

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogDir = Join-Path $PSScriptRoot "logs"
$Log = Join-Path $LogDir "universe-snapshot.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# Keep one rolled copy so an unattended daily task cannot grow a log forever.
if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 1MB)) {
    Move-Item $Log "$Log.1" -Force
}

$Stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
Set-Location $Root

$Output = & python -m dynamic_grid.universe_snapshot --all 2>&1
$Code = $LASTEXITCODE

$Lines = @("[$Stamp] exit=$Code") + ($Output | ForEach-Object { "    $_" })
Add-Content -Path $Log -Value $Lines -Encoding utf8
$Output | ForEach-Object { Write-Host $_ }

exit $Code
