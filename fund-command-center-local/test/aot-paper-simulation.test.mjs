import assert from "node:assert/strict";
import test from "node:test";
import { generateSyntheticAotBars, runAotPaperGridSimulation } from "../src/lib/aot-paper-simulation.ts";

const input = { lowerPrice: "36.00", upperPrice: "44.00", referencePrice: "40.00", investment: "80000", gridCount: 8, mode: "ARITHMETIC", assumedOneWayCostPct: "0.20" };

test("synthetic AOT OHLCV generation is deterministic and tick-aligned", () => {
  const first = generateSyntheticAotBars("40.00", 101, 20);
  assert.deepEqual(first, generateSyntheticAotBars("40.00", 101, 20));
  assert.ok(first.every((bar) => [bar.open, bar.high, bar.low, bar.close].every((price) => Number(price) / 0.25 === Math.round(Number(price) / 0.25))));
});

test("AOT simulation uses three seeds and keeps a held-out split", () => {
  const results = runAotPaperGridSimulation(input);
  assert.equal(results.length, 3);
  assert.ok(results.every((result) => result.trainBars === 96 && result.holdoutBars === 24));
  assert.ok(results.every((result) => Number(result.requiredOpeningInventoryShares) % 100 === 0));
});
