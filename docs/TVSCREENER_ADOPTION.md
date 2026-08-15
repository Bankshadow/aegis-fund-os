# tvscreener adoption boundary

Reviewed source: [`deepentropy/tvscreener`](https://github.com/deepentropy/tvscreener),
Apache-2.0, revision pinned in
[`tvscreener-source.lock.json`](../integrations/tvscreener-source.lock.json).

## What it is

An unofficial Python client for TradingView's public scanner and news-flow
endpoints. Six screeners (stock / forex / crypto / bond / futures / coin),
~13,000 typed fields, a fluent `select().where().get()` API returning pandas
DataFrames, `stream()` for repeated polling, and an MCP server exposing
`discover_fields` / `custom_query` / `get_top_movers` to an assistant.

Verified against the live endpoint from this machine on 2026-08-09: no API key,
no auth header, JSON in / JSON out, 150 rows per request by default.

## The one fact that decides everything else

**The scanner returns the present and only the present.** `get()` is a
snapshot; `stream()` is repeated snapshots. There is no historical, no
as-of-date, and no point-in-time retrieval anywhere in the package.

That single property is what separates the two halves of this document.

## Rejected — screening as a research or selection layer

Not adopted, and not to be adopted without a new pre-declared experiment:

1. **Backtesting on a screened universe.** A universe drawn from today's
   listings and applied to yesterday's bars is survivorship bias by
   construction. E31 already carries this as its stated residual bias. Measured
   here: `WAVES` — a real delisting on 2024-06-17 that sits in E31's 33-symbol
   panel — does **not** appear in today's Binance snapshot. Today's screener
   cannot reconstruct a past universe; it can only hide the names that died.

2. **Screening as an edge.** E33 measured what an asset screen costs on this
   book: the trend screen discarded 54% of the names whose trend was positive,
   and the discarded names beat the kept names at **every** horizon (90d +26.5%
   vs +16.3%). The recorded lesson was *"a state carries information" ≠ "past
   statistics of that state can select assets"*. A screener with a nicer API
   does not change that measurement. Wiring tvscreener in as a selection layer
   would re-run E33's failure with better ergonomics.

3. **13,000 fields against 324 recorded runs.** The Overfitting Lab measured
   in-sample selection at 3/18 = 16.7% OOS hit rate against a chance rate of
   exactly 16.7%, and E30 reproduced it on a different asset class (2/10 = 20%
   vs chance 1/5). Multiple-testing discipline in this repo is a counted number
   in `VALIDATION_LOG.md`. A 13,000-field search surface with no run accounting
   is the fastest available way to destroy it.

4. **`tvscreener` as a runtime dependency.** The package has no retries, no
   backoff, no caching, and no rate-limit handling; it raises on the first
   malformed response and pulls pandas for a payload this repo already parses
   with the stdlib (see `dynamic_grid/real_data.py`). It is also explicitly
   unofficial — *"not affiliated with, endorsed by, or connected to
   TradingView"* — so its endpoint contract can move without notice. It stays a
   **reference**, exactly like the Webull plugin.

5. **`news.py` in the deployed Worker.** The module hits
   `news-mediator.tradingview.com` unauthenticated and scrapes article bodies
   out of HTML. Its `related_symbols` field is genuinely tempting — per-symbol
   attribution is the defect class the news board already had to fix by hand
   (a mining pool's bankruptcy scored against BTC). But
   `docs/NEWS_RISK_DASHBOARDS.md` rests on six named public RSS newsrooms plus
   official Statuspage feeds, and swapping part of that for an unofficial
   scraper running on public Cloudflare infrastructure changes both the terms
   and the reliability story. Local evaluation only; not wired, not deployed.

## Adopted — the endpoint contract, for forward-only universe recording

`dynamic_grid/universe_snapshot.py` (stdlib only, ~200 lines) implements the
scanner POST contract directly and does one thing the library cannot: it makes
the snapshot's date load-bearing.

* A snapshot is written **append-only** to
  `data/universe/snapshots/{profile}/{YYYY-MM-DD}.json`, atomically, and a
  recorded date can never be overwritten. A rewritable universe file is not
  evidence of what the market looked like that day.
* `load_as_of(profile, date)` returns the newest snapshot recorded **on or
  before** `date`, and raises `NoPointInTimeUniverse` when none exists. Asking
  it for E31's start (2017-08-17) raises rather than quietly handing back the
  present.
* The filters and sort rule are stored inside every snapshot. A liquidity screen
  applied at time T is legitimate; the same screen applied with hindsight is
  not, and the only way to tell them apart a year from now is to have written
  the rule down next to the timestamp.

**What this buys us:** starting today, the archive accumulates the point-in-time
universe that Binance klines and the Yahoo chart endpoint cannot give us
retroactively — listing dates, delistings, and the composition of the market on
a given day. In twelve months E-series experiments starting after 2026-08-09
can be run on a universe that was actually knowable at the time. It fixes
nothing about E26–E33 and does not claim to.

### Second pass: what the first adoption left unused

The first pass took the transport and stopped. A re-audit of the parts of the
library that had not been opened — `field/` (1.13 MB of generated enums),
`filter.py`, `core/base.py`'s `symbols` handling — found two strengths that were
load-bearing and had been missed, and both are now in.

**1. Symbolsets — index constituents.** `core/base.py` supports
`symbols: {symbolset: [...]}`, which the first pass skipped entirely. Verified
live: `SYML:SET;SET50` returns exactly 50, `SYML:SET;SET100` exactly 100,
`SYML:SP;SPX` 503, `SYML:NASDAQ;NDX` 102. (`SETHD` and `sSET` return 0 — those
symbolset names do not exist, so they are not shipped.)

This matters far more than the filtered profiles, and for a specific reason:
**the membership rule is exogenous.** SET decides who is in SET50. We do not
choose it, cannot tune it, and cannot fit it to a backtest. E33's failure was a
screen *we* invented, selecting assets on their own past statistics — an index
constituent list is categorically not that, which is why it is the standard
universe definition in equity research. It is the one form of "screening" in
this library that survives our own evidence, and daily point-in-time
constituent history is precisely what cannot be reconstructed later.

Shipped as `set50` and `set100`, with **no filters of our own** — membership is
the definition, and a filter on top would be us quietly editing someone else's
universe. Pinned by a test. Cross-check on 2026-08-09: both are subsets of the
independently-derived 880-name `set-stocks` list, contain no NVDR (`.R`) lines,
and AOT is a SET50 member.

**2. The field catalogue — but from the endpoint, not the enums.** The library
ships ~1.13 MB of generated field classes. Do **not** vendor them: TradingView
publishes the same catalogue live at
`https://scanner.tradingview.com/{market}/metainfo` — 3,771 fields for
`thailand` and `america`, 3,258 for `crypto`, 3,126 for `forex`, 426 for
`futures`, each with a name and type. Always current, nothing to maintain.
Exposed as `--fields KEYWORD --market M`.

**And the finding that decided how far to trust it:** `Value.Traded` appears in
**no** market's metainfo, yet returns real numbers on `thailand` and nothing at
all on `crypto` — with HTTP 200 both times. So the catalogue is an *incomplete*
advertisement: validating columns against it would reject working ones. It is a
discovery aid, never an allowlist, and a test pins that nothing in the module
may reject a column for being absent from it.

The reliable check is therefore empirical, and it is now a guard. `fetch`
records `empty_columns` (fields that came back null for every row) and raises
`DeadSortColumn` when the **sort** column is among them. That combination was a
live hazard: ordering by a dead column leaves an arbitrary — though stable —
server-side order, so a truncated fetch records an arbitrary subset of the
universe while looking perfectly healthy. Both branches are tested against the
real contradiction: dead on `crypto` raises, alive on `thailand` does not.

### Feature-by-feature verdict

| tvscreener feature | Verdict | Reason |
| --- | --- | --- |
| Scanner POST contract | **adopted** | The transport; stdlib reimplementation. |
| `symbols` / symbolsets | **adopted** | Exogenous index universes; the one screen that survives E33. |
| `metainfo` field catalogue | **adopted, as discovery only** | Live endpoint beats 1.13 MB of vendored enums; proven incomplete, so never a gate. |
| Instrument-type filters | **adopted** | Excludes warrants and perpetuals; both traps measured. |
| Pagination / `range` | **adopted, improved** | Ours pauses between pages and reports truncation. |
| 13k generated field enums | rejected | Superseded by `metainfo`; a vendored megabyte that goes stale. |
| `filter.py` operator DSL (`FIELD > 100`) | rejected, for now | Genuinely nice ergonomics, ~40 lines to copy — but we have four profiles with static filters. A DSL layer to maintain for no measured benefit is the surface-building this project pivoted away from. Revisit when profiles are written per-experiment rather than per-market. |
| `presets.py` curated groupings | rejected as code, adopted as idea | Our `Profile` objects *are* presets, with the filters and the timestamp attached. |
| `beautify()` DataFrame styling | rejected | Cosmetic; the dashboards already do this in TSX. |
| `stream()` polling | rejected | A point-in-time archive wants one dated snapshot per day, not a live tape. |
| `ta/` recommendations ("Strong Buy") | rejected | A vendor signal is exactly the screen-as-edge that E33 refuted. |
| `news.py` | rejected for deployment | See above; local evaluation only. |
| MCP server | rejected | A 13k-field search surface with no run accounting, against 324 counted runs. |
| Retries / backoff / caching | nothing to adopt | The library has none; ours pauses and fails loudly. |

### Shipped profiles

| Profile | Market | Rows on 2026-08-09 | Why the filters |
| --- | --- | --- | --- |
| `set-stocks` | `thailand` | 880 of 880 | Unfiltered `thailand` returns **2,250** rows, and the top of a market-cap sort is derivative warrants: `NVDA01`, `NVDA19`, `NVDA03` all report the underlying's 179 trillion THB cap and outrank DELTA. `type == stock` + `is_primary` leaves 880 real primary listings, AOT among them. |
| `binance-spot-usdt` | `crypto` | 489 of 489 | Unfiltered `crypto` is **57,074** rows across every venue, mixing perpetuals (`.P` suffix) with spot. Perps carry funding, which E31 models explicitly, so mixed rows would be a modelling error. `exchange=BINANCE` + `currency=USDT` + `type=spot` leaves 489. Stablecoin pairs are deliberately **not** removed — the raw snapshot stays raw. |
| `set50` | `thailand` | 50 of 50 | Symbolset `SYML:SET;SET50`. Exogenous membership, no filters of ours. AOT is a member. |
| `set100` | `thailand` | 100 of 100 | Symbolset `SYML:SET;SET100`. |

Both traps are silent: a naive market-cap or volume sort returns plausible-looking
rows that are the wrong instrument. Both are pinned by tests.

### Commands

```bash
python -m dynamic_grid.universe_snapshot --list
python -m dynamic_grid.universe_snapshot --profile set50
python -m dynamic_grid.universe_snapshot --fields dividend_yield --market thailand
python -m unittest tests.test_universe_snapshot
```

Re-running on a date already recorded is a no-op and spends no request.

### Daily recording

The archive is only worth having if it does not have holes, and a missed day is
permanent — constituent history cannot be bought back later. So recording is a
scheduled task rather than a habit.

```bash
powershell -File automations/universe-snapshot/install-task.ps1
```

Registers `AegisUniverseSnapshot` for the current user: daily at 18:00 local,
no elevation, no stored password, no admin rights. 18:00 is after the SET close
at 16:30 ICT and still inside the same UTC date as the Thai trading day, so
`as_of` cannot land a day ahead of the market it describes. `-Time HH:MM`
changes the hour; `-Uninstall` removes it; re-running replaces the registration.

`run.ps1` calls `--all`, appends to `automations/universe-snapshot/logs/`
(git-ignored, rolled at 1 MB) and exits 0 only when every profile is recorded
for today. `StartWhenAvailable` is set deliberately: this is a laptop, and a
missed 18:00 must be caught up at the next boot instead of lost.

Three properties the task depends on, each pinned by a test:

* **A failing profile does not cost the others.** `record_all` reports per
  profile; one dead endpoint or one dead sort column still leaves the rest
  recorded.
* **A second run the same day spends nothing.** The archive is append-only, so
  a catch-up firing is a no-op that makes no request.
* **A network error is reported, not raised.** The task reports `failed` and
  exits 1; it does not write a partial snapshot.

The task writes snapshots into the working tree and **does not commit them** —
committing stays a decision you make, per the project's git rule.

**Not chosen: GitHub Actions.** The runtime watchdog precedent would fit, but
three things argue against it here: the module is not on the remote yet, the
archive has to land in the working tree where research reads it, and a daily
call to an unofficial endpoint from a cloud runner is far likelier to be blocked
than from a residential Thai IP. Revisit if the machine stops being the primary
research host.

## Design ideas worth borrowing, separately from the data

These are the parts of tvscreener that are good engineering regardless of the
data question, and they map onto the education product rather than research:

* **Typed fields with operator overloading** — `StockField.PRICE > 100`,
  `.between()`, `.isin()`, `.with_interval("240")`. Our panel code passes raw
  numpy columns around; a typed field layer over `crypto_leverage_e31.build_panel`
  would make the Walk-Forward Lab's mechanism comparisons readable.
* **Curated field presets** — `stock_valuation`, `stock_oscillators`, etc.
  Exactly the right shape for teaching: hand a student twelve named groups, not
  13,000 fields. This is the honest use of a big field catalogue.
* **`beautify()`** — TradingView-style conditional formatting on the DataFrame.
  The dashboards already do this in TSX; the CLI research output does not.

None of these require the dependency.

## Reopening conditions

Using a tvscreener-derived screen as a **selection** input requires, per
`docs/VALIDATION_LOG.md` discipline: a mechanism-level hypothesis declared
before the run, an E-number with criteria written first, judged on assets not
used to build the screen, with a control arm that switches the screen off —
the same shape as E33, which is the experiment that produced the evidence
against it.
