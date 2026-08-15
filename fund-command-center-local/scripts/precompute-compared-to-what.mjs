/**
 * Precompute the "compared to what / counted how many times" teaching slice.
 *
 * Every number on that page is read here out of the committed research output —
 * `docs/stvb-e33-diag.json`, `docs/rvol-ep9m-diag.json`, `docs/golden-pocket-e35.json`
 * — and never typed into the page by hand. This is the same invariant the rest of
 * the lab already has: a teaching page that can drift from the research it cites is
 * worse than no page at all, because it teaches with authority it has not earned.
 *
 * If a research file moves or changes shape this script fails loudly at build time
 * rather than shipping a page full of stale numbers.
 *
 *   node scripts/precompute-compared-to-what.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.join(here, "..", "..", "docs");
const OUT_DIR = path.join(here, "..", "src", "generated");
const OUT = path.join(OUT_DIR, "compared-to-what-data.json");

function read(name) {
  const file = path.join(DOCS, name);
  if (!fs.existsSync(file)) {
    throw new Error(`missing research output: ${file} — run the experiment first`);
  }
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function need(value, what) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    throw new Error(`could not read ${what} from the research output`);
  }
  return value;
}

// --- Exhibit A: E33 --------------------------------------------------------
// The screen was built to keep the names with a positive trend. Measured against
// the names it threw away, it kept the worse half at every horizon.
const e33 = read("stvb-e33-diag.json");
const horizons = ["30", "90", "180"].map((h) => {
  const row = need(e33.screen_discrimination[h], `E33 screen_discrimination[${h}]`);
  return {
    days: Number(h),
    keptMean: need(row.kept_mean, "kept_mean"),
    droppedMean: need(row.dropped_mean, "dropped_mean"),
    nKept: need(row.n_kept, "n_kept"),
    nDropped: need(row.n_dropped, "n_dropped"),
    screenWasRight: row.right === true,
  };
});

// --- Exhibit B: the RVOL / EP9M diagnostic ---------------------------------
// Same signal, same data. The only thing that changed is whether one rally is
// counted once or three times.
const rvol = read("rvol-ep9m-diag.json").d2_ep_signal;
const counting = Object.entries(rvol.horizons).map(([h, row]) => ({
  days: Number(h),
  clusteredMean: need(row.signal_mean, "signal_mean"),
  clusteredPercentile: need(row.percentile_vs_random, "percentile_vs_random"),
  episodeMean: need(row.episode_mean, "episode_mean"),
  episodePercentile: need(row.episode_percentile, "episode_percentile"),
  baseMean: need(row.base_mean, "base_mean"),
  episodeWinRate: need(row.episode_win_rate, "episode_win_rate"),
  baseWinRate: need(row.base_win_rate, "base_win_rate"),
}));

// --- Exhibit C: E35 --------------------------------------------------------
const e35 = read("golden-pocket-e35.json");
const primary = e35.config.primary;
const primaryZones = need(
  e35.btc.by_lookback[String(primary.lookback)],
  "E35 primary lookback block",
);
const horizonKey = String(primary.horizon);
const zones = Object.entries(primaryZones).map(([id, entry]) => ({
  id,
  n: entry.n,
  mean: need(entry[horizonKey].mean, `${id} mean`),
  percentile: need(entry[horizonKey].percentile, `${id} percentile`),
  isClaim: id === primary.zone,
  isControl: id === primary.control,
}));

// Every percentile the experiment produced, so "none crossed the line" is a
// computed fact on the page rather than a claim in prose.
const allPercentiles = [];
for (const zonesAtL of Object.values(e35.btc.by_lookback)) {
  for (const entry of Object.values(zonesAtL)) {
    for (const [key, row] of Object.entries(entry)) {
      if (key !== "n" && row && typeof row.percentile === "number") {
        allPercentiles.push(row.percentile);
      }
    }
  }
}
const crossed = allPercentiles.filter((p) => p >= 0.95 || p <= 0.05).length;

// Effect size versus the noise we generated ourselves by picking a swing rule.
const fibMeans = ["Z1_0382", "Z2_0500", "Z3_golden", "Z4_0786"].map(
  (id) => primaryZones[id][horizonKey].mean,
);
const randomAcrossLookbacks = Object.values(e35.btc.by_lookback).map(
  (zonesAtL) => zonesAtL.Z5_random[horizonKey].mean,
);
const spread = (values) => Math.max(...values) - Math.min(...values);

const payload = {
  generatedAt: new Date().toISOString(),
  source: {
    screen: "docs/stvb-e33-diag.json",
    counting: "docs/rvol-ep9m-diag.json",
    levels: "docs/golden-pocket-e35.json",
  },
  screen: { horizons },
  counting: {
    rows: counting,
    rawSignals: need(rvol.signal_days, "signal_days"),
    episodes: need(rvol.distinct_episodes, "distinct_episodes"),
    totalDays: need(rvol.total_days, "total_days"),
  },
  levels: {
    zones,
    lookback: primary.lookback,
    horizon: primary.horizon,
    measurements: allPercentiles.length,
    crossedThreshold: crossed,
    minPercentile: Math.min(...allPercentiles),
    maxPercentile: Math.max(...allPercentiles),
    fibSpread: spread(fibMeans),
    parameterNoise: spread(randomAcrossLookbacks),
    verdict: e35.verdict,
  },
};

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(OUT, `${JSON.stringify(payload, null, 1)}\n`);
console.log(
  `compared-to-what: ${payload.screen.horizons.length} screen horizons, ` +
    `${payload.counting.rows.length} counting rows, ${payload.levels.zones.length} zones, ` +
    `${payload.levels.measurements} percentiles (${crossed} crossed) -> ${OUT}`,
);
