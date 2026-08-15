import assert from "node:assert/strict";
import test from "node:test";

import {
  NEWS_SOURCES,
  bandFor,
  buildNewsRiskSnapshot,
  buildTrending,
  matchAssets,
  matchExchanges,
  parseFeedXml,
  recencyDecay,
  resolveHeldAssetSymbols,
  resolveHeldExchangeIds,
  scoreArticle,
  scoreText,
} from "../src/lib/news-risk.ts";

const NOW = Date.parse("2026-07-27T00:00:00.000Z");
const hoursAgo = (h) => new Date(NOW - h * 3_600_000).toISOString();

const article = (overrides = {}) => ({
  title: "Placeholder headline",
  summary: "",
  link: `https://example.test/${Math.random()}`,
  publishedAt: hoursAgo(1),
  sourceId: "coindesk",
  sourceLabel: "CoinDesk",
  ...overrides,
});

test("scoreText is deterministic and repeatable across calls", () => {
  const headline = "Exchange halts withdrawals after exploit drains hot wallet";
  const first = scoreText(headline);
  const second = scoreText(headline);
  assert.deepEqual(first.signals.map((s) => s.id).sort(), second.signals.map((s) => s.id).sort());
  assert.equal(first.score, second.score);
  // Repeating a non-matching text between hits must not flip stateful regexes.
  scoreText("A perfectly ordinary market recap");
  assert.equal(scoreText(headline).score, first.score);
});

test("severe negatives are recognised and bounded", () => {
  const hack = scoreText("Bybit hacked: attacker drained the cold wallet");
  assert.ok(hack.signals.some((s) => s.id === "hack" && s.severe));
  assert.ok(hack.score <= -3);

  const stacked = scoreText("Exchange hacked, declares bankruptcy and halts withdrawals amid fraud probe");
  assert.equal(stacked.score, -4, "per-article score is clamped so one headline cannot dominate");
});

test("positive rules score above zero", () => {
  const good = scoreText("Kraken secures MiCA licence and publishes proof of reserves attestation");
  assert.ok(good.score > 0, `expected positive score, got ${good.score}`);
  assert.ok(good.signals.some((s) => s.id === "reserves"));
});

test("context guards cancel inverted matches without muting the real event", () => {
  // Every one of these appeared on the live board as a false positive.
  const cancelled = [
    "Binance 'red teams' its own staff every month to keep hackers out",
    "Kraken resumes withdrawals after scheduled maintenance",
    "SEC drops the case against the exchange",
    "Stablecoin restored its peg within the hour",
  ];
  for (const headline of cancelled) {
    assert.equal(scoreText(headline).score, 0, `expected no signal for: ${headline}`);
  }

  const real = [
    ["Bybit hacked: attacker drained the cold wallet", "hack"],
    ["Exchange suspends all withdrawals", "withdrawal-halt"],
    ["Regulator opens investigation into exchange fraud", "enforcement"],
  ];
  for (const [headline, ruleId] of real) {
    assert.ok(scoreText(headline).signals.some((s) => s.id === ruleId), `expected ${ruleId} for: ${headline}`);
  }
});

test("'delisting' and 'listing' do not cross-trigger", () => {
  assert.ok(scoreText("OKX delists three tokens").signals.some((s) => s.id === "delisting"));
  assert.ok(!scoreText("OKX announces listing of a new token").signals.some((s) => s.id === "delisting"));
});

test("entity matching is word-bounded and handles dotted aliases", () => {
  assert.deepEqual(matchExchanges(article({ title: "Gate.io expands in Europe" })), ["gateio"]);
  assert.deepEqual(matchExchanges(article({ title: "Huobi rebrands operations" })), ["htx"]);
  assert.deepEqual(matchExchanges(article({ title: "A story about binances competitors" })), []);
  assert.deepEqual(matchAssets(article({ title: "Bitcoin and SOL rally" })).sort(), ["BTC", "SOL"]);
  assert.deepEqual(matchAssets(article({ title: "Shares were SOLD in bulk" })), []);
});

test("a statuspage item is attributed to its own venue without naming it", () => {
  const incident = article({
    title: "Withdrawals temporarily suspended",
    sourceId: "status-kraken",
    sourceLabel: "Kraken status",
  });
  assert.deepEqual(matchExchanges(incident), ["kraken"]);
});

test("recency decay halves at the half-life and undated items are not treated as breaking", () => {
  assert.equal(Number(recencyDecay(48).toFixed(6)), 0.5);
  assert.equal(Number(recencyDecay(96).toFixed(6)), 0.25);
  const undated = scoreArticle(article({ publishedAt: null }), NOW);
  assert.equal(Number(undated.decay.toFixed(6)), 0.5);
});

test("bands are driven by negative pressure only — good news cannot cancel a severe event", () => {
  assert.equal(bandFor(3.0, 1), "CRITICAL");
  assert.equal(bandFor(1.0, 1), "ELEVATED");
  assert.equal(bandFor(3.0, 0), "ELEVATED");
  assert.equal(bandFor(1.5, 0), "WATCH");
  assert.equal(bandFor(0.4, 0), "CALM");

  const snapshot = buildNewsRiskSnapshot({
    articles: [
      article({ title: "Binance halts withdrawals after exploit drains hot wallet", link: "https://x.test/1" }),
      article({ title: "Binance publishes proof of reserves attestation", link: "https://x.test/2" }),
      article({ title: "Binance secures regulatory approval and wins approval in new market", link: "https://x.test/3" }),
    ],
    sources: [],
    heldExchangeIds: ["binance"],
    heldAssetSymbols: [],
    now: NOW,
  });
  const binance = snapshot.exchanges.find((e) => e.id === "binance");
  assert.equal(binance.band, "CRITICAL");
  assert.ok(binance.positiveSupport > 0, "good news is still recorded");
  assert.ok(binance.negativePressure > 0);
});

test("held venues sort ahead of unheld ones and held assets drive the asset board", () => {
  const snapshot = buildNewsRiskSnapshot({
    articles: [article({ title: "OKX under investigation over alleged fraud" })],
    sources: [],
    heldExchangeIds: ["kraken"],
    heldAssetSymbols: ["BTC", "USDT"],
    now: NOW,
  });
  assert.equal(snapshot.exchanges[0].id, "kraken", "held venue leads the board even when quiet");
  assert.ok(snapshot.exchanges.find((e) => e.id === "okx").negativePressure > 0);
  assert.deepEqual(snapshot.assets.map((a) => a.id).sort(), ["BTC", "USDT"]);
});

test("a watched venue keeps its row even when there is no news at all", () => {
  const snapshot = buildNewsRiskSnapshot({
    articles: [],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  const pionex = snapshot.exchanges.find((e) => e.id === "pionex");
  assert.ok(pionex, "Pionex is watched, so silence still gets a row");
  assert.equal(pionex.watched, true);
  assert.equal(pionex.held, false);
  assert.equal(pionex.band, "CALM");
});

test("Pionex news is matched and scored like any other venue", () => {
  const snapshot = buildNewsRiskSnapshot({
    articles: [article({ title: "Pionex suspends withdrawals after wallet exploit" })],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  const pionex = snapshot.exchanges.find((e) => e.id === "pionex");
  assert.equal(pionex.band, "CRITICAL");
  assert.equal(pionex.articleCount, 1);
});

test("an unranked venue in the news is no longer filtered off the board", () => {
  // Bitkub is unranked and unheld; before this it could be the top story on
  // Market Pulse while having no row on the exchange board at all.
  const quiet = buildNewsRiskSnapshot({
    articles: [],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  assert.equal(quiet.exchanges.find((e) => e.id === "bitkub"), undefined);

  const loud = buildNewsRiskSnapshot({
    articles: [article({ title: "Thailand's SEC alleges Bitkub concealed a cyberattack" })],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  const bitkub = loud.exchanges.find((e) => e.id === "bitkub");
  assert.ok(bitkub, "a venue in the news earns a row");
  assert.ok(bitkub.negativePressure > 0);
});

test("no feed is a venue's own blog or an unconfigured status page", () => {
  // Pionex's statuspage still serves Statuspage's stock placeholder incident and
  // its blog is marketing; neither may sit behind a real risk badge.
  for (const source of NEWS_SOURCES) {
    assert.ok(
      !/pionex/i.test(source.url),
      `Pionex publishes no usable feed; ${source.url} must not be configured`,
    );
  }
});

test("stale and duplicate articles are dropped", () => {
  const snapshot = buildNewsRiskSnapshot({
    articles: [
      article({ title: "Kraken hacked", link: "https://x.test/dup" }),
      article({ title: "Kraken hacked", link: "https://x.test/dup" }),
      article({ title: "Kraken hacked long ago", link: "https://x.test/old", publishedAt: hoursAgo(24 * 30) }),
    ],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  assert.equal(snapshot.totals.scoredArticles, 1);
});

test("severity decays out of the band once the event goes cold", () => {
  const build = (ageHours) =>
    buildNewsRiskSnapshot({
      articles: [article({ title: "Bitget hacked in wallet exploit", publishedAt: hoursAgo(ageHours) })],
      sources: [],
      heldExchangeIds: [],
      heldAssetSymbols: [],
      now: NOW,
    }).exchanges.find((e) => e.id === "bitget");

  assert.equal(build(2).band, "CRITICAL");
  assert.equal(build(72).band, "ELEVATED", "three days on, a single report no longer justifies CRITICAL");
  assert.equal(build(120).band, "CALM", "one five-day-old report with no follow-up decays out entirely");
});

test("only the headline is scored and attributed, never the summary", () => {
  // A feed summary name-drops the whole market; on live data that attributed a
  // mining pool's bankruptcy to Bitcoin and spread one story across five venues.
  const noisy = article({
    title: "Bitcoin options traders trim their hedges before the Fed meeting",
    summary: "Elsewhere, an exchange was hacked, Kraken halted withdrawals, and OKX faces a lawsuit.",
  });
  const scored = scoreArticle(noisy, NOW);
  assert.equal(scored.score, 0, "nothing in the summary may create a signal");
  assert.deepEqual(scored.exchangeIds, [], "nothing in the summary may attribute a venue");
  assert.deepEqual(scored.assetSymbols, ["BTC"], "the headline still attributes its own subject");
});

test("digests and roundups carry no risk for anyone they mention", () => {
  const digest = scoreArticle(
    article({ title: "Morning Minute: exchange hacked, regulator sues Coinbase" }),
    NOW,
  );
  assert.equal(digest.score, 0);
  assert.deepEqual(digest.signals, []);

  const real = scoreArticle(article({ title: "Regulator sues Coinbase over alleged fraud" }), NOW);
  assert.ok(real.score < 0, "a dedicated story about the same event still counts");
});

test("a future-dated scheduled change is not scored as breaking news", () => {
  const nextWeek = new Date(NOW + 7 * 24 * 3_600_000).toISOString();
  const scheduled = scoreArticle(article({ title: "Perpetual markets closed", publishedAt: nextWeek }), NOW);
  assert.equal(scheduled.scheduled, true);
  assert.ok(scheduled.decay <= 0.5, `scheduled items are capped at half weight, got ${scheduled.decay}`);

  const nowIsh = scoreArticle(article({ title: "Perpetual markets closed", publishedAt: hoursAgo(0) }), NOW);
  assert.ok(nowIsh.decay > scheduled.decay, "a live incident outweighs one announced for next week");

  // A delisting planned two months out must fall out of the window entirely.
  const farOut = buildNewsRiskSnapshot({
    articles: [article({ title: "Token delisting", publishedAt: new Date(NOW + 60 * 24 * 3_600_000).toISOString() })],
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  assert.equal(farOut.totals.scoredArticles, 0);
});

test("a single-token incident loses severity but keeps direction", () => {
  const narrow = scoreArticle(article({ title: "Midnight (NIGHT) Deposits Temporarily Suspended" }), NOW);
  assert.equal(narrow.narrowScope, true);
  assert.ok(narrow.score < 0, "it is still bad news");
  assert.ok(narrow.score >= -2, `weight is capped at 1 per signal, got ${narrow.score}`);
  assert.ok(!narrow.signals.some((s) => s.severe), "one token's deposits are not a venue-wide halt");

  const venueWide = scoreArticle(article({ title: "Exchange suspends all withdrawals" }), NOW);
  assert.ok(venueWide.signals.some((s) => s.severe));
});

test("repeated routine chatter damps harmonically instead of summing", () => {
  const delisting = (n) =>
    article({ title: `Token ${n} Delisting scheduled`, link: `https://x.test/d${n}`, publishedAt: hoursAgo(1) });

  const snapshot = buildNewsRiskSnapshot({
    articles: [1, 2, 3, 4].map((n) => ({ ...delisting(n), title: `Kraken ${delisting(n).title}` })),
    sources: [],
    heldExchangeIds: [],
    heldAssetSymbols: [],
    now: NOW,
  });
  const kraken = snapshot.exchanges.find((e) => e.id === "kraken");
  assert.equal(kraken.articleCount, 4);
  assert.ok(
    kraken.negativePressure < 2.5,
    `four routine delistings must not sum to four points of risk, got ${kraken.negativePressure}`,
  );
  assert.equal(kraken.band, "WATCH", "routine ops chatter is worth a look, not an escalation");
});

test("trending clusters the same story across outlets and ranks by loudness", () => {
  const now = NOW;
  const same = (sourceId, sourceLabel) =>
    scoreArticle(
      article({ title: "Regulator approves spot ETF listing for major asset manager", sourceId, sourceLabel }),
      now,
    );
  const lonely = scoreArticle(article({ title: "Small protocol ships a routine documentation update" }), now);

  const trending = buildTrending([same("coindesk", "CoinDesk"), same("decrypt", "Decrypt"), same("theblock", "The Block"), lonely]);
  assert.equal(trending[0].sourceLabels.length, 3);
  assert.ok(trending[0].heat > trending[trending.length - 1].heat);
});

test("RSS and Atom feeds both parse, with CDATA and entities decoded", () => {
  const rss = `<rss><channel>
    <item>
      <title><![CDATA[Exchange halts withdrawals & deposits]]></title>
      <link>https://news.test/a</link>
      <description>Full &amp; complete</description>
      <pubDate>Sat, 26 Jul 2026 10:00:00 GMT</pubDate>
    </item>
  </channel></rss>`;
  const [item] = parseFeedXml(rss, NEWS_SOURCES[0]);
  assert.equal(item.title, "Exchange halts withdrawals & deposits");
  assert.equal(item.link, "https://news.test/a");
  assert.equal(item.summary, "Full & complete");
  assert.equal(item.publishedAt, "2026-07-26T10:00:00.000Z");

  const atom = `<feed>
    <entry>
      <title>Kraken incident resolved</title>
      <link rel="alternate" href="https://news.test/b"/>
      <summary>All systems operational</summary>
      <updated>2026-07-26T12:30:00Z</updated>
    </entry>
  </feed>`;
  const [entry] = parseFeedXml(atom, NEWS_SOURCES[6]);
  assert.equal(entry.title, "Kraken incident resolved");
  assert.equal(entry.link, "https://news.test/b");
  assert.equal(entry.publishedAt, "2026-07-26T12:30:00.000Z");

  assert.deepEqual(parseFeedXml("<html>not a feed</html>", NEWS_SOURCES[0]), []);
});

test("holdings resolution ignores empty accounts and keeps both legs of a pair", () => {
  assert.deepEqual(
    resolveHeldExchangeIds([
      { platform: "Binance", cash: 10, mv: 0 },
      { platform: "Kraken", cash: 0, mv: 0 },
      { platform: "Manual", cash: 5, mv: 5 },
      { platform: "IBKR", cash: 1, mv: 1 },
    ]).sort(),
    ["binance", "ibkr"],
  );
  assert.deepEqual(resolveHeldAssetSymbols(["BTC-USDT", "SOL-USD", "AAPL", "EURUSD"]).sort(), [
    "AAPL",
    "BTC",
    "SOL",
    "USDT",
  ]);
});

test("every configured feed is a plain https URL with no credential in it", () => {
  for (const source of NEWS_SOURCES) {
    const url = new URL(source.url);
    assert.equal(url.protocol, "https:", `${source.id} must use https`);
    assert.equal(url.search, "", `${source.id} must not carry query parameters`);
    assert.equal(url.username, "");
    assert.equal(url.password, "");
  }
});
