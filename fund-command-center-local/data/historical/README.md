# Historical OHLCV fixtures

`AOT.BK_daily_2025-2026.csv` contains daily OHLCV for Airports of Thailand
(SET: AOT, Yahoo Finance symbol `AOT.BK`) retrieved on 2026-07-21 from the
public Yahoo Finance chart endpoint:

https://query1.finance.yahoo.com/v8/finance/chart/AOT.BK?period1=1735689600&period2=1784592000&interval=1d&events=div%2Csplits

`AOT.BK_daily_2005-2026.csv` is the long-history fixture used by walk-forward
validation: 5,273 daily bars, 2005-01-04 to 2026-07-20, retrieved 2026-07-22
from the same endpoint with `period1=1104537600`. No bar was dropped for missing
OHLC. Prefer this file for any out-of-sample work; the 2025-2026 file is only
long enough for smoke and regression checks. Note that AOT traded near 5 THB in
2005 and near 64 THB in 2026, so a grid range must be derived per walk-forward
fold from in-sample bars only — a range spanning the whole file is lookahead.
See `docs/AOT_VALIDATION_CRITERIA.md`.

One source defect was repaired in that file, and only one: the 2023-08-08 bar
arrived as `o=70.75 h=71 l=70.25 c=70`, whose low sits one tick above the close,
which `validateMarketBars` correctly rejects as impossible. Its low was clamped
to the close (`l=70`); open, high, close, adjusted close and volume are
untouched, and no other bar in the 5,273 was altered. Note that
`analyzeMarketData` does not flag this class of defect — it counts non-positive
prices, not OHLC ordering — so run `validateMarketBars` over any new fixture
before trusting it.

The files are research fixtures for the local paper backtest. Prices are in THB;
timestamps are UTC and volume is shares. `adjustedClose` is the adjusted series
reported by the source. Verify licensing, corporate actions, timezone and latest
rows before using this data for any investment decision.

If the public endpoint is unavailable, use the UI's three-seed Synthetic test
for wiring/regression checks only. Synthetic output is not market evidence.
