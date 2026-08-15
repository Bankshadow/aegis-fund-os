---
name: agent-build-loop
description: >-
  Run builds as prompt → plan → execute → check → fix with a human owning plan
  and check. Use when starting a multi-step build, chaining models on a large
  codebase/doc, adding automation/watchdog approval gates, or when the user
  mentions build loop, human-in-the-loop, compress-then-execute, or
  mikenevermiss-style AI building. Do not use for model seat selection alone
  (that is model-router / ROUTING.md) or for ship verification alone (ship-gate).
---

# Agent build loop (repo-mapped)

Source idea: five-step AI build loop + model chain + failure patterns
([mikenevermiss](https://x.com/mikenevermiss/status/2080532258960597249)).
Maps onto **this** Grid Trading / Fund OS stack. Not a vibe-coding or
website-builder tutorial.

## Core reframe

- Chatting ≠ building. The loop only counts when the agent **touches** the
  environment (files, terminal, browser, declared check) and a human checks the
  **real** result.
- Human job = **plan** + **check**. Agent job = execute + propose fix.
- Done = environment fact (`gate/verify.*`, declared check, `ValidationGate`) —
  never "the model said it worked."

## Never (constitution)

- Never live-order or touch third-party capital
- Never let an agent mutate live/prod data without an explicit human approval step
- Never treat subscription chat plans as covering separate API / automation bills
- Never skip `gate/verify.*` or edit tests to pass
- Never pick a one-shot builder/tool before the finished need is clear
  (DB, Worker, D1, broker adapter, paper-only, etc.)

## Five-step loop

| Step | Owner | What "good" looks like here |
|---|---|---|
| 1 Prompt | Human | Outcome + constraints in plain language; criteria before run |
| 2 Plan | Human glances | Steps visible for multi-file / migrate / deploy work; effort before model (`ROUTING.md`) |
| 3 Execute | Agent | Real edits, real commands — not a lecture |
| 4 Check | Human + gate | Live page / test output / gate exit / ValidationGate — not model self-report |
| 5 Fix | Agent | Re-enter from the failed check; do not widen scope |

Skip plan glance only for trivial single-file edits. Never skip check.

## Seats (do not duplicate ROUTING.md)

Use `model-router` / `ROUTING.md` for which seat. This skill only adds **when to chain**:

| Job | Prefer | Why |
|---|---|---|
| Long, correctness-heavy build | Claude Sonnet / Opus / Fable advisor | Stays on thread; judgment grams |
| Bulk / multi-app terminal | GPT-5.6 Sol | Shell + cross-tool loops |
| Huge corpus first pass | Cheap wide-context reader (then hand off) | Summarize before spending frontier budget |
| Mechanical repeats | Luna / Haiku-class | Classify, format, cheap drafts |

Prices and bench truth live in `.claude/skills/model-bench/SKILL.md` — do not
trust vendor scorecards alone.

## Compress → execute (section 6 pattern)

When input is a large legacy tree, long transcript, or multi-doc dump:

1. **Reader pass** (cheap / wide context): produce a short map — modules,
   invariants, risky surfaces, open questions. Cap to a few thousand words.
2. **Executor pass** (driver seat): work from that map + live files; write,
   test, fix.
3. **Check**: human + `gate/verify.ps1` (or declared check). Advisor consult
   only for promote/kill / risk judgment (≤3/task).

Do not burn the expensive seat reading throwaway bulk. Do not let the summary
replace reading the files that will actually change.

## Automation / approval (section 5 pattern → this repo)

Prefer in-repo, token-gated, read-only paths over ad-hoc n8n for Fund OS:

- Runtime status: `/api/automation/runtime-status` + GitHub watchdog
  (`.github/workflows/runtime-watchdog.yml`) — halt/fail issues only; no
  order/cancel/transfer path.
- Cron / reconcile: dry-loop opt-in, human before prod mutate.
- Any workflow that publishes or spends: **Wait / approve** before live side
  effects (same idea as n8n Wait-for-Slack-approve).

n8n/Zapier tutorials from the source article are optional operator tooling —
not the default agent stack here.

## Failure checklist (before "done")

1. Credits / budget — mid-build burn expected on large one-shots; size scope first.
2. Separate bills — Claude/ChatGPT sub ≠ Anthropic/OpenAI API key for automation.
3. Zero human check on live data — forbidden; add approval or stay paper/sandbox.
4. Vendor bench claims — confirm with `gate/eval_gate.py` / this repo's traffic.
5. Tool before need — Fund OS is Workers + D1 + existing grid runtime; do not
   re-platform onto Bolt/v0/etc. for a one-file fix.

## Out of scope for this skill

- Pottery-site / Claude Design / Lovable walkthroughs (general web builders)
- Replacing `ship-gate`, `stuck-protocol`, or `model-router`
- Quant promote/kill → use `quant-research-pipeline`
- Capital / layer weights → use `quant-portfolio-allocation`

## Invoke

```
Use agent-build-loop: plan this change, then execute, then I check via gate.
```

Or when drowning in context:

```
Use agent-build-loop compress→execute on <path or dump>, then ship-gate.
```
