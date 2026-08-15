import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  RESEARCH_CANDIDATES,
  RESEARCH_COLD_SHOWER,
  verdictLabel,
  verdictTone,
} from "../src/lib/research-board.ts";

describe("research board · measured honestly", () => {
  it("keeps at least one FAIL row and never hides max drawdown", () => {
    assert.ok(RESEARCH_CANDIDATES.length >= 3);
    assert.ok(RESEARCH_CANDIDATES.some((c) => c.verdict === "FAIL"));
    for (const c of RESEARCH_CANDIDATES) {
      assert.ok(c.maxDdPct > 0, `${c.id} must show a positive max-DD magnitude`);
      assert.ok(c.diagnosis.length > 20, `${c.id} needs an honest diagnosis`);
      assert.ok(c.logRef.includes("VALIDATION_LOG"), `${c.id} must cite the log`);
    }
  });

  it("matches AOT walk-forward fixture numbers for E26/E28/E29", () => {
    const e26 = RESEARCH_CANDIDATES.find((c) => c.id === "E26");
    const e28 = RESEARCH_CANDIDATES.find((c) => c.id === "E28");
    const e29 = RESEARCH_CANDIDATES.find((c) => c.id === "E29");
    assert.ok(e26 && e28 && e29);
    assert.equal(e26.robust, -17.97);
    assert.equal(e28.robust, -19.91);
    assert.equal(e29.robust, -12.17);
    assert.equal(e26.labVariant, "baseline");
    assert.equal(e28.labVariant, "trailing");
    assert.equal(e29.labVariant, "exposure-cap");
  });

  it("maps verdicts to UI tones without promoting FAIL as positive", () => {
    assert.equal(verdictTone("FAIL"), "neg");
    assert.equal(verdictTone("MECHANISM_ONLY"), "warn");
    assert.equal(verdictTone("PASS"), "pos");
    assert.match(verdictLabel("MECHANISM_ONLY"), /GATE FAIL/);
    assert.match(RESEARCH_COLD_SHOWER, /not a forecast/i);
  });
});
