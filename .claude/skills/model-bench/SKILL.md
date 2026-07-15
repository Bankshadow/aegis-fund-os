# Model bench — prices & seats (July 2026)

Load before any routing or cost question. **Only file that may hardcode rates.**
Update here when labs change prices — never in ROUTING.md or agent code.

## Roster (indicative; verify before budgeting)

| Seat | Role here | Ballpark in/out per MTok |
|---|---|---|
| Claude Fable 5 | Advisor / planner / grader of goals | ~$10 / $50 |
| Claude Opus 4.8 | Fable fallback, hard subtasks | below Fable |
| Claude Sonnet 5 | Default driver (bulk) | best value while intro lasts |
| GPT-5.6 Sol | Terminal-heavy driver / cross review | ~$5 / $30 |
| GPT-5.6 Terra | Seat daily driver alternative | ~½ Sol |
| GPT-5.6 Luna | Mechanical / cheap | ~$1 / $6 |

## Facts that change builds

1. Cached input ~90% off both labs — stable system prefix, append-only history.
2. Fable safety refusal is success+fallback to Opus, not a hard error (~<5% sessions).
3. Availability is operational risk — every seat needs a logged fallback.
4. Cost = rate × turns-to-green; stronger@lower-effort often wins.
5. Batch overnight work when TASKS.md is deep (stacks with cache).

## This repo's split

- Fable: judgment grams (promote/kill, experiment design)
- Sonnet / Sol: bulk execution
- Gate script: final vote

See `ROUTING.md`.
