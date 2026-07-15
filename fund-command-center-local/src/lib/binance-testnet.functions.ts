import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";

import { probeBinanceSpotTestnet } from "./binance-testnet.server";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

function assertTrustedSameOriginRequest() {
  const request = getRequest();
  const requestUrl = new URL(request.url);
  const isLoopback = LOOPBACK_HOSTS.has(requestUrl.hostname);

  if (!isLoopback && requestUrl.protocol !== "https:") {
    throw new Error("Binance Testnet integration requires HTTPS outside local development.");
  }

  const origin = request.headers.get("origin");
  if (!origin && !isLoopback) {
    throw new Error("Binance Testnet integration requires a same-origin browser request.");
  }
  if (origin && new URL(origin).origin !== requestUrl.origin) {
    throw new Error("Cross-origin integration requests are not allowed.");
  }
}

export const testBinanceTestnetConnection = createServerFn({ method: "POST" }).handler(async () => {
  assertTrustedSameOriginRequest();
  return probeBinanceSpotTestnet();
});
