import assert from "node:assert/strict";
import test from "node:test";

import {
  parseLoopLineageSnapshot,
  unconfiguredLoopLineage,
} from "../src/lib/loop-lineage.ts";

const validSnapshot = () => ({
  schemaVersion: 1,
  source: "verified_loop_lineage",
  generatedAt: "2026-07-16T00:00:00+00:00",
  readOnly: true,
  integrity: {
    experimentChain: "verified",
    experimentRecordCount: 1,
    memoryFileHash: "a".repeat(64),
    driftQueueRecordCount: 1,
    driftQueueFileHash: "b".repeat(64),
    reviewChain: "verified",
    reviewRecordCount: 1,
    reviewFileHash: "c".repeat(64),
  },
  summary: {
    experimentCount: 1,
    openDriftTaskCount: 1,
    verdictCounts: { kill: 1, revise: 0, paper_review: 0, unresolved: 0 },
    reviewCounts: { approved_for_paper: 0, rejected: 0, pending: 0 },
  },
  experiments: [
    {
      experimentId: "E26",
      target: "research",
      decision: "kill",
      datasets: ["BTCUSDT 4h"],
      reasons: ["lost to cash"],
      recordHash: "d".repeat(64),
      paperReview: null,
    },
  ],
  driftTasks: [
    {
      taskId: "drift-1",
      action: "open_research_task",
      signals: ["robust_score_drop"],
    },
  ],
  capabilities: {
    canMutateStrategy: false,
    canApprovePaper: false,
    canPlaceOrder: false,
  },
});

test("returns an explicit read-only fallback when unconfigured", () => {
  const snapshot = unconfiguredLoopLineage();
  assert.equal(snapshot.source, "demo_fallback");
  assert.equal(snapshot.readOnly, true);
  assert.deepEqual(snapshot.experiments, []);
  assert.deepEqual(snapshot.capabilities, {
    canMutateStrategy: false,
    canApprovePaper: false,
    canPlaceOrder: false,
  });
});

test("accepts a verified read-only lineage snapshot", () => {
  const snapshot = parseLoopLineageSnapshot(JSON.stringify(validSnapshot()));
  assert.equal(snapshot.experiments[0].experimentId, "E26");
  assert.equal(snapshot.driftTasks[0].action, "open_research_task");
});

test("rejects any snapshot that advertises mutation capability", () => {
  const raw = validSnapshot();
  raw.capabilities.canMutateStrategy = true;
  assert.throws(
    () => parseLoopLineageSnapshot(JSON.stringify(raw)),
    /read-only lineage validation/,
  );
});

test("rejects invalid experiment and drift actions", () => {
  const experiment = validSnapshot();
  experiment.experiments[0].decision = "live";
  assert.throws(() => parseLoopLineageSnapshot(JSON.stringify(experiment)), /invalid experiment/);

  const drift = validSnapshot();
  drift.driftTasks[0].action = "change_parameters";
  assert.throws(() => parseLoopLineageSnapshot(JSON.stringify(drift)), /invalid drift task/);
});

test("rejects a self-review or review bound to another experiment hash", () => {
  const selfReview = validSnapshot();
  selfReview.experiments[0].paperReview = {
    reviewedAt: "2026-07-17T00:00:00+00:00",
    experimentRecordHash: "d".repeat(64),
    maker: "same@example.com",
    reviewer: "SAME@example.com",
    decision: "approved_for_paper",
    rationale: "self review",
    recordHash: "e".repeat(64),
  };
  assert.throws(() => parseLoopLineageSnapshot(JSON.stringify(selfReview)), /invalid paper review/);

  const rebound = validSnapshot();
  rebound.experiments[0].paperReview = {
    reviewedAt: "2026-07-17T00:00:00+00:00",
    experimentRecordHash: "f".repeat(64),
    maker: "maker@example.com",
    reviewer: "reviewer@example.com",
    decision: "approved_for_paper",
    rationale: "independent review",
    recordHash: "e".repeat(64),
  };
  assert.throws(() => parseLoopLineageSnapshot(JSON.stringify(rebound)), /invalid paper review/);
});
