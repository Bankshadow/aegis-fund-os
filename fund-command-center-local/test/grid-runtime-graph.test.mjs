import assert from "node:assert/strict";
import test from "node:test";
import {
  classifyReconcileRoute,
  shouldContinueReconcileLoop,
  summarizeFleetRoutes,
} from "../src/lib/grid-runtime-graph.ts";

const empty = { filled: 0, placed: 0, statusUpdated: 0, reconciliationRequired: 0, deferred: 0 };

test("ok summary routes to continue with no work remaining", () => {
  const route = classifyReconcileRoute({ ...empty, filled: 1, placed: 1 });
  assert.equal(route.severity, "ok");
  assert.equal(route.action, "continue");
  assert.equal(route.workRemaining, false);
});

test("deferred budget exhaustion routes to retry_next without operator review", () => {
  const route = classifyReconcileRoute({ ...empty, deferred: 3 });
  assert.equal(route.severity, "deferred");
  assert.equal(route.action, "retry_next");
  assert.equal(route.workRemaining, true);
});

test("reconciliationRequired outranks deferred and demands operator review", () => {
  const route = classifyReconcileRoute({ ...empty, deferred: 2, reconciliationRequired: 1 });
  assert.equal(route.severity, "mismatch");
  assert.equal(route.action, "operator_review");
});

test("failed bot classifies as error", () => {
  const route = classifyReconcileRoute(empty, true);
  assert.equal(route.severity, "error");
  assert.equal(route.action, "operator_review");
});

test("fleet summary peaks at the worst bot without mutating per-bot results", () => {
  const fleet = summarizeFleetRoutes([
    { route: classifyReconcileRoute({ ...empty, placed: 1 }) },
    { route: classifyReconcileRoute({ ...empty, deferred: 1 }) },
    { error: "lease conflict" },
  ]);
  assert.equal(fleet.ok, 1);
  assert.equal(fleet.deferred, 1);
  assert.equal(fleet.error, 1);
  assert.equal(fleet.peakSeverity, "error");
  assert.equal(fleet.action, "operator_review");
});

test("dry-loop continues while deferred work remains, stops on mismatch", () => {
  const deferred = classifyReconcileRoute({ ...empty, deferred: 1 });
  const mismatch = classifyReconcileRoute({ ...empty, reconciliationRequired: 1 });
  const ok = classifyReconcileRoute(empty);

  assert.equal(shouldContinueReconcileLoop([deferred]).continue, true);
  assert.equal(shouldContinueReconcileLoop([deferred, mismatch]).continue, false);
  assert.equal(shouldContinueReconcileLoop([deferred, mismatch]).reason, "operator_review");
  assert.equal(shouldContinueReconcileLoop([ok, ok], { dryRounds: 2 }).continue, false);
  assert.equal(shouldContinueReconcileLoop([ok, ok], { dryRounds: 2 }).reason, "dry");
});

test("dry-loop refuses to exceed maxRounds", () => {
  const deferred = classifyReconcileRoute({ ...empty, deferred: 1 });
  const decision = shouldContinueReconcileLoop([deferred, deferred, deferred], { maxRounds: 3 });
  assert.equal(decision.continue, false);
  assert.equal(decision.reason, "max_rounds");
});
