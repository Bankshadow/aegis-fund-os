import "@tanstack/react-start/server-only";

import { GridBotRepository, type D1DatabaseLike } from "./grid-bot-repository.ts";

/** Read-only contract consumed by external workflow tools such as n8n. */
export type AutomationStatusEnv = {
  GOVERNANCE_DB?: D1DatabaseLike;
  AEGIS_AUTOMATION_STATUS_TOKEN?: string;
  GRID_TESTNET_KILL_SWITCH?: string;
};

const equal = (left: string, right: string) => {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
};

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

/**
 * Deliberately cannot trigger reconciliation or any order operation. It returns
 * only bounded operational state so an external automation can alert humans.
 */
export async function handleAutomationStatusRequest(
  request: Request,
  env: AutomationStatusEnv | undefined,
): Promise<Response> {
  if (request.method !== "GET") return respond(405, { error: "GET required" });
  if (!env) return respond(503, { error: "automation status is unconfigured" });
  const token = env.AEGIS_AUTOMATION_STATUS_TOKEN?.trim();
  const provided = request.headers.get("x-aegis-automation-token")?.trim() ?? "";
  if (!token || !equal(provided, token)) return respond(401, { error: "unauthorized" });
  if (!env.GOVERNANCE_DB) return respond(503, { error: "governance storage unavailable" });

  const repo = new GridBotRepository(env.GOVERNANCE_DB);
  const [bots, recentRuns] = await Promise.all([repo.listBots(), repo.listRecentRuntimeRuns(undefined, 25)]);
  const controls = await Promise.all(
    bots.map(async (bot) => ({ botId: bot.id, ...(await repo.getRuntimeSafetyControl(`BOT:${bot.id}`)) })),
  );
  const halted = controls.filter((control) => control.placementDisabled);
  const failedRuns = recentRuns.filter((run) => run.status === "FAILED");
  return respond(200, {
    schema: "aegis.automation-status.v1",
    checkedAt: new Date().toISOString(),
    mode: env.GRID_TESTNET_KILL_SWITCH?.trim() === "true" ? "SAFE_HOLD" : "TESTNET_ENABLED",
    bots: { total: bots.length, running: bots.filter((bot) => bot.runtimeState === "RUNNING").length },
    safety: { haltedBots: halted.length, failedRuns: failedRuns.length },
    recentFailures: failedRuns.slice(0, 5).map((run) => ({ botId: run.botId, reason: run.reason, startedAt: run.startedAt })),
  });
}
