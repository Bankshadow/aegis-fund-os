/**
 * Research candidates for the Overview "measured honestly" board.
 *
 * Numbers are copied from docs/VALIDATION_LOG.md (and the precomputed AOT
 * walk-forward fixture). This is deliberately not a live leaderboard of wins —
 * every row that failed the declared gate stays FAIL with its drawdown visible
 * next to return, same doctrine as Minara's "Top strategies, measured honestly".
 *
 * No order path. No promotion path. Read-only research surface.
 */

export type ResearchVerdict = "FAIL" | "MECHANISM_ONLY" | "PASS";

export type ResearchCandidate = {
  id: string;
  name: string;
  universe: string;
  window: string;
  /** Headline return metric (mean OOS return % or CAGR %, as labeled). */
  returnPct: number;
  returnLabel: "mean return" | "CAGR";
  /** Worst / mean max drawdown as a positive percent magnitude. */
  maxDdPct: number;
  /** Project robust score when applicable (return − 2×maxDD); null if N/A. */
  robust: number | null;
  /** Vs buy-and-hold / index delta in percentage points when applicable. */
  vsBenchmarkPct: number | null;
  benchmarkLabel: string;
  sharpe: number | null;
  verdict: ResearchVerdict;
  /** One-line diagnosis — the "told me I was wrong" moment, not a sales pitch. */
  diagnosis: string;
  /** Deep-link into Walk-Forward Lab when the candidate is an AOT grid variant. */
  labVariant?: "baseline" | "trailing" | "exposure-cap";
  logRef: string;
};

export const RESEARCH_BOARD_TITLE = "Research candidates · measured honestly";

export const RESEARCH_BOARD_SUBTITLE =
  "Return and max drawdown sit side by side. Failures stay on the board. Gate verdict is a script, not a model opinion.";

export const RESEARCH_COLD_SHOWER =
  "A backtest is not a forecast. Positive in-sample or cycle-window numbers can reverse; concentrated drawdowns are real risk, not footnotes. Nothing here is a live order or investment advice.";

/**
 * Ordered newest-first so the operator sees the latest filtration first.
 * Keep FAIL rows; never cherry-pick winners for the Overview.
 */
export const RESEARCH_CANDIDATES: ResearchCandidate[] = [
  {
    id: "E33",
    name: "Screened Trend-Vote Basket",
    universe: "30 clean crypto (held-out)",
    window: "2018-08 → 2026-08",
    returnPct: 10.1,
    returnLabel: "CAGR",
    maxDdPct: 72.7,
    robust: null,
    vsBenchmarkPct: -11.2,
    benchmarkLabel: "eq-wt B&H CAGR 21.3%",
    sharpe: 0.45,
    verdict: "FAIL",
    diagnosis:
      "Screen is the cause and it is wrong: cut names with positive trend 54%; discarded names beat kept names at every horizon (90d +26.5% vs +16.3%).",
    logRef: "VALIDATION_LOG §E33",
  },
  {
    id: "E32-T6",
    name: "Donchian-55 2× on trend filter",
    universe: "BTC continuous · held-out ETH/SOL",
    window: "2018-08 → 2026-08",
    returnPct: 49.8,
    returnLabel: "CAGR",
    maxDdPct: 79.9,
    robust: null,
    vsBenchmarkPct: 16.0,
    benchmarkLabel: "BTC B&H CAGR 33.8% (in-sample)",
    sharpe: 0.9,
    verdict: "FAIL",
    diagnosis:
      "Home-run on BTC, then held-out kills it: ETH −13.7%/yr, SOL −61.9%/yr. Vol drag at 2× under-delivers ~42%/yr vs linear scaling.",
    logRef: "VALIDATION_LOG §E32",
  },
  {
    id: "E29",
    name: "AOT grid + trailing + exposure cap",
    universe: "AOT.BK daily · 18 OOS folds",
    window: "2005–2026 walk-forward",
    returnPct: 14.88,
    returnLabel: "mean return",
    maxDdPct: 13.52,
    robust: -12.17,
    vsBenchmarkPct: -8.28,
    benchmarkLabel: "buy-and-hold (mean alpha)",
    sharpe: null,
    verdict: "MECHANISM_ONLY",
    diagnosis:
      "Mean looks better (−19.91 → −12.17 robust) but decomposition fails: gains come from folds that stop trading (engaged 100% → 78%), not the mechanism.",
    labVariant: "exposure-cap",
    logRef: "VALIDATION_LOG §E29",
  },
  {
    id: "E28",
    name: "AOT grid + trailing re-anchor",
    universe: "AOT.BK daily · 18 OOS folds",
    window: "2005–2026 walk-forward",
    returnPct: 13.76,
    returnLabel: "mean return",
    maxDdPct: 16.84,
    robust: -19.91,
    vsBenchmarkPct: -9.4,
    benchmarkLabel: "buy-and-hold (mean alpha)",
    sharpe: null,
    verdict: "MECHANISM_ONLY",
    diagnosis:
      "Mechanism direction correct (engaged 83% → 100%, alpha −10.79 → −9.40) but gate still FAIL — paid for more engagement with worse drawdown.",
    labVariant: "trailing",
    logRef: "VALIDATION_LOG §E28",
  },
  {
    id: "E26",
    name: "AOT fixed grid (baseline)",
    universe: "AOT.BK daily · 18 OOS folds",
    window: "2005–2026 walk-forward",
    returnPct: 12.37,
    returnLabel: "mean return",
    maxDdPct: 15.17,
    robust: -17.97,
    vsBenchmarkPct: -10.79,
    benchmarkLabel: "buy-and-hold (mean alpha)",
    sharpe: null,
    verdict: "FAIL",
    diagnosis:
      "Cuts drawdown vs buy-and-hold but loses on return − 2×maxDD and mean alpha. Selling out then watching the trend is the structural failure mode.",
    labVariant: "baseline",
    logRef: "VALIDATION_LOG §E26",
  },
];

export function verdictTone(verdict: ResearchVerdict): "neg" | "warn" | "pos" {
  if (verdict === "PASS") return "pos";
  if (verdict === "MECHANISM_ONLY") return "warn";
  return "neg";
}

export function verdictLabel(verdict: ResearchVerdict): string {
  if (verdict === "PASS") return "PASS";
  if (verdict === "MECHANISM_ONLY") return "MECHANISM ONLY · GATE FAIL";
  return "FAIL";
}
