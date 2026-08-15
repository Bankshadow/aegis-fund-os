# S003 — implementable spec, corrected against evidence (2026-08-16)

Supersedes `final_logic.md`. Paste the whole file as a prompt; it is written to
be implemented without asking a follow-up question, and to be **checkable** —
§10 gives the numbers a correct implementation must hit.

---

## 0. Read this before implementing

This is the **best-evidenced** version of S003, not a recommended trading
system. Fifteen pre-registered experiments (`docs/VALIDATION_LOG.md` E44–E58)
concluded:

- The edge is **real**: positive on data the designer never saw, positive under
  pessimistic fills and real costs, positive on both assets, and reproduced by
  an independent backtest engine to nine decimals on SOL.
- The edge is **not worth trading over simply holding**. Sized to buy & hold's
  drawdown, S003 beats it on the realised path but wins only **57%** of 500
  paired bootstrap resamples, under the 60% declared in advance (E58).
- What it actually is: a **drawdown instrument, not a return instrument**. At
  1% risk over 2022–2026 it made **+30.5%** with a **21.4%** max drawdown,
  against buy & hold's **+49.0%** at **74.1%**.

Everything the original spec layered on top — the portfolio cooldown, the
volatility overlay, 4%-of-equity sizing — was tested and rejected. §8 lists
each with the reason.

**Research artifact. No live orders. Do not size this from these numbers.**

---

## 1. Universe, timeframe, warm-up

- **Assets**: `SOL-USD`, `LINK-USD`. Independent entries; one open position per
  asset at a time.
- **Timeframe**: **1D** only. Do not transfer to 4H, BTC or ETH without a new
  study — E51 found the edge does not generalise (6 of 31 unseen coins
  profitable) and **flips sign across data vendors**.
- **Warm-up**: no signal may fire before bar index **201** (0-based). Bars
  0–200 exist only to season the ATR.
- **Data hygiene**: drop trailing bars that fail `low <= open <= high` and
  `low <= close <= high`, from the end inward, before anything else.

## 2. Indicators

**Wilder ATR(14)**, seeded so that index `i` uses bars `0..i` only:

```
TR[0]  = high[0] - low[0]
TR[i]  = max(high[i]-low[i], |high[i]-close[i-1]|, |low[i]-close[i-1]|)
ATR[13] = mean(TR[0..13])
ATR[i]  = (ATR[i-1] * 13 + TR[i]) / 14
```

ATR is NaN before index 13. A standard library ATR that starts one bar later
converges to within `1e-7` by bar 201, so either seeding is acceptable (E57 R0).

## 3. Bar type versus the prior bar

```
if   H <= H1 and L >= L1:  "1"    # inside
elif H >  H1 and L <  L1:  "3"    # outside
elif H >  H1 and L >= L1:  "2U"
elif L <  L1 and H <= H1:  "2D"
else:                      "1"
```

Only `2U` and `2D` produce signals. Bar 0 has no type.

*(The original spec listed two further `elif` branches after `2D`. They are
unreachable — the outside case catches `H>H1 and L<L1` first. Harmless; omitted
here.)*

## 4. Entry

Enter at the **close of the signal bar**.

| Bar type | Extra condition | Side |
|---|---|---|
| `2U` | `close < open` (red) | **SHORT** |
| `2D` | `close > open` (green) | **LONG** |

Skip if `|close - open| == 0` (doji). Skip if that asset already holds a
position. No regime filter, no volume gate, no higher-timeframe filter — E46
found no module change transfers out of sample.

## 5. Stop, R, targets

`SL_BUFFER = 0.25`, `MIN_STOP_ATR = 0.5`, `MAX_RISK_ATR = 3.0`, `band = ATR[i]`

**LONG**
```
stop = min(low - 0.25*band, close - 0.5*band)
R    = close - stop
```

**SHORT**
```
stop = max(high + 0.25*band, close + 0.5*band)
R    = stop - close
```

Skip the trade if `band` is NaN or `<= 0`, or if `R <= 0`, or if `R > 3.0*band`.

```
TP2 = entry ± 2R      # arms break-even
TP3 = entry ± 3R      # exit
```

Full size, no scale-out. `TP1 = entry ± 1R` exists in the original spec but has
**no effect on P&L** — there is no partial exit and no stop change at 1R. Omit
it or keep it as a marker; it changes nothing.

## 6. Trade management — read §6.3 carefully

### 6.1 The entry bar is never managed
Evaluation starts on the bar **after** entry. Structurally the stop sits at
least `0.25*ATR` beyond the signal bar's extreme, so this cannot bind, but
implement it explicitly.

### 6.2 Break-even
On any later bar whose range touches **TP2**, move the stop to **entry**. Once
armed it stays armed. A stop-out at that level books **BE_SL** (≈ 0 R gross).

### 6.3 The arming bar — the rule the original spec omitted

> **On the bar that arms break-even, the position does not stop out.** The stop
> check for that bar is skipped entirely — both the original stop and the new
> break-even stop. The break-even stop becomes live from the **next** bar.

This is worth **27.5% of total portR** (E55 D). It is not a rounding detail.

Two things make it defensible rather than convenient: an event-driven
backtester on daily bars produces it automatically, because the strategy
callback runs after the bar closes and cannot move a stop mid-bar (E57 R5); and
the literal alternative requires intra-bar path information that daily bars do
not carry. But **it is an assumption**, so §10 gives its cost so any report can
carry the error bar.

### 6.4 Same-bar TP3 and stop
Optimistic model: if one bar touches both TP3 and the live stop, book **TP3**.

Note this can only ever be TP3 against the **break-even** stop, never the
original one: TP2 lies between entry and TP3, so any bar reaching TP3 has
already armed break-even on that same bar. Under `be_rule = after_tp2` the
original stop can never race TP3.

### 6.5 Exits
`TP3`, `SL`, `BE_SL`, or `EOD` (mark the last bar's close if still open).

### 6.6 Fees
0.05% per side, 0.10% round trip, charged in R:

```
fee_R = 2 * 0.0005 * entry / R
pnl_R = (exit - entry) * side / R - fee_R
```

Both legs are charged on the **entry** price. Charging each leg on its own
notional instead changes total portR by **0.0225 R over 339 trades** (E57 R6) —
measured, immaterial, keep the simpler form for comparability.

## 7. Position sizing

**Risk 1% of current equity per trade.** Size so that
`|entry - stop| * size = 0.01 * equity`. Risk is fixed at entry; P&L is booked
at exit. Positions on the two assets may overlap.

E49 bootstrapped drawdown as a distribution rather than a single path:

| risk/trade | realised maxDD | **p90 maxDD** | paths ruined |
|---|---|---|---|
| 1% | 18.0% | 23.4% | 0% |
| 2% | 33.1% | 42.4% | 0% |
| 4% | 56.3% | 70.0% | 1.8% |
| 6% | 72.1% | 86.0% | **19.4%** |

Above 2% the p90 drawdown exceeds what almost anyone holds through.

## 8. Explicitly excluded, with the reason

| Excluded | Why |
|---|---|
| Portfolio cooldown (pause 2 signals after 4 losses) | E55 A — wins on LINK only, worst fold doubles, **flips sign** under the pessimistic intrabar model, beats baseline in only 3 of 9 neighbouring (streak, skip) cells |
| Volatility-target sizing overlay | E55 C — loses to its own scale factors shuffled onto the wrong trades; the spec's clamp ceiling never binds (realised scale 0.60–1.64) |
| Equity-curve filter (halve size below equity MA) | E48 — loses to a random-halving placebo at the same duty cycle |
| 4% of shared equity | E55 B — demands ~70% drawdown tolerance |
| Any parameter tuning | E46 NO_HIT, E53 FIX_THE_PARAMETERS — selecting parameters loses to fixing them |
| More assets | E51 — 6 of 31 profitable, sign flips across vendors |
| Regime / volume / trend filters, grid, martingale | never survived their own pre-registered criteria |

## 9. Ambiguities the original spec left open — resolved

1. **Within one bar, manage positions before taking entries.** An asset that
   closes a position on bar `i` may take a new signal on bar `i`.
2. **Order closes by exit date, then by symbol A→Z** when two close the same day.
3. A signal blocked because the asset already holds a position is **not** a
   skipped signal for any counting purpose.
4. `tp_first` / `sl_first` name the same-bar tie-break, but under §6.2 the
   tie-break can only apply to the break-even stop (see §6.4). Practically,
   `sl_first` means "the arming bar **can** stop out at break-even" — it is the
   pessimistic mirror of §6.3.
5. **Warm-up is 201 bars, counted per asset**, not from a shared calendar.

## 10. Acceptance tests — an implementation is correct when it reproduces these

Data: `SOL-USD` 2020-04-10 → 2026-08-11 (**2315** bars after tail-drop),
`LINK-USD` 2017-11-09 → 2026-08-12 (**3199** bars). Fees 0.05%/side.

| # | Configuration | Trades | portR |
|---|---|---|---|
| A1 | spec as written above | **339** | **+72.81** |
| A2 | A1, per asset | — | SOL **+34.10** · LINK **+38.71** |
| A3 | A1 restricted to entries before 2023-08-12 | **209** | **+41.12** |
| A4 | §6.3 removed (arming bar **can** stop out) | **342** | **+52.76** |
| A5 | pessimistic tie-break (`sl_first`) | **342** | **+43.76** |
| A6 | A5 per asset | — | SOL **+25.09** · LINK **+18.67** |

Also expected: exit-reason mix for A1 is exactly 95 TP3 / 207 SL / 35 BE_SL /
2 EOD. Full-history portR reaches zero at about **0.467%/side** under A5.

If A1 lands between +43 and +73 but not on +72.81, the difference is almost
certainly §6.3 or the tie-break, not the entry logic — A1 and A4 share 100% of
entry dates.

## 11. What to report, always

- **portR as the interval `[+43.76, +72.81] R`**, never one end. The lower
  bound is §6.3 removed and fills assumed pessimistic; the upper is the spec as
  written. The truth is inside.
- Drawdown as a **distribution** (p90), not the single realised path.
- The comparison against **buy & hold at the same drawdown**, as a win rate over
  resampled histories — which is the test S003 fails.

---

*Sources: `docs/VALIDATION_LOG.md` (E44–E58), `docs/E5*_CRITERIA.md`,
`docs/CASE_STUDY_S003.md`. Reference implementation:
`dynamic_grid/strat_trap.py`, pinned by `tests/test_strat_trap.py` and
`tests/test_portfolio_s017.py`, enforced by `gate/verify.ps1`.*
