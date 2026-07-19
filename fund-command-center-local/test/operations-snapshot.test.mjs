import assert from "node:assert/strict";
import test from "node:test";
import {
  parseOperationsSnapshot,
  loadOperationsSnapshot,
  UNCONFIGURED_SNAPSHOT,
  DEFAULT_SNAPSHOT_KEY,
} from "../src/lib/operations-snapshot.ts";

const realSnapshot = (over = {}) =>
  JSON.stringify({
    schemaVersion: 1,
    status: "ready",
    source: "persisted_snapshot",
    generatedAt: "2026-07-19T00:00:00Z",
    fx: { reportingCurrency: "USDT", asOf: "2026-07-19", status: "Approved", totalBaseValue: 1000, rates: [] },
    exceptions: [],
    ...over,
  });

const bucketWith = (map) => ({
  reads: [],
  async get(key) {
    this.reads.push(key);
    const value = map[key];
    return value === undefined ? null : { text: async () => value };
  },
});

test("parse accepts a persisted ready/provisional record", () => {
  assert.equal(parseOperationsSnapshot(realSnapshot()).status, "ready");
  assert.equal(parseOperationsSnapshot(realSnapshot({ status: "provisional" })).status, "provisional");
});

test("parse rejects demo/invalid records (fail closed)", () => {
  assert.throws(() => parseOperationsSnapshot("{ not json"), /valid JSON/);
  assert.throws(() => parseOperationsSnapshot(realSnapshot({ source: "demo_fallback" })), /persisted/);
  assert.throws(() => parseOperationsSnapshot(realSnapshot({ status: "unconfigured" })), /persisted/);
});

test("R2 is read first, at the default key, when a bucket is bound", async () => {
  const bucket = bucketWith({ [DEFAULT_SNAPSHOT_KEY]: realSnapshot({ generatedAt: "from-r2" }) });
  const snap = await loadOperationsSnapshot({ bucket, inlineJson: realSnapshot({ generatedAt: "from-env" }) });
  assert.equal(snap.generatedAt, "from-r2");
  assert.deepEqual(bucket.reads, [DEFAULT_SNAPSHOT_KEY]);
});

test("a custom R2 key overrides the default", async () => {
  const bucket = bucketWith({ "custom.json": realSnapshot() });
  const snap = await loadOperationsSnapshot({ bucket, key: "custom.json" });
  assert.equal(snap.status, "ready");
  assert.deepEqual(bucket.reads, ["custom.json"]);
});

test("falls through to inline JSON when the R2 object is missing", async () => {
  const bucket = bucketWith({}); // key not present
  const snap = await loadOperationsSnapshot({ bucket, inlineJson: realSnapshot({ generatedAt: "from-env" }) });
  assert.equal(snap.generatedAt, "from-env");
});

test("returns the unconfigured fallback when nothing is configured", async () => {
  const snap = await loadOperationsSnapshot({});
  assert.deepEqual(snap, UNCONFIGURED_SNAPSHOT);
});

test("a configured-but-invalid R2 object fails closed rather than showing demo", async () => {
  const bucket = bucketWith({ [DEFAULT_SNAPSHOT_KEY]: realSnapshot({ source: "demo_fallback" }) });
  await assert.rejects(() => loadOperationsSnapshot({ bucket }), /persisted/);
});
