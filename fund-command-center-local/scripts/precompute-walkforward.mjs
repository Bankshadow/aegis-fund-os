/**
 * Precompute every Walk-Forward Lab view at build time.
 *
 * These views are pure and expensive: the comparison alone is 972 backtests and
 * ~8.9s of CPU. Running that inside a Cloudflare Worker request is not just slow, it
 * risks blowing the Worker CPU limit outright — and per-isolate memoisation does not
 * help, because every cold isolate pays it again. The fixture and the engine are
 * static, so the answer can never change between deploys: compute it once here and
 * ship JSON the Worker only has to hand back.
 *
 * Every reachable page must be covered, or a student hits an uncached path and the
 * Worker does the expensive thing after all. That is why the cost scenarios are a
 * closed preset set rather than free-form numbers.
 *
 *   node scripts/precompute-walkforward.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { analyzeMarketData, parseMarketCsv, validateMarketBars } from "../src/lib/aot-backtest.ts";
import {
  COST_PRESET_IDS,
  VARIANT_IDS,
  buildComparison,
  buildOverfitView,
  buildView,
} from "../src/lib/walk-forward-views.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "data", "historical", "AOT.BK_daily_2005-2026.csv");
const OUT_DIR = path.join(here, "..", "src", "generated");
const OUT = path.join(OUT_DIR, "walk-forward-data.json");

const { bars } = parseMarketCsv(fs.readFileSync(DATA, "utf8"));

// Same gate the research harness applies: never ship numbers derived from a file
// that failed validation.
const quality = analyzeMarketData(bars);
const blocked = validateMarketBars(bars).filter((w) => w.severity === "BLOCKED");
if (quality.duplicates || quality.missingOhlcv || quality.invalidPrices || quality.negativeVolume || blocked.length) {
  console.error("ABORT: AOT fixture failed data quality validation; refusing to precompute.");
  for (const warning of blocked) console.error(`  ${warning.code}: ${warning.message}`);
  process.exit(2);
}

const started = Date.now();
const views = {};
for (const variant of VARIANT_IDS) {
  for (const cost of COST_PRESET_IDS) {
    const key = `${variant}:${cost}`;
    const t0 = Date.now();
    views[key] = buildView(bars, variant, cost);
    console.log(`  ${key.padEnd(24)} ${String(Date.now() - t0).padStart(6)}ms`);
  }
}

const comparison = buildComparison(VARIANT_IDS.map((variant) => views[`${variant}:thai`]));
const overfitT0 = Date.now();
const overfit = buildOverfitView(bars);
console.log(`  ${"overfit".padEnd(24)} ${String(Date.now() - overfitT0).padStart(6)}ms`);

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ generatedAt: new Date().toISOString(), views, comparison, overfit }));

const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
console.log(
  `precomputed ${Object.keys(views).length} views + comparison + overfit in ${((Date.now() - started) / 1000).toFixed(1)}s -> ${OUT} (${kb} KB)`,
);
