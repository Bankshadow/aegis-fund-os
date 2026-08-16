# Experiment number registry

**Claim a number here before writing `docs/E<N>_CRITERIA.md`.**

Two people (and an agent) have been allocating E-numbers independently. On
2026-08-12 that collided three times in one day: E36, E39 and E40 were each
claimed twice, one criteria document was destroyed by an overwrite, and one
runner (`e39_crowding.py`) was overwritten and had to be reconstructed from the
surviving engine. Nothing in the repo made a number look taken.

## Rules

1. **Claim first, write second.** Add a row below, then create the criteria doc.
2. **Never write to `docs/E<N>_*`, `e<N>_*.py`, or `docs/*-e<N>.json` for a
   number you have not claimed** — read the target first if it already exists.
3. **A criteria document is a pre-registration.** If one is lost, it cannot be
   rewritten after the results are known. Record it as lost and say so.
4. Untracked files have no undo. `git add` new experiment files early.

## Claimed

| N | Owner | Title | Criteria doc | Status |
|---|---|---|---|---|
| E30 | research | BTC directional logic | `docs/BTC_E30_CRITERIA.md` | FAIL |
| E31 | research | 2–3x/yr with leverage & shorts | `docs/CRYPTO_E31_CRITERIA.md` | FAIL |
| E32 | research | Leverage on a trend filter | `docs/E32_CRITERIA.md` | FAIL |
| E33 | research | Screened Trend-Vote Basket | `docs/E33_CRITERIA.md` | FAIL |
| E34 | research | BTC decision cadence | `docs/E34_CRITERIA.md` | FAIL |
| E35 | research | Golden pocket 0.618–0.66 | `docs/E35_CRITERIA.md` | FAIL |
| **E36** | **COLLIDED — resolved by labelling, 2026-08-16** | **(a) E36-volume**: Volume Patterns / Koroush · **(b) E36-emarsi**: EMA9/21 + loose RSI | `docs/E36_CRITERIA.md` holds **(b)** only. **(a)'s pre-registration was overwritten and is lost** — its log entry is a post-hoc summary and (a) is therefore **NOT a pre-registered experiment** | both FAIL |
| E37 | research | EMA9/21 + RSI 45/55, 5x, DSL exits | `docs/E37_CRITERIA.md` | ⚖️ |
| E38 | research | Spec identification: re-entry × halt | `docs/E38_CRITERIA.md` | FAIL |
| E39 | osmo | Crowded-long liquidation fade (S1) | `docs/E39_CRITERIA.md` | FAIL |
| E40 | **RETIRED** | never ran under this number — the trend-sizing study passed through it (E39 → E40 → E42) while the collision was being untangled | `docs/E40_CRITERIA.md` is a **superseded draft**, kept as the audit trail | — · **do not reuse** |
| E41 | osmo | DEX-vol relative-strength rotation (S2) | `docs/E41_CRITERIA.md` | FAIL — G2/G5a fail, G1/G3/G4 pass |
| E42 | research | Trend filter as size, not switch | `docs/E42_CRITERIA.md` | ⚖️ |
| E43 | osmo | Hyperliquid fees as BTC risk-on overlay (S3) | `docs/E43_CRITERIA.md` | FAIL |
| E44 | research | S003 reproduction: fade failed-breakout, SOL+LINK daily | `docs/E44_CRITERIA.md` | ✅ reproduced |
| E45 | research | S003 on full history: the years the designer never saw | `docs/E45_CRITERIA.md` | **MIXED** — Y1 passes (portR positive on never-seen data) but Y2 and Y4 fail |
| E46 | research | S003 tuning: one module at a time + selection value | `docs/E46_CRITERIA.md` | **NO_HIT** — T1/T2/T3 all fail; no module change transfers |
| E47 | research | Sizing overlays vs simply trading smaller, at matched DD | `docs/E47_CRITERIA.md` | done — U1/U2/U3 pass, but E48 shows the pass is a placebo effect |
| E48 | research | Adversarial attack on V4 equity-curve filter + promotion rule | `docs/E48_CRITERIA.md` | **NOT PROMOTED** — W1 placebo + W5 per-asset failed |
| E49 | research | Risk-per-trade table with drawdown as a bootstrap distribution | `docs/E49_CRITERIA.md` | done — 6%/trade ruins 19.4% of resampled paths; tolerance->risk table published |
| E50 | research | S003 stress: pessimistic intrabar x real trading costs | `docs/E50_CRITERIA.md` | done — Y2 pass, Y3 fail: edge real but thin |
| E51 | research | Universe expansion: cross-sectional out-of-sample on 31 unseen coins | `docs/E51_CRITERIA.md` | **FAIL — decisive** — 6/31 coins profitable; result flips sign across data vendors |
| E52 | research | TSMOM vs cross-sectional momentum, noise gate first | `docs/E52_CRITERIA.md` | M1-LS = challenger; E53: headline is a top-3-of-54 draw; E54: V1 was a tautology and the buy&hold benchmark was mislabelled (verdicts unchanged) |
| E53 | research | Walk-forward optimisation of M1-LS + placebo gate | `docs/E53_CRITERIA.md` | P2 FAIL — optimising loses to fixing; k=30 exposed as an isolated spike |
| E54 | research | Ten-specialist candidate bake-off under a max-statistic placebo ceiling | `docs/E54_CRITERIA.md` | **NO SURVIVORS** — 6/10 negative; also corrected two E52 harness defects |
| E55 | research | Closing the four gaps between `final_logic.md` and the code: portfolio S017 cooldown, 4% shared sizing, spec-faithful vol overlay, BE-bar rule | `docs/E55_CRITERIA.md` | **A FAIL** (S017 wins on one coin, flips under sl_first, 3/9 neighbours) · B: 4%/trade demands a 70% DD tolerance · **C FAIL** (loses to its own shuffled scales; clamp 4.0 never binds) · **D: the undocumented BE-bar rule is worth 28% of portR** |
| E56 | research | The unmeasured corner: pessimistic intrabar x literal BE-arming-bar x real costs, all three at once | `docs/E56_CRITERIA.md` | **EDGE REAL BUT THIN** (Z2/Z3 pass, Z4 fails exactly as E50 Y3 did) — and the premise was wrong: the BE axis is **nested inside** the intrabar axis, so the "third corner" never existed and E50 had already measured the floor |
| E57 | research | Implementation independence: S003 re-run on `backtrader` (GPL-3.0, isolated venv outside the repo, nothing vendored) | `docs/E57_CRITERIA.md` | **REPRODUCED** — +71.81 vs +72.81, 100% entry-date match, SOL agrees to 9 dp; the undocumented BE-arming rule turns out to be standard event-driven behaviour. R0 failed as written (mis-scoped over the ATR seed region — criteria defect, logged) |
| E58 | research | S003 vs buy & hold as paired distributions, at matched drawdown | `docs/E58_CRITERIA.md` | **NOT WORTH IT** — S2 60.0% (needs 90%), S2b 57.0% (needs 60%); W_COMMON 10.8%/10.4%. The realised 2x win at matched DD survives resampling only 57% of the time. Per the declared decision table the forward paper log is **cancelled** |
| E59 | research | BORA x S003: does real taker-buy order flow add edge over S003's price-only absorption proxy? BTCUSDT daily | `docs/E59_CRITERIA.md` | **TRADES LESS, DOES NOT READ FLOW** — BORA's own two tests (§22 control group, §25 incremental edge) both PASS while the filter loses to a duty-matched placebo (16/20 random seeds beat it). Baseline S003 on BTC daily is −58.14 R, so any filter that cuts trade count "improves" it |

**Next free number: E60.**

## Resolved inconsistencies

Both items from the 2026-08-12 numbering collision were closed on 2026-08-16.
They are kept here rather than deleted: how a ledger recovered from a mistake
is part of the evidence.

- **E40 / E41 — resolved.** They were never the same experiment; the registry
  row was simply stale. `docs/E41_CRITERIA.md` exists and is the Osmo S2
  pre-registration in its own right (its header records the move from E40).
  `docs/E40_CRITERIA.md` is an earlier draft of the **trend-sizing** study,
  which travelled E39 → E40 → E42 during the collision and finished as **E42**
  (`docs/E42_CRITERIA.md`, `docs/trend-sizing-e42.json`, log § E42). The
  artefacts E40_CRITERIA.md points at — `trend-sizing-e40.json` and a log § E40
  — were never produced. **E40 is retired: no experiment ran under it, and the
  number must never be reused.**

- **E36 — resolved by labelling, not by restoration.** The Koroush volume
  pre-registration was overwritten and no copy was found. Both E36 experiments
  keep their number and are now disambiguated as **E36-volume** (Koroush) and
  **E36-emarsi** (EMA9/21 + loose RSI). `docs/E36_CRITERIA.md` is the
  pre-registration for **E36-emarsi only**.

  > **E36-volume is not a pre-registered experiment.** Its log entry was
  > written after the results were known. It may be cited as a record of what
  > was run; it may **not** be cited as evidence that criteria were declared in
  > advance. Its FAIL verdict is unaffected — a negative result needs no
  > pre-registration to be believed, which is precisely the asymmetry this
  > ledger exists to preserve.

  If a personal copy of the original criteria ever turns up, restore it and
  reverse this label; until then the honest reading is the one above.
