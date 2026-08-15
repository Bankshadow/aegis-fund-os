/**
 * News → venue / asset risk scoring.
 *
 * Deterministic and rule-based on purpose. The project constitution treats
 * "Done" as a passing check and never a model opinion, so the tilt behind every
 * badge on the news dashboards has to be reproducible and unit-testable: same
 * headline in, same score out, no per-item token cost, no drift between runs.
 *
 * Read-only monitoring. Nothing in this module places, cancels, or sizes an
 * order, and no score here is a recommendation to trade.
 */

export type FeedKind = "news" | "status";

export type NewsSource = {
  id: string;
  label: string;
  url: string;
  kind: FeedKind;
};

export type RawArticle = {
  title: string;
  summary: string;
  link: string;
  /** ISO string, or null when the feed omitted a usable date. */
  publishedAt: string | null;
  sourceId: string;
  sourceLabel: string;
};

export type ImpactRule = {
  id: string;
  label: string;
  /** Negative = bad for the venue/asset, positive = good. */
  weight: number;
  /** Custody- or solvency-threatening. A single hit forces the band up. */
  severe?: boolean;
  pattern: RegExp;
  /**
   * Context that cancels the rule. Keyword matching cannot tell "hacked" from
   * "keeps hackers out", and on live data that difference put a healthy venue
   * into ELEVATED — so the common inversions are named explicitly.
   */
  guard?: RegExp;
};

export type ImpactSignal = { id: string; label: string; weight: number; severe: boolean };

export type ScoredArticle = RawArticle & {
  score: number;
  signals: ImpactSignal[];
  exchangeIds: string[];
  assetSymbols: string[];
  /** Recency weight in (0, 1]; 1 = just published. */
  decay: number;
  /** Dated in the future — an announced/scheduled change, not an incident. */
  scheduled: boolean;
  /** Affects one listed token or one region, not the venue as a whole. */
  narrowScope: boolean;
};

export type RiskBand = "CRITICAL" | "ELEVATED" | "WATCH" | "CALM";

export type EntityRisk = {
  id: string;
  name: string;
  held: boolean;
  /** Explicitly tracked by the operator — always shown, even when quiet. */
  watched: boolean;
  /** Approximate top-10 rank by spot volume, or null when unranked. */
  rank: number | null;
  band: RiskBand;
  negativePressure: number;
  positiveSupport: number;
  net: number;
  severeCount: number;
  articleCount: number;
  articles: ScoredArticle[];
};

export type SourceStatus = {
  id: string;
  label: string;
  kind: FeedKind;
  status: "ok" | "failed";
  itemCount: number;
  error?: string;
};

export type TrendingStory = {
  key: string;
  title: string;
  link: string;
  publishedAt: string | null;
  sourceLabels: string[];
  score: number;
  heat: number;
  exchangeIds: string[];
  assetSymbols: string[];
  signals: ImpactSignal[];
};

export type NewsRiskSnapshot = {
  schema: "aegis.news-risk.v1";
  generatedAt: string;
  sources: SourceStatus[];
  exchanges: EntityRisk[];
  assets: EntityRisk[];
  trending: TrendingStory[];
  totals: {
    articles: number;
    scoredArticles: number;
    heldExchangesAtRisk: number;
    heldAssetsAtRisk: number;
  };
};

/* ------------------------------------------------------------------ feeds */

/**
 * Free, key-less feeds only. Every fetch is independent and failure-tolerant —
 * a dead feed degrades one row in the source table, it never blanks the board.
 */
export const NEWS_SOURCES: NewsSource[] = [
  {
    id: "coindesk",
    label: "CoinDesk",
    url: "https://www.coindesk.com/arc/outboundfeeds/rss/",
    kind: "news",
  },
  {
    id: "cointelegraph",
    label: "Cointelegraph",
    url: "https://cointelegraph.com/rss",
    kind: "news",
  },
  { id: "decrypt", label: "Decrypt", url: "https://decrypt.co/feed", kind: "news" },
  { id: "theblock", label: "The Block", url: "https://www.theblock.co/rss.xml", kind: "news" },
  { id: "cryptoslate", label: "CryptoSlate", url: "https://cryptoslate.com/feed/", kind: "news" },
  {
    id: "bitcoinmagazine",
    label: "Bitcoin Magazine",
    url: "https://bitcoinmagazine.com/feed",
    kind: "news",
  },
  // Statuspage history feeds — the venue's own incident record, which is where a
  // withdrawal halt shows up before a journalist writes it.
  {
    id: "status-coinbase",
    label: "Coinbase status",
    url: "https://status.coinbase.com/history.rss",
    kind: "status",
  },
  {
    id: "status-kraken",
    label: "Kraken status",
    url: "https://status.kraken.com/history.rss",
    kind: "status",
  },
  // Deliberately absent: Pionex. Its Statuspage (pionex.statuspage.io) was never
  // configured and still serves Statuspage's stock "This is an example incident"
  // placeholder, and its blog feed is self-published marketing. Neither is
  // evidence about the venue, and piping either into a live risk board would put
  // synthetic or promotional content behind a real badge. Pionex is monitored
  // through the independent newsrooms above instead; revisit if it ever starts
  // publishing real incidents.
];

/* -------------------------------------------------------------- registries */

export type ExchangeEntry = {
  id: string;
  name: string;
  rank: number | null;
  aliases: string[];
  /**
   * Operator-tracked venue: always shown, even when quiet and even when the book
   * holds nothing there. For a venue you actually run bots on, a silent row is
   * the answer to "anything happened?" — dropping it off the board is not.
   */
  watch?: boolean;
};

/**
 * Top-10 ranks are approximate spot-volume ordering, kept here as editable data
 * rather than fetched — a wrong rank misorders a table, a wrong feed misses an
 * incident, so only the second one is worth a network call.
 */
export const EXCHANGE_REGISTRY: ExchangeEntry[] = [
  { id: "binance", name: "Binance", rank: 1, aliases: ["Binance"] },
  { id: "coinbase", name: "Coinbase", rank: 2, aliases: ["Coinbase"] },
  { id: "okx", name: "OKX", rank: 3, aliases: ["OKX", "OKEx"] },
  { id: "bybit", name: "Bybit", rank: 4, aliases: ["Bybit"] },
  { id: "upbit", name: "Upbit", rank: 5, aliases: ["Upbit"] },
  { id: "kraken", name: "Kraken", rank: 6, aliases: ["Kraken"] },
  { id: "bitget", name: "Bitget", rank: 7, aliases: ["Bitget"] },
  { id: "kucoin", name: "KuCoin", rank: 8, aliases: ["KuCoin"] },
  { id: "gateio", name: "Gate.io", rank: 9, aliases: ["Gate.io"] },
  { id: "htx", name: "HTX", rank: 10, aliases: ["HTX", "Huobi"] },
  // Unranked but in scope: venues this book touches or the operator cares about.
  // Pionex is the grid-bot venue for this project, so it is watched explicitly
  // rather than left to surface only when a newsroom happens to mention it.
  { id: "pionex", name: "Pionex", rank: null, aliases: ["Pionex"], watch: true },
  { id: "hyperliquid", name: "Hyperliquid", rank: null, aliases: ["Hyperliquid"] },
  { id: "bitkub", name: "Bitkub", rank: null, aliases: ["Bitkub"] },
  { id: "cryptocom", name: "Crypto.com", rank: null, aliases: ["Crypto.com"] },
  { id: "mexc", name: "MEXC", rank: null, aliases: ["MEXC"] },
  { id: "webull", name: "Webull", rank: null, aliases: ["Webull"] },
  { id: "ibkr", name: "Interactive Brokers", rank: null, aliases: ["Interactive Brokers", "IBKR"] },
];

export type AssetEntry = { symbol: string; name: string; aliases: string[] };

export const ASSET_REGISTRY: AssetEntry[] = [
  { symbol: "BTC", name: "Bitcoin", aliases: ["BTC", "Bitcoin"] },
  { symbol: "ETH", name: "Ethereum", aliases: ["ETH", "Ethereum", "Ether"] },
  { symbol: "SOL", name: "Solana", aliases: ["SOL", "Solana"] },
  { symbol: "USDT", name: "Tether", aliases: ["USDT", "Tether"] },
  { symbol: "USDC", name: "USD Coin", aliases: ["USDC", "Circle"] },
  { symbol: "XRP", name: "XRP", aliases: ["XRP", "Ripple"] },
  { symbol: "BNB", name: "BNB", aliases: ["BNB"] },
  { symbol: "AAPL", name: "Apple", aliases: ["AAPL", "Apple"] },
  { symbol: "MSFT", name: "Microsoft", aliases: ["MSFT", "Microsoft"] },
  { symbol: "NVDA", name: "NVIDIA", aliases: ["NVDA", "Nvidia"] },
  { symbol: "AOT", name: "Airports of Thailand", aliases: ["AOT", "Airports of Thailand"] },
];

/* ------------------------------------------------------------------ rules */

/**
 * Weights are bounded to [-3, +2] per rule so no single phrase can dominate,
 * and the negative side reaches -3 only for events that threaten custody.
 */
export const IMPACT_RULES: ImpactRule[] = [
  {
    id: "hack",
    label: "Hack / exploit",
    weight: -3,
    severe: true,
    pattern:
      /\b(hack(s|ed|ing)?|exploit(s|ed)?|breach(es|ed)?|stolen|drained|siphon(ed)?|cyber-? ?attacks?|security incident)\b|แฮก|ถูกขโมย/i,
    guard:
      /\b(red team(s|ed|ing)?|bug bounty|white ?hat|prevent(s|ed|ing)?|protect(s|ed|ing)?|thwart(s|ed)?|foil(s|ed)?|avert(s|ed)?|keeps? (hackers|attackers) out|anti-?hack|simulat(e|es|ed|ion)|drill|awareness|how to (avoid|protect|spot)|warns? (of|about)|recover(s|ed) (the |all )?(stolen )?funds)\b/i,
  },
  {
    id: "withdrawal-halt",
    label: "Withdrawals / trading halted",
    weight: -3,
    severe: true,
    // Both orderings, because a statuspage writes "Deposits Temporarily
    // Suspended" while a newsroom writes "Exchange suspends withdrawals".
    pattern:
      /\b(?:halt(?:s|ed|ing)?|suspend(?:s|ed|ing)?|paus(?:e|es|ed)|freez(?:e|es)|frozen)\b[^.]{0,40}\b(?:withdrawal|withdrawals|deposit|deposits|redemption|redemptions|trading)\b|\b(?:withdrawal|withdrawals|deposit|deposits|redemption|redemptions|trading)\b[^.]{0,40}\b(?:halted|suspended|paused|frozen|disabled)\b|ระงับการถอน/i,
    guard:
      /\b(resum(e|es|ed)|restor(e|es|ed)|back online|lift(s|ed) the (halt|suspension)|fully operational)\b/i,
  },
  {
    id: "insolvency",
    label: "Insolvency / missing funds",
    weight: -3,
    severe: true,
    pattern:
      /\b(insolven(t|cy)|bankrupt(cy)?|chapter 11|commingl(e|ed|ing)|missing funds|reserve shortfall|unable to meet withdrawals)\b|ล้มละลาย/i,
    guard: /\b(anniversary|documentary|lessons? (from|of)|years? (after|since)|looking back)\b/i,
  },
  {
    id: "depeg",
    label: "Depeg / collapse",
    weight: -3,
    severe: true,
    pattern: /\b(de-?peg(s|ged|ging)?|collapse[sd]?|implod(e|es|ed|ing)|death spiral)\b/i,
    guard: /\b(re-?peg(s|ged)?|restored (its )?peg|no risk of|avoided|unlikely to)\b/i,
  },
  {
    id: "enforcement",
    label: "Enforcement / litigation",
    weight: -2,
    pattern:
      /\b(lawsuit|sues?|sued|charged with|indict(s|ed|ment)?|fraud|enforcement action|crackdown|investigat(e|es|ed|ion)|probe|subpoena|raid(s|ed)?)\b|ฟ้องร้อง|สอบสวน/i,
    guard:
      /\b(drops? (the )?(case|charges)|charges dismissed|cleared of|withdraws? (the )?(lawsuit|case)|closes? the (probe|investigation))\b/i,
  },
  {
    id: "penalty",
    label: "Fine / sanction",
    weight: -2,
    pattern:
      /\b(fined?|penalt(y|ies)|settles? with|settlement with|sanction(s|ed)?|OFAC|money laundering|AML (violation|failures?))\b/i,
  },
  {
    id: "license-loss",
    label: "Licence loss / market exit",
    weight: -2,
    pattern:
      /\b(revok(e|es|ed)|licen[cs]e (denied|rejected|withdrawn)|ban(s|ned)?|barred|ordered to (cease|halt|stop)|exit(s|ing)? the (market|country)|shuts? down)\b|เพิกถอนใบอนุญาต/i,
  },
  { id: "delisting", label: "Delisting", weight: -1, pattern: /\bdelist(s|ed|ing)?\b/i },
  {
    id: "outage",
    label: "Outage / degradation",
    weight: -1,
    pattern:
      /\b(outage|downtime|degraded (performance|service)|service disruption|api (errors|issues)|system (failure|issues?)|incident|unavailable|maintenance extended)\b/i,
  },
  {
    id: "outflow",
    label: "Outflows / withdrawal pressure",
    weight: -1,
    pattern:
      /\b(net outflows?|outflows?|withdrawal (surge|spike)|record redemptions|users? (flee|fleeing))\b/i,
  },
  {
    id: "leadership",
    label: "Leadership exit / layoffs",
    weight: -1,
    pattern: /\b(layoffs?|lays off|steps? down|resign(s|ed|ation)?|ousted)\b/i,
  },
  {
    id: "license-win",
    label: "Licence / regulatory approval",
    weight: 2,
    pattern:
      /\b(licen[cs]e (granted|approved|obtained|secured)|regulatory approval|wins? approval|registration (granted|approved)|MiCA (licen[cs]e|authorisation|authorization)|VASP licen[cs]e)\b|ได้รับใบอนุญาต/i,
  },
  {
    id: "reserves",
    label: "Proof of reserves / audit",
    weight: 2,
    pattern:
      /\b(proof of reserves?|attestation|reserves? audit|fully backed|1:1 backed|solvency report)\b/i,
  },
  {
    id: "inflow",
    label: "Inflows / record volume",
    weight: 2,
    pattern:
      /\b(net inflows?|record (volume|inflows?)|all-time high volume|assets under (management|custody) (rise|surge|grow)s?)\b/i,
  },
  {
    id: "expansion",
    label: "Funding / expansion",
    weight: 1,
    pattern:
      /\b(raises?|funding round|acquisitions?|acquires?|partnership|expands?|launch(es|ed)?|integrat(es|ed|ion)|upgrades?)\b/i,
  },
];

/** Per-article score bound. Two severe hits still cannot exceed it. */
export const SCORE_BOUND = 4;

const clamp = (value: number, bound: number) => Math.max(-bound, Math.min(bound, value));

export function scoreText(text: string): { score: number; signals: ImpactSignal[] } {
  const signals: ImpactSignal[] = [];
  for (const rule of IMPACT_RULES) {
    // Patterns carry no /g flag on purpose: RegExp.test is stateful with /g and
    // would silently alternate hit/miss across articles.
    if (rule.pattern.test(text) && !(rule.guard && rule.guard.test(text))) {
      signals.push({
        id: rule.id,
        label: rule.label,
        weight: rule.weight,
        severe: rule.severe === true,
      });
    }
  }
  const raw = signals.reduce((total, signal) => total + signal.weight, 0);
  return { score: clamp(raw, SCORE_BOUND), signals };
}

/* ------------------------------------------------------------- feed parsing */

const decodeText = (value: string): string =>
  value
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;|&#0*39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, code: string) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code: string) =>
      String.fromCodePoint(Number.parseInt(code, 16)),
    )
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

const tagValue = (block: string, name: string): string => {
  const match = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i"));
  return match ? decodeText(match[1]) : "";
};

const atomLink = (block: string): string => {
  const match = block.match(/<link[^>]*href=["']([^"']+)["'][^>]*\/?>/i);
  return match ? decodeText(match[1]) : "";
};

const toIso = (value: string): string | null => {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : new Date(parsed).toISOString();
};

/** Parses RSS 2.0 `<item>` and Atom `<entry>` without pulling in an XML dependency. */
export function parseFeedXml(xml: string, source: NewsSource, limit = 40): RawArticle[] {
  const blocks = xml.match(/<(item|entry)\b[\s\S]*?<\/\1>/gi) ?? [];
  const articles: RawArticle[] = [];
  for (const block of blocks.slice(0, limit)) {
    const title = tagValue(block, "title");
    if (!title) continue;
    const link = tagValue(block, "link") || atomLink(block);
    const summary =
      tagValue(block, "description") || tagValue(block, "summary") || tagValue(block, "content");
    const published =
      toIso(tagValue(block, "pubDate")) ??
      toIso(tagValue(block, "published")) ??
      toIso(tagValue(block, "updated")) ??
      toIso(tagValue(block, "dc:date"));
    articles.push({
      title,
      summary: summary.slice(0, 400),
      link,
      publishedAt: published,
      sourceId: source.id,
      sourceLabel: source.label,
    });
  }
  return articles;
}

/* ---------------------------------------------------------- entity matching */

const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const aliasMatcher = (aliases: string[]) =>
  new RegExp(`(?:^|[^\\w])(?:${aliases.map(escapeRegex).join("|")})(?:[^\\w]|$)`, "i");

const EXCHANGE_MATCHERS = EXCHANGE_REGISTRY.map((entry) => ({
  id: entry.id,
  pattern: aliasMatcher(entry.aliases),
}));
const ASSET_MATCHERS = ASSET_REGISTRY.map((entry) => ({
  symbol: entry.symbol,
  pattern: aliasMatcher(entry.aliases),
}));

/**
 * A Statuspage feed never names its own venue in the item title — the incident
 * is implicitly about that exchange — so the source id carries the attribution.
 */
const STATUS_FEED_EXCHANGE: Record<string, string> = {
  "status-coinbase": "coinbase",
  "status-kraken": "kraken",
};

/**
 * Headline only, never the summary.
 *
 * A feed summary is a paragraph that name-drops half the market, so matching on
 * it attributed a mining pool's bankruptcy to Bitcoin itself and let one roundup
 * push five unrelated venues into the negative. A headline states what the story
 * is actually about; that precision is worth the recall it costs.
 */
export function matchExchanges(article: RawArticle): string[] {
  const implied = STATUS_FEED_EXCHANGE[article.sourceId];
  const matched = EXCHANGE_MATCHERS.filter((m) => m.pattern.test(article.title)).map((m) => m.id);
  return implied && !matched.includes(implied) ? [implied, ...matched] : matched;
}

export function matchAssets(article: RawArticle): string[] {
  return ASSET_MATCHERS.filter((m) => m.pattern.test(article.title)).map((m) => m.symbol);
}

/**
 * Digests and roundups cover many unrelated stories under one headline, so any
 * signal found in them belongs to no particular venue or asset. They stay
 * visible in the article counts but contribute no risk.
 */
export const DIGEST_PATTERN =
  /^(morning minute|crypto (week ahead|long ?& ?short|daily)|daily (digest|brief|recap)|weekly (recap|roundup|review)|week in review|news roundup|market wrap|top \d+|\d+ things)\b|\b(week ahead|roundup|recap)\s*[:|-]/i;

/* ------------------------------------------------------------ holdings map */

/** Demo-book platform label → registry id. Unknown labels are simply not held. */
const PLATFORM_TO_EXCHANGE: Record<string, string> = {
  binance: "binance",
  coinbase: "coinbase",
  kraken: "kraken",
  bybit: "bybit",
  okx: "okx",
  hyperliquid: "hyperliquid",
  bitkub: "bitkub",
  webull: "webull",
  ibkr: "ibkr",
  "interactive brokers": "ibkr",
};

export type HeldAccount = { platform: string; cash: number; mv: number };

/**
 * A venue counts as held only when it actually carries balance. A configured but
 * empty or disconnected account is monitored as a top-10 venue, not reported as
 * exposure the operator has to defend.
 */
export function resolveHeldExchangeIds(accounts: HeldAccount[]): string[] {
  const held = new Set<string>();
  for (const account of accounts) {
    if (account.cash + account.mv <= 0) continue;
    const id = PLATFORM_TO_EXCHANGE[account.platform.trim().toLowerCase()];
    if (id) held.add(id);
  }
  return [...held];
}

const KNOWN_SYMBOLS = new Set(ASSET_REGISTRY.map((entry) => entry.symbol));

/**
 * Both legs of a crypto pair are holdings: sitting in USDT is a position in
 * Tether, and a depeg is exactly the kind of news this board exists to catch.
 */
export function resolveHeldAssetSymbols(positionSymbols: string[]): string[] {
  const held = new Set<string>();
  for (const raw of positionSymbols) {
    for (const leg of raw.toUpperCase().split(/[-/_]/)) {
      if (KNOWN_SYMBOLS.has(leg)) held.add(leg);
    }
  }
  return [...held];
}

/* ---------------------------------------------------------------- scoring */

export const HALF_LIFE_HOURS = 48;
export const SCHEDULED_HALF_LIFE_HOURS = 24 * 7;
export const MAX_AGE_HOURS = 24 * 7;

export function recencyDecay(ageHours: number, halfLifeHours = HALF_LIFE_HOURS): number {
  return Math.pow(0.5, Math.max(0, ageHours) / halfLifeHours);
}

/**
 * Statuspage feeds are full of *scheduled* maintenance and delistings dated weeks
 * ahead. Clamping a negative age to zero would score a delisting planned for
 * September as breaking news today, so a future-dated item is capped at half
 * weight and grows toward that cap as the date approaches.
 */
export function weightForAge(ageHours: number): { decay: number; scheduled: boolean } {
  if (ageHours >= 0) return { decay: recencyDecay(ageHours), scheduled: false };
  return { decay: 0.5 * recencyDecay(-ageHours, SCHEDULED_HALF_LIFE_HOURS), scheduled: true };
}

/**
 * A single listed token or one country's client base is not the venue.
 * "Midnight (NIGHT) Deposits Temporarily Suspended" reads like a withdrawal halt
 * to a keyword matcher, and left alone it would put a healthy exchange in
 * CRITICAL — so a narrow-scope item keeps its direction but loses its severity.
 */
export const NARROW_SCOPE_PATTERN =
  /\([A-Z0-9]{2,10}\)|\bfor [A-Z][A-Za-z]+ (clients|customers|users|residents)\b|\b(single|one) (token|asset|pair|market)\b/;

const demoteNarrowScope = (signals: ImpactSignal[]): ImpactSignal[] =>
  signals.map((signal) => ({
    ...signal,
    severe: false,
    weight: Math.sign(signal.weight) * Math.min(Math.abs(signal.weight), 1),
  }));

export function scoreArticle(article: RawArticle, now: number): ScoredArticle {
  const isDigest = DIGEST_PATTERN.test(article.title);
  const matched = isDigest ? { score: 0, signals: [] } : scoreText(article.title);
  const narrowScope = NARROW_SCOPE_PATTERN.test(article.title);
  const signals = narrowScope ? demoteNarrowScope(matched.signals) : matched.signals;
  const score = narrowScope
    ? clamp(
        signals.reduce((total, signal) => total + signal.weight, 0),
        SCORE_BOUND,
      )
    : matched.score;

  const published = article.publishedAt ? Date.parse(article.publishedAt) : Number.NaN;
  // An undated item is treated as one half-life old rather than as breaking news:
  // unknown recency must not be able to raise a band on its own.
  const ageHours = Number.isNaN(published) ? HALF_LIFE_HOURS : (now - published) / 3_600_000;
  const { decay, scheduled } = weightForAge(ageHours);

  return {
    ...article,
    score,
    signals,
    exchangeIds: matchExchanges(article),
    assetSymbols: matchAssets(article),
    decay,
    scheduled,
    narrowScope,
  };
}

/**
 * The band is driven by negative pressure alone — good news never nets out bad.
 * A proof-of-reserves post published the same week as a withdrawal halt does not
 * make the withdrawal halt less true, and averaging the two would hide it.
 */
export function bandFor(negativePressure: number, severeCount: number): RiskBand {
  if (severeCount > 0 && negativePressure >= 2.5) return "CRITICAL";
  if (severeCount > 0 || negativePressure >= 3) return "ELEVATED";
  if (negativePressure >= 1) return "WATCH";
  return "CALM";
}

export const BAND_ORDER: Record<RiskBand, number> = { CRITICAL: 0, ELEVATED: 1, WATCH: 2, CALM: 3 };

/** The signal that carries an article — used to detect repeated routine chatter. */
const dominantSignalId = (article: ScoredArticle): string => {
  if (article.signals.length === 0) return "none";
  return article.signals.reduce((best, signal) =>
    Math.abs(signal.weight) > Math.abs(best.weight) ? signal : best,
  ).id;
};

function aggregate(
  id: string,
  name: string,
  rank: number | null,
  held: boolean,
  articles: ScoredArticle[],
  watched = false,
): EntityRisk {
  let negativePressure = 0;
  let positiveSupport = 0;
  let severeCount = 0;

  // Strongest first, so when the same routine signal repeats it is the most
  // significant instance that keeps full weight.
  const ordered = [...articles].sort(
    (a, b) => Math.abs(b.score) * b.decay - Math.abs(a.score) * a.decay,
  );
  const seenPerSignal = new Map<string, number>();

  for (const article of ordered) {
    // Harmonic damping per signal type: four routine token delistings in one week
    // are one operational pattern, not four independent threats, and summing them
    // linearly is what pushed a healthy venue into ELEVATED on live data.
    const signalId = dominantSignalId(article);
    const occurrence = (seenPerSignal.get(signalId) ?? 0) + 1;
    seenPerSignal.set(signalId, occurrence);
    const weighted = (Math.abs(article.score) * article.decay) / occurrence;

    if (article.score < 0) negativePressure += weighted;
    else if (article.score > 0) positiveSupport += weighted;
    // Severity only counts while the event is still fresh; a six-day-old exploit
    // with no follow-up should decay out of CRITICAL on its own.
    if (article.signals.some((signal) => signal.severe) && article.decay >= 0.35) severeCount += 1;
  }
  const round = (value: number) => Math.round(value * 100) / 100;
  return {
    id,
    name,
    held,
    watched,
    rank,
    band: bandFor(negativePressure, severeCount),
    negativePressure: round(negativePressure),
    positiveSupport: round(positiveSupport),
    net: round(positiveSupport - negativePressure),
    severeCount,
    articleCount: articles.length,
    articles: ordered.slice(0, 8),
  };
}

/* --------------------------------------------------------------- trending */

const STOPWORDS = new Set([
  "the",
  "a",
  "an",
  "of",
  "to",
  "in",
  "on",
  "for",
  "and",
  "as",
  "is",
  "are",
  "it",
  "its",
  "with",
  "by",
  "from",
  "at",
  "after",
  "over",
  "into",
  "amid",
  "says",
  "say",
  "new",
]);

const titleTokens = (title: string): Set<string> =>
  new Set(
    title
      .toLowerCase()
      .replace(/[^a-z0-9฀-๿\s]/g, " ")
      .split(/\s+/)
      .filter((token) => token.length > 2 && !STOPWORDS.has(token)),
  );

const jaccard = (left: Set<string>, right: Set<string>): number => {
  if (left.size === 0 || right.size === 0) return 0;
  let shared = 0;
  for (const token of left) if (right.has(token)) shared += 1;
  return shared / (left.size + right.size - shared);
};

/**
 * "Heat" is how loudly the market is talking, not how bad the news is: distinct
 * outlets carrying the same story dominate the term, impact only modulates it.
 * That keeps the supplementary board a firehose gauge and leaves the risk call
 * to the exchange and asset boards.
 */
export function buildTrending(articles: ScoredArticle[], limit = 12): TrendingStory[] {
  const clusters: Array<{ tokens: Set<string>; items: ScoredArticle[] }> = [];
  for (const article of articles) {
    const tokens = titleTokens(article.title);
    const existing = clusters.find((cluster) => jaccard(cluster.tokens, tokens) >= 0.5);
    if (existing) existing.items.push(article);
    else clusters.push({ tokens, items: [article] });
  }

  return clusters
    .map((cluster) => {
      const items = [...cluster.items].sort((a, b) => b.decay - a.decay);
      const lead = items[0];
      const sourceLabels = [...new Set(items.map((item) => item.sourceLabel))];
      const strongest = items.reduce(
        (best, item) => (Math.abs(item.score) > Math.abs(best.score) ? item : best),
        lead,
      );
      const heat =
        Math.round(lead.decay * (2 * sourceLabels.length + Math.abs(strongest.score)) * 100) / 100;
      return {
        key: lead.link || lead.title,
        title: lead.title,
        link: lead.link,
        publishedAt: lead.publishedAt,
        sourceLabels,
        score: strongest.score,
        heat,
        exchangeIds: [...new Set(items.flatMap((item) => item.exchangeIds))],
        assetSymbols: [...new Set(items.flatMap((item) => item.assetSymbols))],
        signals: strongest.signals,
      };
    })
    .sort((a, b) => b.heat - a.heat)
    .slice(0, limit);
}

/* --------------------------------------------------------------- snapshot */

export type SnapshotInput = {
  articles: RawArticle[];
  sources: SourceStatus[];
  heldExchangeIds: string[];
  heldAssetSymbols: string[];
  now?: number;
};

export function buildNewsRiskSnapshot(input: SnapshotInput): NewsRiskSnapshot {
  const now = input.now ?? Date.now();
  const heldExchanges = new Set(input.heldExchangeIds);
  const heldAssets = new Set(input.heldAssetSymbols);

  const seen = new Set<string>();
  const scored: ScoredArticle[] = [];
  for (const article of input.articles) {
    const key = (article.link || article.title).trim().toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const item = scoreArticle(article, now);
    if (item.decay < recencyDecay(MAX_AGE_HOURS)) continue;
    scored.push(item);
  }

  const byExchange = new Map<string, ScoredArticle[]>();
  const byAsset = new Map<string, ScoredArticle[]>();
  for (const article of scored) {
    for (const id of article.exchangeIds) {
      byExchange.set(id, [...(byExchange.get(id) ?? []), article]);
    }
    for (const symbol of article.assetSymbols) {
      byAsset.set(symbol, [...(byAsset.get(symbol) ?? []), article]);
    }
  }

  // A venue earns a row by being ranked, watched, held, or in the news. Filtering
  // on rank alone silently hid every unranked venue — Bitkub could be the top
  // story on Market Pulse while its row was missing from the board entirely.
  const exchanges = EXCHANGE_REGISTRY.filter(
    (entry) =>
      entry.rank !== null ||
      entry.watch === true ||
      heldExchanges.has(entry.id) ||
      (byExchange.get(entry.id)?.length ?? 0) > 0,
  )
    .map((entry) =>
      aggregate(
        entry.id,
        entry.name,
        entry.rank,
        heldExchanges.has(entry.id),
        byExchange.get(entry.id) ?? [],
        entry.watch === true,
      ),
    )
    // Held first, then risk band — the operator's own exposure outranks a louder
    // story somewhere they hold nothing, but a real incident still beats a quiet
    // watched venue. Within a band, watched venues precede the generic top 10.
    .sort(
      (a, b) =>
        Number(b.held) - Number(a.held) ||
        BAND_ORDER[a.band] - BAND_ORDER[b.band] ||
        Number(b.watched) - Number(a.watched) ||
        (a.rank ?? 99) - (b.rank ?? 99),
    );

  const assets = ASSET_REGISTRY.filter((entry) => heldAssets.has(entry.symbol))
    .map((entry) =>
      aggregate(entry.symbol, entry.name, null, true, byAsset.get(entry.symbol) ?? []),
    )
    .sort(
      (a, b) => BAND_ORDER[a.band] - BAND_ORDER[b.band] || b.negativePressure - a.negativePressure,
    );

  const atRisk = (entity: EntityRisk) => entity.held && entity.band !== "CALM";

  return {
    schema: "aegis.news-risk.v1",
    generatedAt: new Date(now).toISOString(),
    sources: input.sources,
    exchanges,
    assets,
    trending: buildTrending(scored),
    totals: {
      articles: input.articles.length,
      scoredArticles: scored.length,
      heldExchangesAtRisk: exchanges.filter(atRisk).length,
      heldAssetsAtRisk: assets.filter(atRisk).length,
    },
  };
}
