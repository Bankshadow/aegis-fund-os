import assert from "node:assert/strict";
import test from "node:test";
import {
  appendGovernanceEvent,
  decideApproval,
  submitForApproval,
  transitionRuntime,
  verifyGovernanceChain,
  verifyGovernanceChains,
} from "../src/lib/grid-bot-governance.ts";

const draft = { id: "BOT-1", state: "DRAFT", makerId: "maker-a", version: 1 };

test("enforces maker-checker separation and one terminal decision", () => {
  const pending = submitForApproval(draft, "maker-a");
  assert.equal(pending.state, "PENDING_APPROVAL");
  assert.throws(() => decideApproval(pending, "maker-a", "APPROVED"), /Maker cannot/);
  const approved = decideApproval(pending, "checker-b", "APPROVED");
  assert.equal(approved.state, "APPROVED");
  assert.equal(approved.checkerId, "checker-b");
  assert.throws(() => decideApproval(approved, "checker-c", "REJECTED"), /not awaiting/);
});

test("allows only approved runtime lifecycle transitions", () => {
  assert.throws(() => transitionRuntime("DRAFT", "IDLE", "RUNNING"), /Only an approved/);
  assert.equal(transitionRuntime("APPROVED", "IDLE", "RUNNING"), "RUNNING");
  assert.equal(transitionRuntime("APPROVED", "RUNNING", "PAUSED"), "PAUSED");
  assert.equal(transitionRuntime("APPROVED", "PAUSED", "RUNNING"), "RUNNING");
  assert.equal(transitionRuntime("APPROVED", "RUNNING", "STOPPED"), "STOPPED");
  assert.throws(() => transitionRuntime("APPROVED", "STOPPED", "RUNNING"), /Invalid runtime/);
});

test("verifies independent per-bot audit chains", async () => {
  const first = await appendGovernanceEvent([], {
    eventId: "EVT-A",
    botId: "BOT-A",
    eventType: "bot.created",
    actorId: "maker-a",
    payload: { state: "DRAFT" },
    occurredAt: "2026-07-16T00:00:00.000Z",
  });
  const second = await appendGovernanceEvent([], {
    eventId: "EVT-B",
    botId: "BOT-B",
    eventType: "bot.created",
    actorId: "maker-b",
    payload: { state: "DRAFT" },
    occurredAt: "2026-07-16T00:00:01.000Z",
  });
  assert.equal(await verifyGovernanceChains([first, second]), true);
});

test("builds a tamper-evident governance event chain", async () => {
  const first = await appendGovernanceEvent([], {
    eventId: "EV-1",
    botId: "BOT-1",
    eventType: "bot.created",
    actorId: "maker-a",
    payload: { state: "DRAFT" },
    occurredAt: "2026-07-16T00:00:00.000Z",
  });
  const second = await appendGovernanceEvent([first], {
    eventId: "EV-2",
    botId: "BOT-1",
    eventType: "approval.requested",
    actorId: "maker-a",
    payload: { state: "PENDING_APPROVAL" },
    occurredAt: "2026-07-16T00:01:00.000Z",
  });
  assert.equal(await verifyGovernanceChain([first, second]), true);
  assert.equal(await verifyGovernanceChain([first, { ...second, actorId: "attacker" }]), false);
});
