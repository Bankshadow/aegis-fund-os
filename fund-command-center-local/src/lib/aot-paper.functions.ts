import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";
import { AotPaperRepository } from "./aot-paper-repository.ts";
import { calculatePaperGrid, type PaperGridConfig } from "./aot-paper-domain.ts";
import type { D1DatabaseLike } from "./grid-bot-repository.ts";

type CloudflareRequest = Request & {
  runtime?: { cloudflare?: { env?: { GOVERNANCE_DB?: D1DatabaseLike } } };
};
const repository = () => {
  const db = (getRequest() as CloudflareRequest).runtime?.cloudflare?.env?.GOVERNANCE_DB;
  if (!db) throw new Error("Paper strategy storage is unavailable; mutation blocked");
  return new AotPaperRepository(db);
};
const actor = (claim?: string) => {
  const request = getRequest();
  const email = request.headers.get("cf-access-authenticated-user-email")?.trim();
  const jwt = request.headers.get("cf-access-jwt-assertion")?.trim();
  if (email && jwt) return email.toLowerCase();
  const host = new URL(request.url).hostname;
  if ((host === "localhost" || host === "127.0.0.1") && claim?.trim())
    return claim.trim().toLowerCase();
  throw new Error("Verified identity is required; paper mutation blocked");
};
const configSchema = z.object({
  name: z.string().trim().min(1).max(120),
  lowerPrice: z.string(),
  upperPrice: z.string(),
  referencePrice: z.string(),
  initialCash: z.string(),
  initialInventory: z.string(),
  levelCount: z.number().int().min(3).max(200),
  mode: z.enum(["ARITHMETIC", "GEOMETRIC"]),
  oneWayCostPct: z.string(),
  slippagePct: z.string(),
  maxPositionValue: z.string(),
  maxActiveOrders: z.number().int().min(1).max(400),
  stopLossPrice: z.string().optional(),
  takeProfitPrice: z.string().optional(),
});
const withActor = z.object({ actorId: z.string().optional() });
export const previewAotPaperGrid = createServerFn({ method: "POST" })
  .validator(configSchema)
  .handler(({ data }) => calculatePaperGrid(data as PaperGridConfig));
export const createAotPaperStrategy = createServerFn({ method: "POST" })
  .validator(configSchema.extend({ actorId: z.string().optional() }))
  .handler(({ data }) => repository().create(data as PaperGridConfig, actor(data.actorId)));
export const getAotPaperStrategies = createServerFn({ method: "GET" }).handler(() =>
  repository().list(),
);
export const getAotPaperStrategy = createServerFn({ method: "GET" })
  .validator(z.object({ strategyId: z.string().min(1) }))
  .handler(({ data }) => repository().get(data.strategyId));
export const requestAotPaperApproval = createServerFn({ method: "POST" })
  .validator(withActor.extend({ strategyId: z.string().min(1) }))
  .handler(({ data }) => repository().requestApproval(data.strategyId, actor(data.actorId)));
export const decideAotPaperApproval = createServerFn({ method: "POST" })
  .validator(
    withActor.extend({
      strategyId: z.string().min(1),
      approved: z.boolean(),
      reason: z.string().trim().min(3).max(500),
    }),
  )
  .handler(({ data }) =>
    repository().approve(data.strategyId, actor(data.actorId), data.approved, data.reason),
  );
export const transitionAotPaperStrategy = createServerFn({ method: "POST" })
  .validator(
    withActor.extend({
      strategyId: z.string().min(1),
      next: z.enum(["RUNNING", "PAUSED", "STOPPED"]),
    }),
  )
  .handler(async ({ data }) => {
    const repo = repository();
    const current = await repo.get(data.strategyId);
    if (data.next === "RUNNING" && current?.status === "APPROVED")
      await repo.openOrders(data.strategyId, actor(data.actorId));
    return repo.runtime(data.strategyId, actor(data.actorId), data.next);
  });
export const applyAotPaperPrice = createServerFn({ method: "POST" })
  .validator(
    withActor.extend({
      strategyId: z.string().min(1),
      eventId: z.string().uuid(),
      price: z.string(),
      volume: z.string(),
      timestamp: z.string().datetime(),
    }),
  )
  .handler(({ data }) =>
    repository().applyPrice(
      data.strategyId,
      actor(data.actorId),
      data.eventId,
      data.price,
      data.volume,
      data.timestamp,
    ),
  );
export const getAotPaperOrders = createServerFn({ method: "GET" })
  .validator(z.object({ strategyId: z.string().min(1) }))
  .handler(({ data }) => repository().listOrders(data.strategyId));
