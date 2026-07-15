# Deterministic ship gate — final vote. No model opinions.
# Exit 0 = green. Non-zero = BLOCKED.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== GATE: strategy framework unit tests ==="
python -m unittest tests.test_strategy_framework -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: fund ops unit tests ==="
python -m unittest discover -s tests -p "test_fund*.py" -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: eval seatbelt (offline) ==="
python gate/eval_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: SHIP ==="
exit 0
