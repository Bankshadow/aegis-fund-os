# Deterministic heartbeat loop (Windows).
# Exit map: 0 = done/quiet, 2 = circuit breaker / blocked, 3 = budget.
# Caps turn a runaway agent into a bounded lesson.

param(
    [double]$BudgetUsd = 2.0,
    [int]$MaxIters = 3,
    [string]$Driver = "manual"  # manual | note — wire CLI when ready
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Log = Join-Path $Root "loop\progress.log"
$Tasks = Join-Path $Root "loop\TASKS.md"
if (-not (Test-Path $Log)) { New-Item -ItemType File -Path $Log | Out-Null }

function Write-ProgressLine([string]$msg) {
    $line = "{0:u} {1}" -f (Get-Date).ToUniversalTime(), $msg
    Add-Content -Path $Log -Value $line
    Write-Host $line
}

$spent = 0.0
for ($i = 1; $i -le $MaxIters; $i++) {
    if ($spent -ge $BudgetUsd) {
        Write-ProgressLine "BUDGET spent=$spent cap=$BudgetUsd"
        exit 3
    }

    $content = Get-Content $Tasks -Raw
    if ($content -notmatch '- \[ \] ') {
        Write-ProgressLine "QUIET no unticked tasks"
        exit 0
    }

    Write-ProgressLine "TICK $i/$MaxIters driver=$Driver — read loop/PROMPT.md; one task only"
    Write-Host @"

=== HAND-RUN TICK $i ===
1. Open loop/PROMPT.md and loop/TASKS.md
2. Do the first unticked task only
3. Run its check command
4. Tick the box on success; append a note here if BLOCKED
5. Re-run this script or exit

Press Enter when this tick is finished (or Ctrl+C to abort)...
"@
    [void](Read-Host)

    # Re-check gate after human/agent tick — cheap fact, not opinion
    & powershell -File (Join-Path $Root "gate\verify.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-ProgressLine "BLOCKED gate failed after tick $i"
        exit 2
    }

    # Estimate: manual ticks cost $0 against API; reserve slot for future CLI cost parse
    $spent += 0.0
    Write-ProgressLine "OK tick=$i spent=$spent"
}

Write-ProgressLine "BUDGET max_iters=$MaxIters"
exit 3
