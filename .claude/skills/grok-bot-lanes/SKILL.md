# Grok Bot lanes

Filtrate [EXM7777 / Machina, 2026-08-24](https://x.com/EXM7777/status/2091905664704745583)
("How to make money with Grok Bot") onto **this** stack. Do not install the
article's ten revenue bots.

## Adopt

1. **One bot, one job.** A lane owns a repeatable outcome, not a category of questions.
2. **Vault > memory.** Read `docs/vault/` plus `STATE.md` / `VALIDATION_LOG.md`. Memory is compost.
3. **Read-and-prepare first.** Then human review. Then one approved action. Then a routine.
4. **Approval wins over allow.** Fail closed **before** the action. Approval does not undo completed work.
5. **Verify before done.** `gate/verify.*` or a declared `loop/TASKS.md` check. Self-report is not done.
6. **One specialist at a time.** Native lanes may already be running. Do not open a second specialist until the first is stable.
7. **Money never on day one** — and live orders / spend / send never in this repo.

## Reject (hard)

| Article workflow | Why |
|---|---|
| AI UGC / Higgsfield | Sponsored ads factory. Not this product. |
| SEO / AEO auditor | Speculative unused surface. Slice 5 is student feedback. |
| Email outbound / Smartlead | No CRM. Sending would be a money/attention move. |
| LinkedIn campaigns | Ads/forms/UTMs. Not this product. |
| Paid media reallocation | Capital move. Constitution. |
| Clipping / long-form video | Unused until students ask. |
| Ghostwriting for clients | This repo teaches from its own ledger. |
| 10-bot swarm on day one | BUILD 7 fan-outs stay deferred (`ROUTING.md`). |
| Lanes as security boundaries | Shared computer = separate screens, not isolation. |

## This product's lanes

KEEP (already shipping): `education_evidence`, `research_loop`, `runtime_watchdog`.

ADAPT (read/draft only): `x_research`, `social_drafts`, `competitor_watch`, `chief_of_staff`.

Code: `python agent/lanes.py` and `python -m unittest tests.test_grok_bot_lanes`.

## Reverse prompting (once)

Do not start by writing ten prompts. The vault **is** the extract of this
business. If a new session needs context, point at `docs/vault/` then
`docs/HANDOFF_CURSOR.md`. Do not duplicate the vault into bot memory.

## Map of Grok Bot knobs → this repo

| Knob | Here |
|---|---|
| description | `AGENTS.md`, `CLAUDE.md`, this skill |
| conversation | current task / `loop/TASKS.md` |
| memory | `STATE.md` (not source of truth) |
| connectors | existing read-only adapters only |
| computer use | never for exchange/broker UIs |
| skills | `.claude/skills/` |
| routines | `loop/ralph.ps1`, read-only watchdog workflow |
| approvals | this registry + ValidationGate + maker/checker |

Not a BUILD 7 install. Scout/overnight/factory/swarm still need ROUTING.md triggers.
