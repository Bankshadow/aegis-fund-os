import { createServerFn } from "@tanstack/react-start";

import { ACCOUNTS, POSITIONS } from "./demo-data";
import {
  NEWS_SOURCES,
  buildNewsRiskSnapshot,
  parseFeedXml,
  resolveHeldAssetSymbols,
  resolveHeldExchangeIds,
  type NewsRiskSnapshot,
  type NewsSource,
  type RawArticle,
  type SourceStatus,
} from "./news-risk";

export type {
  EntityRisk,
  NewsRiskSnapshot,
  RiskBand,
  ScoredArticle,
  TrendingStory,
} from "./news-risk";

const FETCH_TIMEOUT_MS = 6_000;
const CACHE_TTL_MS = 10 * 60_000;
const MAX_FEED_BYTES = 1_500_000;

type CachedSnapshot = { at: number; snapshot: NewsRiskSnapshot };
let cache: CachedSnapshot | undefined;

type FeedResult = { status: SourceStatus; articles: RawArticle[] };

async function fetchFeed(source: NewsSource): Promise<FeedResult> {
  try {
    const response = await fetch(source.url, {
      headers: {
        // Several outlets return 403 to a bare Workers fetch; identify the client
        // honestly instead of impersonating a browser.
        "user-agent": "AegisFundOS-NewsRisk/1.0 (read-only monitoring)",
        accept:
          "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
      },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) {
      return {
        status: {
          id: source.id,
          label: source.label,
          kind: source.kind,
          status: "failed",
          itemCount: 0,
          error: `HTTP ${response.status}`,
        },
        articles: [],
      };
    }
    const xml = (await response.text()).slice(0, MAX_FEED_BYTES);
    const articles = parseFeedXml(xml, source);
    return {
      status: {
        id: source.id,
        label: source.label,
        kind: source.kind,
        status: "ok",
        itemCount: articles.length,
      },
      articles,
    };
  } catch (error) {
    return {
      status: {
        id: source.id,
        label: source.label,
        kind: source.kind,
        status: "failed",
        itemCount: 0,
        error: error instanceof Error ? error.message : "fetch failed",
      },
      articles: [],
    };
  }
}

/**
 * Live public RSS in, deterministic risk bands out.
 *
 * Every feed is fetched independently and failures are reported rather than
 * hidden: a board that silently shows CALM because the network died is worse
 * than one that says the source is down. Nothing is ever back-filled with
 * placeholder articles — an empty board means no news matched, full stop.
 *
 * The holdings overlay comes from the demo book (`ACCOUNTS` / `POSITIONS`), so
 * "held" here means the prototype's paper/testnet ledger, not live custody.
 */
export const getNewsRiskSnapshot = createServerFn({ method: "GET" }).handler(
  async (): Promise<NewsRiskSnapshot> => {
    if (cache && Date.now() - cache.at < CACHE_TTL_MS) return cache.snapshot;

    const results = await Promise.all(NEWS_SOURCES.map(fetchFeed));
    const snapshot = buildNewsRiskSnapshot({
      articles: results.flatMap((result) => result.articles),
      sources: results.map((result) => result.status),
      heldExchangeIds: resolveHeldExchangeIds(
        ACCOUNTS.map((a) => ({ platform: a.platform, cash: a.cash, mv: a.mv })),
      ),
      heldAssetSymbols: resolveHeldAssetSymbols(POSITIONS.map((p) => p.sym)),
    });

    // Only a snapshot with at least one working feed is worth caching for ten
    // minutes; a total outage should be retried on the next page view.
    if (snapshot.sources.some((source) => source.status === "ok"))
      cache = { at: Date.now(), snapshot };
    return snapshot;
  },
);
