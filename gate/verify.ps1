# Deterministic ship gate — final vote. No model opinions.
# Exit 0 = green. Non-zero = BLOCKED.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== GATE: strategy framework unit tests ==="
python -m unittest tests.test_strategy_framework -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: agent graph contracts (L2, no execution) ==="
python -m unittest tests.test_agent_graph -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: reflect cannot write laws, criteria or the gate ==="
python -m unittest tests.test_reflect -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: universe snapshots are point-in-time and append-only ==="
python -m unittest tests.test_universe_snapshot -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: egress allowlist and untrusted-content guard ==="
python -m unittest tests.test_egress_policy -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: S003 engine invariants (E44) ==="
python -m unittest tests.test_strat_trap -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# H1: with the cooldown off, the portfolio driver must reproduce run_symbol
# trade for trade. If that breaks, every number logged from E44 onward stops
# being comparable to anything measured after it.
Write-Host "=== GATE: portfolio driver == run_symbol, and S017 semantics (E55) ==="
python -m unittest tests.test_portfolio_s017 -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: fund ops unit tests ==="
python -m unittest discover -s tests -p "test_fund*.py" -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: eval seatbelt (offline) ==="
python gate/eval_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== GATE: SHIP ==="
exit 0
