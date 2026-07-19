import assert from "node:assert/strict";
import test from "node:test";
import { resolveActorIdentity, PUBLIC_TEST_ACTOR } from "../src/lib/actor-identity.ts";

const base = {
  accessEmail: null,
  accessJwt: null,
  hostname: "aegis-fund-os.example.workers.dev",
  localClaim: undefined,
  publicTestMode: false,
};

test("a verified Cloudflare Access identity wins and is lowercased", () => {
  assert.equal(
    resolveActorIdentity({ ...base, accessEmail: "Checker@X.com", accessJwt: "jwt" }),
    "checker@x.com",
  );
});

test("blocks fail-closed with no Access, off localhost, no public test mode", () => {
  assert.throws(() => resolveActorIdentity(base), /Cloudflare Access identity is required/);
});

test("an Access email without the JWT is not trusted", () => {
  assert.throws(
    () => resolveActorIdentity({ ...base, accessEmail: "checker@x", accessJwt: null }),
    /required/,
  );
});

test("localhost honors a client claim", () => {
  assert.equal(
    resolveActorIdentity({ ...base, hostname: "localhost", localClaim: "Maker@Local" }),
    "maker@local",
  );
});

test("localhost without a claim still fails closed", () => {
  assert.throws(() => resolveActorIdentity({ ...base, hostname: "localhost" }), /required/);
});

test("public test mode accepts a claim so maker≠checker can be exercised", () => {
  assert.equal(
    resolveActorIdentity({ ...base, publicTestMode: true, localClaim: "maker@test" }),
    "maker@test",
  );
  assert.equal(
    resolveActorIdentity({ ...base, publicTestMode: true, localClaim: "checker@test" }),
    "checker@test",
  );
});

test("public test mode without a claim uses the fixed system test actor", () => {
  assert.equal(resolveActorIdentity({ ...base, publicTestMode: true }), PUBLIC_TEST_ACTOR);
});

test("Access still takes precedence even when public test mode is on", () => {
  assert.equal(
    resolveActorIdentity({ ...base, publicTestMode: true, accessEmail: "real@x", accessJwt: "j" }),
    "real@x",
  );
});
