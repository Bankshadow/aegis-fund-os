import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";

import { probeHyperliquid } from "./hyperliquid.server";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

function assertLocalSameOriginRequest() {
  const request = getRequest();
  const requestUrl = new URL(request.url);
  if (!LOOPBACK_HOSTS.has(requestUrl.hostname)) {
    throw new Error("Hyperliquid integration is restricted to local development.");
  }

  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== requestUrl.host) {
    throw new Error("Cross-origin integration requests are not allowed.");
  }
}

export const testHyperliquidConnection = createServerFn({ method: "POST" }).handler(async () => {
  assertLocalSameOriginRequest();
  return probeHyperliquid();
});
