# Loop backlog — tiny, verifiable tasks only

Format: `- [ ] <title> | check: <command>`

- [x] Confirm ship gate is green | check: powershell -File gate/verify.ps1
- [x] Run fast demo smoke | check: python run_demo.py --fast
- [x] E24 dual short_cfg experiment + log | check: python dual_short_cfg_demo.py
- [x] E25 conservative dual experiment + log | check: python dual_conservative_demo.py
- [x] Add fail-closed Loop Engineering experiment contract | check: python -m unittest tests.test_loop_engineering
- [x] Add append-only JSONL experiment memory with code/data hashes | check: python -m unittest tests.test_loop_memory
- [x] Add one-contract research runner with immutable result output | check: python -m unittest tests.test_loop_runner
- [x] Add drift monitor that can open research tasks but cannot change parameters | check: python -m unittest tests.test_loop_drift
- [x] Export read-only experiment lineage snapshot for Aegis | check: python -m unittest tests.test_loop_snapshot
- [x] Add server-only Aegis reader for Loop lineage snapshot | check: pnpm --dir fund-command-center-local test
- [x] Bind read-only Loop lineage to Aegis Strategy Lab UI | check: pnpm --dir fund-command-center-local build
- [x] Add independent paper-review decision ledger | check: python -m unittest tests.test_loop_review
- [x] Project paper-review decisions into Loop snapshot and Aegis | check: python -m unittest tests.test_loop_snapshot
- [x] Add Loop CLI for verified snapshot export | check: python -m unittest tests.test_loop_cli
