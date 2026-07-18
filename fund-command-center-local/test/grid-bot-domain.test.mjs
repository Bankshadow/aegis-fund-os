import assert from "node:assert/strict";
import test from "node:test";
import { buildExactGridPreview, findGridBot, roi, totalPnl } from "../src/lib/grid-bot-domain.ts";

const base = {
  lowerPrice: "90",
  upperPrice: "110",
  currentPrice: "100",
  investment: "1000",
  gridCount: 10,
  mode: "ARITHMETIC",
  feeRatePct: "0.1",
  tickSize: "0.01",
  stepSize: "0.00001",
  minNotional: "5",
};
test("builds exact arithmetic and geometric previews", () => {
  const a = buildExactGridPreview(base);
  const g = buildExactGridPreview({ ...base, mode: "GEOMETRIC" });
  assert.equal(a.length, 10);
  assert.equal(g.length, 10);
  assert.equal(a[0].price, "90");
  assert.notEqual(a[1].price, g[1].price);
  assert.ok(a.every((r) => r.initialState === "PREVIEW"));
});
test("respects tick, step and minimum notional", () => {
  const rows = buildExactGridPreview({ ...base, tickSize: "0.1", stepSize: "0.001" });
  assert.ok(rows.every((r) => (Number(r.price) * 10) % 1 === 0));
  assert.ok(rows.every((r) => (Number(r.quantity) * 1000) % 1 === 0));
  assert.throws(() => buildExactGridPreview({ ...base, investment: "20" }), /minimum notional/);
});
test("keeps grid profit, unrealized pnl, total pnl and roi separate", () => {
  const bot = findGridBot("BOT-T-104");
  assert.ok(bot);
  assert.equal(totalPnl(bot), "141.40");
  assert.equal(roi(bot), "1.18");
  assert.equal(bot.gridProfit, "184.20");
  assert.equal(bot.unrealizedPnl, "-42.80");
});
test("rejects market outside configured range", () =>
  assert.throws(() => buildExactGridPreview({ ...base, currentPrice: "120" }), /inside/));
