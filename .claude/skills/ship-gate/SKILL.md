# Ship gate

Before claiming done, merge, or promote a strategy change:

```powershell
powershell -File gate/verify.ps1
```

or

```bash
bash gate/verify.sh
```

Exit 0 = SHIP. Non-zero = BLOCKED — fix, do not edit tests to pass, do not lower ValidationGate.

`gate/eval_gate.py` is the seatbelt for routing/prompt/constitution edits (deterministic only).
