import assert from "node:assert/strict";
import test from "node:test";

import { evaluateDailyClose } from "../src/lib/daily-close.ts";

const completeChecks = { data: true, prices: true, recon: true, fx: true, fees: true };

test("blocks NAV close while reconciliation is unresolved", () => {
  const result = evaluateDailyClose({
    state: "Provisional",
    maker: "Maker",
    reviewer: "Checker",
    checks: { ...completeChecks, recon: false },
  });
  assert.equal(result.canLock, false);
  assert.match(result.blockers.join(" "), /Reconciliation/);
});

test("requires an independent reviewer before NAV close", () => {
  const result = evaluateDailyClose({
    state: "Provisional",
    maker: "Maker",
    reviewer: "Maker",
    checks: completeChecks,
  });
  assert.equal(result.canLock, false);
  assert.match(result.blockers.join(" "), /different people/);
});

test("permits lock only when all close controls pass", () => {
  const result = evaluateDailyClose({
    state: "Provisional",
    maker: "Maker",
    reviewer: "Checker",
    checks: completeChecks,
  });
  assert.deepEqual(result, { state: "Ready to lock", canLock: true, blockers: [] });
});
