#!/usr/bin/env bash
# Deterministic ship gate — final vote. No model opinions.
# Exit 0 = green. Non-zero = BLOCKED.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== GATE: strategy framework unit tests ==="
python -m unittest tests.test_strategy_framework -v

echo "=== GATE: fund ops unit tests (if present) ==="
python -m unittest tests.test_fund_ops tests.test_fund_mvp_weeks_2_to_8 -v 2>/dev/null || \
  python -m unittest discover -s tests -p 'test_fund*.py' -v

echo "=== GATE: eval seatbelt (offline) ==="
python gate/eval_gate.py

echo "=== GATE: SHIP ==="
exit 0
