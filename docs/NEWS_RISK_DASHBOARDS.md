# News Risk Dashboards

Three boards the operator opens every morning, grouped under **Daily Monitor**
in the Fund OS sidebar:

| # | Board | Route | Question it answers |
| - | ----- | ----- | ------------------- |
| 1 | Portfolio & NAV | `/portfolio` | What do we hold and what is it worth? |
| 2 | Exchange News Risk | `/news-exchanges` | Is any venue holding our assets in trouble? |
| 3 | Held Asset News | `/news-assets` | Is any position we hold in trouble? |
| + | Market Pulse | `/news-market` | What is the market loud about today? (supplementary) |

Read-only monitoring. No order, cancel, sizing, or transfer path exists in any of
this code, and no score is a recommendation to trade.

## Data provenance

- **News: live, public RSS, no API key.** Six newsrooms plus two venue
  Statuspage history feeds (`src/lib/news-risk.ts` → `NEWS_SOURCES`).
- **Holdings: the prototype's paper/testnet book** (`ACCOUNTS`, `POSITIONS` in
  `src/lib/demo-data.ts`), not live custody. Every board states this inline.
- Feeds are fetched independently with a 6s timeout and cached 10 minutes per
  isolate. A dead feed is **reported as failed**, never silently treated as
  "no news" — a board that shows CALM because the network died is worse than one
  that says the source is down. A snapshot is only cached if ≥1 feed succeeded.

### Which venues get a row

A venue appears on the exchange board if it is **ranked** (top 10), **watched**,
**held**, or **in the news**. The last two conditions matter: filtering on rank
alone silently hid every unranked venue, so Bitkub could be the top story on
Market Pulse while having no row on the risk board at all.

`watch: true` marks an operator-tracked venue — always shown, even at zero
articles, because for a venue you run bots on "nothing happened" is the answer
you came for. **Pionex** is watched (it is this project's grid-bot venue).

### Feeds deliberately not configured

- **Pionex** — `pionex.statuspage.io` was never configured and still serves
  Statuspage's stock *"This is an example incident"* placeholder; the Pionex blog
  feed is self-published marketing. Neither is evidence about the venue, and
  piping either in would put synthetic or promotional content behind a real
  badge. Pionex is covered through the independent newsrooms instead. Revisit if
  it starts publishing real incidents.

## Scoring contract

Deterministic keyword rules, no LLM. Same headline in, same score out — so the
badge behind every escalation is reproducible and unit-testable, per the
project's "Done = a passing check, never a model opinion" law.

1. **Headline only.** Summaries are never scored or used for entity attribution.
   Live data showed a feed summary name-dropping half the market, which
   attributed a mining pool's bankruptcy to Bitcoin and spread one story's
   signals across five unrelated venues.
2. **Rules** (`IMPACT_RULES`) carry a weight in `[-3, +2]`. `-3` is reserved for
   custody-threatening events (hack, withdrawal halt, insolvency, depeg), which
   are flagged `severe`. Per-article score is clamped to ±4.
3. **Guards** cancel inverted matches — "keeps hackers out", "resumes
   withdrawals", "drops the case", "restored its peg".
4. **Digests** ("Morning Minute:", "Week Ahead:", "Weekly Recap") score zero:
   a multi-topic roundup's signals belong to no particular venue or asset.
5. **Narrow scope** — a title naming one token `(NIGHT)` or one region's clients
   keeps its direction but loses severity and is capped at ±1 per signal.
6. **Recency**: 48-hour half-life. Future-dated items (scheduled maintenance and
   delistings, common on Statuspage) are capped at half weight and grow toward
   it as the date approaches, instead of scoring as breaking news. Undated items
   are treated as one half-life old.
7. **Repetition damping**: within one entity, repeated hits of the same signal
   contribute `1, 1/2, 1/3, …`. Four routine token delistings in a week are one
   operational pattern, not four independent threats.
8. **Bands come from negative pressure alone.** Good news never nets out bad — a
   proof-of-reserves post published the same week as a withdrawal halt does not
   make the halt less true. `CRITICAL` needs a fresh severe event *and* ≥2.5
   pressure; `ELEVATED` needs either; `WATCH` ≥1; otherwise `CALM`.

## Known limitations

- Entity attribution is bag-of-words on the headline. "Poolin, once one of
  **Bitcoin**'s biggest mining pools, files for bankruptcy" is scored against
  BTC. Repetition damping limits the damage; it does not eliminate it.
- Rank ordering of the top 10 is hand-maintained data, not fetched.
- Cluster detection for Market Pulse uses title-token Jaccard ≥ 0.5, so two
  outlets wording the same story very differently stay separate.
- Coverage is English-language crypto media plus two Statuspage feeds. An asset
  with zero articles means **no coverage**, not good news, and the asset board
  says so.

## Checks

```
cd fund-command-center-local && node --test test/news-risk.test.mjs
```
