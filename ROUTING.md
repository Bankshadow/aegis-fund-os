# ROUTING.md — Model + Effort Policy

Single source of truth for both Claude Code and Codex/Cursor sessions.
Prices live only in `.claude/skills/model-bench/SKILL.md` — never hardcode rates here.

## Three principles (Avid / Evidence Ladder)

1. **Route at boundaries. Effort before model.** Mid-session model swaps burn ~90% cache discount.
2. **Nothing grades its own homework.** Writer ≠ advisor ≠ reviewer; final vote is `gate/verify.*`.
3. **Done is an environment fact** — passing suite, ticked task, gate exit 0 — never self-report.

## Seats for this repo

| Lane | Model | When |
|---|---|---|
| Driver (bulk) | `claude-sonnet-5` or `gpt-5.6-sol` | Code, demos, data plumbing, routine analysis |
| Advisor (grams) | `claude-fable-5` | Risk/return judgment, experiment design, promote/kill calls |
| Fallback | `claude-opus-4-8` | Fable safety refusal / hard architecture |
| Terminal-heavy | GPT-5.6 Sol (native Codex) | Long shell loops, CI plumbing |
| Mechanical | Luna / Haiku-class | Classify, format, cheap verify drafts |
| Final vote | bash/ps1 gate | Deterministic only |

## Decision order (cheapest first)

1. **Free check** — is this a known smoke / lint / unittest? → no model, run the command.
2. **Scored guess** — count difficulty markers (`why`, `debug`, `race`, `overfit`, `promote`, `regime`, `walk-forward`, multi-file, prior fail).  
   - 0–1 → cheap driver  
   - 2 → mid (Sonnet / Sol)  
   - ≥3 → frontier advisor in the loop (Fable consult), still driven by cheap executor
3. **Paid experiment** — only if BUILD-2 eval traffic shows ≥~5× capability-per-dollar gap; else delete the router and keep one seat.

Router is **guilty until proven** on this repo's evals (`gate/eval_gate.py`).

## Effort dial

- Default **high** for research judgment; **medium** for bulk typing.
- **Max** = depth (one chain). **Ultra** = width (fan-out). Not the same axis.
- Fast mode off unless you measured the seat-window burn.
- Subagents inherit parent seat+effort — pin them lower in frontmatter / prompts.

## Advisor inversion (BUILD 5)

Cheap driver owns the loop. Fable is consulted only when stuck protocol fires
(see `.claude/skills/stuck-protocol/SKILL.md`). Cap: **3 consults / task**.

```
python agent/executor_advisor.py "โจทย์..."
```

## Cross-vendor review (BUILD 6)

Meaningful diffs: review from the **other** lineage when available
(`/codex:review` adversarial on load-bearing strategy/risk changes).
Verdict file > chat praise.

## Fan-outs (BUILD 7) — install only when triggered

| Fan-out | Install when |
|---|---|
| Scout swarm | Research/archaeology > 30 min/day |
| Overnight burner | `loop/TASKS.md` has ≥10 small verifiable items |
| Plan split | Planning tokens dominate the bill |
| Factory SQLite gate | >1 writer session/day or multi-day review cycles |

Do not install speculatively.

## Graph contracts (BUILD 7.5) — scaffold only

Harness diamonds live in `agent/graph_contracts.py` + `agent/graph_ops.py`.
They validate findings, reduce with code, and route review severity. They do
**not** spawn subagents and do **not** touch L3 placement. Use them when a
task needs an explicit fan-out → reduce → synthesize shape; keep BUILD 7
swarms deferred until the triggers above fire.

## Watch weekly

- **Cheap-tier share** of ticks (target: majority of traffic on Sonnet/Sol/Luna)
- Gate pass rate and BLOCKED reasons
- Advisor consult count vs task completions
