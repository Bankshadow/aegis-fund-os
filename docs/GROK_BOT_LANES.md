# Grok Bot lanes — filtration of EXM7777 onto this repo

Source: [Machina (@EXM7777) status/2091905664704745583](https://x.com/EXM7777/status/2091905664704745583),
24 Aug 2026, *How to make money with Grok Bot*.

Same pattern as `docs/AGENT_STACK.md` (Avid) and `docs/LOOP_ENGINEERING.md`:
**adopt doctrine, reject the install that would violate this constitution.**

The article's useful claims:

- A bot is one persistent named agent with one job. One giant agent loses trust.
- All bots share one cloud computer; lanes are screens, **not** security boundaries.
- Memory is not an authoritative source. A markdown vault is.
- Start with a reverse-prompting extract, then read-and-prepare, then review,
  then one approved action, then a routine.
- Require-Approval always stops matching actions; when allow and approval
  both match, **approval wins**.
- "Done" without a check is worse than no bot.
- Get one lane stable before the next specialist.
- Money moves are never day-one automation.

The article's harmful-if-literal claims for **this** product:

- Ten revenue workflows (UGC ads, Smartlead outbound, LinkedIn, Meta spend,
  ghostwriting, SEO auditor, clipping factory) as the default roster.
- Higgsfield (or any ads surface) as the first thing to build.
- Computer-use against trading venues.

## Roster

Implemented in `agent/lanes.py`. Print it:

```
python agent/lanes.py
python agent/lanes.py --allowed
```

| lane_id | disposition | max autonomy | notes |
|---|---|---|---|
| education_evidence | KEEP | routine | Walk-Forward Lab, already shipping |
| research_loop | KEEP | human_review | Loop Engineering / ValidationGate |
| runtime_watchdog | KEEP | routine | read-only status poll |
| x_research | ADAPT | read_prepare | file vault notes; never auto-post |
| social_drafts | ADAPT | human_review | draft from evidence; human publishes |
| competitor_watch | ADAPT | read_prepare | claims vs VALIDATION_LOG |
| chief_of_staff | ADAPT | read_prepare | sourced readout; not a placement proxy |
| ugc_higgsfield | REJECT | — | sponsored ads factory |
| seo_aeo | REJECT | — | unused surface |
| email_outbound | REJECT | — | no CRM; send = human |
| linkedin_campaigns | REJECT | — | ads/forms |
| paid_media | REJECT | — | money move |
| video_clipping | REJECT | — | wait for student slice 5 |
| ghostwriting | REJECT | — | not a client shop |

Native stable set: `education_evidence`, `research_loop`, `runtime_watchdog`.
`activate()` allows **one** specialist on top of that set. A second specialist
while the first is still active fails closed.

## Vault

`docs/vault/` is the source of truth the article asked for (offer, ICP,
refuse, rulings, voice). `STATE.md` remains session memory.

## What this is not

- Not a trigger to install BUILD 7 scout/overnight/factory/swarm.
- Not a new education page. Slice 5 is still student feedback
  (`docs/HANDOFF_CURSOR.md` §0-NEW).
- Not computer-use against Binance, Webull, or any broker UI.
- Not Higgsfield, Smartlead, Typefully, Firecrawl, or DataForSEO as required
  connectors.

## Checks

```
python -m unittest tests.test_grok_bot_lanes
python gate/eval_gate.py
bash gate/verify.sh
```
