import "@tanstack/react-start/server-only";

import { GridBotRepository, type D1DatabaseLike } from "./grid-bot-repository.ts";
import { reconcileAllRunningTestnetGrids } from "./grid-reconcile.ts";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server.ts";
import { placeSingleTestnetOrder } from "./binance-testnet-execution.ts";

/**
 * HTTP entrypoint for the external grid-runtime scheduler (a GitHub Actions cron
 * calls this instead of an in-Worker Nitro cron hook, which this abstracted build
 * cannot register). Two independent gates, both fail-closed:
 *
 *  1. `GRID_CRON_ENABLED` must be exactly "true" — otherwise a 200 no-op, so a
 *     scheduled workflow stays green while the loop is intentionally off.
 *  2. `X-Grid-Cron-Secret` must equal the `GRID_CRON_SECRET` Worker secret
 *     (constant-time compare) — this is an app-layer factor on top of the
 *     Cloudflare Access service token that already gates the route at the edge.
 *
 * Runs under system actor `system:grid-cron`; it never uses a human identity.
 */

export type GridCronEnv = {
  GOVERNANCE_DB?: D1DatabaseLike;
  GRID_CRON_ENABLED?: string;
  GRID_CRON_SECRET?: string;
};

const timingSafeEqual = (a: string, b: string) => {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
};

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export async function handleGridCronRequest(request: Request, env: GridCronEnv | undefined): Promise<Response> {
  if (request.method !== "POST") return jsonResponse(405, { error: "POST required" });
  if (env?.GRID_CRON_ENABLED?.trim() !== "true")
    return jsonResponse(200, { enabled: false, ranAt: new Date().toISOString(), results: [] });

  const secret = env?.GRID_CRON_SECRET?.trim();
  const provided = request.headers.get("x-grid-cron-secret")?.trim() ?? "";
  if (!secret || !timingSafeEqual(provided, secret)) return jsonResponse(401, { error: "unauthorized" });

  if (!env?.GOVERNANCE_DB) return jsonResponse(503, { error: "governance storage unavailable" });

  const repo = new GridBotRepository(env.GOVERNANCE_DB);
  const results = await reconcileAllRunningTestnetGrids(repo, "system:grid-cron", {
    getStatus: getBinanceTestnetGridStatus,
    placeOrder: placeSingleTestnetOrder,
  });
  return jsonResponse(200, { enabled: true, ranAt: new Date().toISOString(), results });
}
