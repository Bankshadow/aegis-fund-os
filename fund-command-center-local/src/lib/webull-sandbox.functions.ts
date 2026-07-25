import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";

import { placeWebullSandboxTestOrder, probeWebullSandbox } from "./webull-sandbox.server.ts";

const sandboxOrderSchema = z.object({
  accountId: z.string().trim().min(1).max(64),
  symbol: z
    .string()
    .trim()
    .regex(/^[A-Za-z][A-Za-z0-9.-]{0,9}$/),
  side: z.enum(["BUY", "SELL"]),
  limitPrice: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,4})?$/),
  quantity: z
    .string()
    .trim()
    .regex(/^(0|[1-9]\d*)(\.\d{1,8})?$/),
});

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

function assertTrustedSameOriginRequest() {
  const request = getRequest();
  const requestUrl = new URL(request.url);
  if (!LOOPBACK_HOSTS.has(requestUrl.hostname) && requestUrl.protocol !== "https:")
    throw new Error("Webull sandbox integration requires HTTPS outside local development.");
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).origin !== requestUrl.origin)
    throw new Error("Cross-origin integration requests are not allowed.");
}

export const testWebullSandboxConnection = createServerFn({ method: "POST" }).handler(async () => {
  assertTrustedSameOriginRequest();
  return probeWebullSandbox();
});

export const placeWebullSandboxOrder = createServerFn({ method: "POST" })
  .validator(sandboxOrderSchema)
  .handler(async ({ data }) => {
    assertTrustedSameOriginRequest();
    return placeWebullSandboxTestOrder(data);
  });
