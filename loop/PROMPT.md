# One task per tick. Fresh context. Repo is memory.

## Rules

1. Read `loop/TASKS.md`. Pick the **first** unticked `- [ ]` item only.
2. For a strategy experiment, validate its `ExperimentContract` before running.
3. Do that one task. Do not start a second.
4. Run its check command. If exit ≠ 0, fix once; if still failing, mark BLOCKED and stop.
5. On success: tick the item `- [x]`, append one line to `loop/progress.log`, commit if the task says so.
6. Stop. Exit the harness. Caps: iterations and dollars — both enforced by `ralph.ps1`.

## Stops (every branch ends here)

- DONE — check passed, task ticked
- BLOCKED — check failed after one repair attempt; human needed
- BUDGET — dollar or iteration cap hit
- QUIET — no unticked tasks

## Never

- Never edit tests to pass
- Never lower ValidationGate criteria
- Never live-order
- Never consult Fable more than 3 times for one task (use stuck protocol)
- Never let the loop change production/paper parameters or promote itself to live
