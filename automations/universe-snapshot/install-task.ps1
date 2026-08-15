# Register (or remove) the daily universe-snapshot Windows Scheduled Task.
#
# Runs as the current user, no elevation, no stored password, no admin rights.
# Default 18:00 local — after the SET close at 16:30 ICT, and still the same UTC
# date as the Thai trading day, so `as_of` cannot land a day ahead.
#
#   powershell -File automations/universe-snapshot/install-task.ps1
#   powershell -File automations/universe-snapshot/install-task.ps1 -Time 19:30
#   powershell -File automations/universe-snapshot/install-task.ps1 -Uninstall
#
# Idempotent: re-running replaces the existing registration.

param(
    [string]$Time = "18:00",
    [string]$TaskName = "AegisUniverseSnapshot",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$Runner = Join-Path $PSScriptRoot "run.ps1"
if (-not (Test-Path $Runner)) { throw "runner not found: $Runner" }

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($Uninstall) {
    if ($Existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "removed scheduled task '$TaskName'"
    } else {
        Write-Host "no scheduled task named '$TaskName'"
    }
    exit 0
}

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Runner`""

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

# StartWhenAvailable is the important one: this machine is a laptop, and a
# missed 18:00 must be caught up on the next boot rather than lost. A skipped
# day is a permanent hole in the archive - constituent history cannot be
# re-bought later.
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

if ($Existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal `
    -Description "Daily point-in-time universe snapshot (read-only public TradingView scanner). No order path." | Out-Null

$Task = Get-ScheduledTask -TaskName $TaskName
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "registered '$TaskName' - state $($Task.State), daily at $Time, next run $($Info.NextRunTime)"
