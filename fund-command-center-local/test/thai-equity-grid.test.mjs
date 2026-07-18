import assert from "node:assert/strict";
import test from "node:test";
import { buildAotPaperGrid } from "../src/lib/thai-equity-grid.ts";

const input = {
  lowerPrice: "36.00",
  upperPrice: "44.00",
  referencePrice: "40.00",
  investment: "80000",
  gridCount: 8,
  mode: "ARITHMETIC",
  assumedOneWayCostPct: "0.20",
};

test("AOT paper grid rounds every row to the SET-style tick and 100-share board lot", () => {
  const rows = buildAotPaperGrid(input);
  assert.equal(rows.length, 8);
  assert.ok(rows.every((row) => Number(row.quantity) % 100 === 0));
  assert.ok(rows.every((row) => Number(row.price) / 0.25 === Math.round(Number(row.price) / 0.25)));
});

test("AOT paper grid rejects manual prices outside the paper tick", () => {
  assert.throws(() => buildAotPaperGrid({ ...input, referencePrice: "40.10" }), /฿0.25 paper tick/);
});

test("AOT paper grid rejects capital that cannot fund a board lot at the upper range", () => {
  assert.throws(() => buildAotPaperGrid({ ...input, investment: "30000" }), /below minimum notional/);
});
