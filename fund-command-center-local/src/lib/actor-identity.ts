/**
 * Resolve the acting identity for a governed mutation. Fail-closed by default:
 * without a verified Cloudflare Access identity (and off localhost) the mutation
 * is blocked.
 *
 * `publicTestMode` is an explicit, operator-set escape hatch for the public
 * testnet research deployment (no login). When enabled it accepts a
 * client-supplied claim (spoofable — acceptable because execution is locked to
 * Binance Spot Testnet with no real funds) so create / one-click start /
 * reconcile can run, and even maker≠checker four-eyes can be exercised with two
 * distinct claims. It is OFF unless `AEGIS_PUBLIC_TEST_MODE === "true"`, so
 * production without the flag keeps requiring Access.
 */
export const PUBLIC_TEST_ACTOR = "public-test-operator";

export function resolveActorIdentity(input: {
  accessEmail?: string | null;
  accessJwt?: string | null;
  hostname: string;
  localClaim?: string;
  publicTestMode: boolean;
}): string {
  const email = input.accessEmail?.trim();
  const jwt = input.accessJwt?.trim();
  if (email && jwt) return email.toLowerCase();

  const isLocalhost = input.hostname === "127.0.0.1" || input.hostname === "localhost";
  const claim = input.localClaim?.trim();
  if (isLocalhost && claim) return claim.toLowerCase();

  if (input.publicTestMode) return claim ? claim.toLowerCase() : PUBLIC_TEST_ACTOR;

  throw new Error("Verified Cloudflare Access identity is required; mutation blocked");
}
