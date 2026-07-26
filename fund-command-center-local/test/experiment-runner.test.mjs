import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");

const run = (spec) => {
  try {
    return execFileSync(process.execPath, [path.join("scripts", "experiment.mjs"), spec], {
      cwd: root,
      encoding: "utf8",
    });
  } catch (error) {
    // A non-clearing gate exits 1 by design; the report on stdout is what we assert.
    if (error.stdout) return error.stdout;
    throw error;
  }
};

/**
 * E29 is the runner's own regression case. It passed all three of its declared
 * mechanism criteria on the mean, and the decomposition is what showed the mean was
 * not the mechanism. If this test ever goes quiet, the runner has stopped catching
 * the failure mode it exists to catch.
 */
test("E29 decomposition reproduces the hand analysis and refuses to call it a win", () => {
  const out = run("experiments/E29.json");

  // All three declared criteria pass on the mean...
  assert.match(out, /PASS {2}M1: meanDrawdown/);
  assert.match(out, /PASS {2}M2: meanRobust/);
  assert.match(out, /PASS {2}M3: meanAlpha/);

  // ...but only 3 of 18 folds are the mechanism; 9 changed because the selection
  // step picked a different geometry, and 6 reproduce the baseline exactly.
  assert.match(out, /inert \(reproduces baseline exactly\) : 6/);
  assert.match(out, /mechanism \(same geometry chosen\) {4}: 3/);
  assert.match(out, /reselected \(geometry changed\) {7}: 9/);
  assert.match(out, /folds that stopped trading entirely : 4/);

  // Both honesty warnings must fire, and the verdict must not read as a clean win.
  assert.match(out, /largely a selection artifact/);
  assert.match(out, /tautology rather than an edge/);
  assert.match(out, /VERDICT: PARTIAL BUT SUSPECT/);
});

test("a spec without pre-declared criteria is refused", () => {
  // Criteria must be frozen before the run; a spec without them is a fishing trip.
  const bad = path.join(here, "fixtures-experiment-no-criteria.json");
  fs.writeFileSync(bad, JSON.stringify({ id: "EX", declaredAt: "2026-07-25", variant: {} }));
  try {
    let failed = false;
    try {
      execFileSync(process.execPath, [path.join("scripts", "experiment.mjs"), bad], { cwd: root, encoding: "utf8" });
    } catch (error) {
      failed = true;
      assert.match(String(error.stderr), /mechanismCriteria/);
    }
    assert.ok(failed, "runner must refuse a spec with no declared criteria");
  } finally {
    fs.rmSync(bad, { force: true });
  }
});
