// Seeded, deterministic demo data for Aegis Fund OS. All fictional.

export const FUND = {
  name: "Aegis Global Opportunities Fund I",
  code: "AGOF-I",
  baseCurrency: "USD",
  timezone: "Asia/Bangkok",
  inceptionDate: "2023-04-01",
  administrator: "Meridian Fund Services (Demo)",
  auditor: "KPMG-equivalent (Demo)",
};

export const KPIS = {
  nav: 128_734_512.44,
  navPrev: 127_910_802.1,
  netPnl: 823_710.34,
  dailyReturn: 0.0064,
  mtdReturn: 0.0182,
  ytdReturn: 0.1147,
  cash: 14_205_331.02,
  grossExposure: 0.87,
  netExposure: 0.42,
  drawdown: -0.0231,
  maxDrawdown: -0.0684,
  twr: 0.1147,
  mwr: 0.1063,
  fees: 214_003.12,
  unrealized: 4_120_442.11,
  realized: 3_902_119.55,
};

// Deterministic NAV series
function seededSeries(n: number, start: number, seed: number) {
  let s = seed;
  const rand = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  const arr: { d: string; nav: number; bench: number }[] = [];
  let v = start;
  let b = start;
  const base = new Date("2025-01-02").getTime();
  for (let i = 0; i < n; i++) {
    const drift = (rand() - 0.47) * 0.012;
    const bdrift = (rand() - 0.49) * 0.009;
    v = v * (1 + drift);
    b = b * (1 + bdrift);
    const dt = new Date(base + i * 86_400_000);
    arr.push({
      d: dt.toISOString().slice(0, 10),
      nav: Math.round(v * 100) / 100,
      bench: Math.round(b * 100) / 100,
    });
  }
  return arr;
}

export const NAV_SERIES = seededSeries(200, 115_500_000, 42);

export const MONTHLY_RETURNS = [
  { m: "Jan", r: 0.021 },
  { m: "Feb", r: -0.008 },
  { m: "Mar", r: 0.034 },
  { m: "Apr", r: 0.012 },
  { m: "May", r: -0.019 },
  { m: "Jun", r: 0.027 },
  { m: "Jul", r: 0.041 },
  { m: "Aug", r: -0.014 },
  { m: "Sep", r: 0.006 },
  { m: "Oct", r: 0.018 },
  { m: "Nov", r: 0.009 },
  { m: "Dec", r: null as number | null },
];

export const ALLOCATION_ASSET = [
  { name: "Digital Assets", value: 38 },
  { name: "Global Equities", value: 27 },
  { name: "FX & Rates", value: 14 },
  { name: "Commodities", value: 8 },
  { name: "Cash & Equivalents", value: 13 },
];

export const ALLOCATION_PLATFORM = [
  { name: "Binance Testnet", value: 32 },
  { name: "IBKR Paper", value: 41 },
  { name: "Coinbase Sandbox", value: 14 },
  { name: "Manual Custodian", value: 13 },
];

export const EXPOSURE_STRATEGY = [
  { name: "Systematic Macro", gross: 0.42, net: 0.18 },
  { name: "Digital Momentum", gross: 0.28, net: 0.11 },
  { name: "Cross-Asset Carry", gross: 0.12, net: 0.08 },
  { name: "Vol Overlay", gross: 0.05, net: -0.02 },
];

export const EXPOSURE_CCY = [
  { name: "USD", value: 62 },
  { name: "EUR", value: 11 },
  { name: "JPY", value: 8 },
  { name: "GBP", value: 6 },
  { name: "THB", value: 5 },
  { name: "Other", value: 8 },
];

export type PlatformRow = {
  id: string;
  platform: string;
  alias: string;
  env: "Paper" | "Testnet" | "Sandbox" | "Manual";
  base: string;
  cash: number;
  mv: number;
  status: "Healthy" | "Degraded" | "Stale" | "Disconnected";
  lastSync: string;
  source: string;
};

export const ACCOUNTS: PlatformRow[] = [
  {
    id: "acc-01",
    platform: "Binance",
    alias: "BIN-TESTNET-01",
    env: "Testnet",
    base: "USDT",
    cash: 4_120_331.02,
    mv: 12_004_223.11,
    status: "Healthy",
    lastSync: "2s ago",
    source: "REST + WS",
  },
  {
    id: "acc-02",
    platform: "IBKR",
    alias: "IBKR-PAPER-DU-9821",
    env: "Paper",
    base: "USD",
    cash: 6_710_002.55,
    mv: 41_802_112.87,
    status: "Healthy",
    lastSync: "12s ago",
    source: "TWS Gateway",
  },
  {
    id: "acc-03",
    platform: "Coinbase",
    alias: "CB-SANDBOX-A",
    env: "Sandbox",
    base: "USD",
    cash: 1_902_442.1,
    mv: 8_442_009.09,
    status: "Degraded",
    lastSync: "6m ago",
    source: "Advanced Trade API",
  },
  {
    id: "acc-04",
    platform: "Manual",
    alias: "CUSTODIAN-PB-01",
    env: "Manual",
    base: "USD",
    cash: 1_472_555.35,
    mv: 12_002_113.55,
    status: "Stale",
    lastSync: "14h ago",
    source: "CSV Upload",
  },
  {
    id: "acc-05",
    platform: "Kraken",
    alias: "KRK-DEMO-02",
    env: "Sandbox",
    base: "USD",
    cash: 0,
    mv: 0,
    status: "Disconnected",
    lastSync: "—",
    source: "Not connected",
  },
];

export const LEDGER = Array.from({ length: 32 }).map((_, i) => {
  const sides: ("DR" | "CR")[] = ["DR", "CR"];
  const side = sides[i % 2];
  const amt = 1000 + ((i * 9301) % 87_000);
  return {
    id: `EVT-2025-${String(9820 - i).padStart(5, "0")}`,
    ts: `2025-11-${String(15 - (i % 14)).padStart(2, "0")} ${String(9 + (i % 8)).padStart(2, "0")}:${String((i * 7) % 60).padStart(2, "0")}:12`,
    account: [
      "1100-Cash-USD",
      "1200-Positions-Crypto",
      "1210-Positions-Equity",
      "4100-Trading-PnL",
      "5100-Fees",
      "2100-Payables",
    ][i % 6],
    dr: side === "DR" ? amt : 0,
    cr: side === "CR" ? amt : 0,
    ccy: ["USD", "USD", "USDT", "EUR"][i % 4],
    source: ["IBKR", "Binance", "Coinbase", "Manual"][i % 4],
    ref: `TRD-${100_000 + i * 13}`,
    status: (i % 11 === 0 ? "Pending" : "Posted") as "Posted" | "Pending",
  };
});

export const RECON_STAGES = ["Imported", "Matched", "Exception", "Reviewed", "Locked"] as const;

export const RECON_METRICS = {
  matchRate: 0.9843,
  openBreaks: 7,
  agedBreaks: 2,
  unresolvedValue: 128_442.55,
};

export const RECON_BREAKS = [
  {
    id: "BRK-2201",
    severity: "High" as const,
    source: "Binance",
    sourceVal: 122_004.22,
    ledgerVal: 121_996.11,
    delta: 8.11,
    reason: "Timing",
    owner: "N. Suriya",
    age: "2d",
    status: "Exception" as const,
  },
  {
    id: "BRK-2202",
    severity: "Medium" as const,
    source: "IBKR",
    sourceVal: 44_120.0,
    ledgerVal: 44_119.55,
    delta: 0.45,
    reason: "FX rounding",
    owner: "T. Anand",
    age: "6h",
    status: "Reviewed" as const,
  },
  {
    id: "BRK-2203",
    severity: "Low" as const,
    source: "Coinbase",
    sourceVal: 8_211.1,
    ledgerVal: 8_202.3,
    delta: 8.8,
    reason: "Fee schedule",
    owner: "L. Chan",
    age: "1h",
    status: "Matched" as const,
  },
  {
    id: "BRK-2204",
    severity: "High" as const,
    source: "Manual",
    sourceVal: 22_400.0,
    ledgerVal: 0.0,
    delta: 22_400.0,
    reason: "Missing wire",
    owner: "N. Suriya",
    age: "4d",
    status: "Exception" as const,
  },
  {
    id: "BRK-2205",
    severity: "Medium" as const,
    source: "Binance",
    sourceVal: 3_140.55,
    ledgerVal: 3_130.1,
    delta: 10.45,
    reason: "Corporate action",
    owner: "P. Wong",
    age: "12h",
    status: "Exception" as const,
  },
];

export const FX_VALUATION = {
  reportingCurrency: "USD",
  asOf: "2025-11-14 09:42 ICT",
  status: "Approved" as const,
  source: "Approved valuation snapshot",
  totalBaseValue: 128_734_512.44,
  rates: [
    { pair: "EUR/USD", rate: 1.0842, status: "Approved" as const },
    { pair: "GBP/USD", rate: 1.2684, status: "Approved" as const },
    { pair: "USD/JPY", rate: 154.22, status: "Approved" as const },
    { pair: "THB/USD", rate: 0.0281, status: "Approved" as const },
  ],
};

export const PERSISTED_EXCEPTIONS = [
  {
    id: "EXC-2025-001",
    asset: "EUR",
    reason: "missing FX rate",
    owner: "Niran C. (Ops)",
    status: "Open" as const,
    source: "SQLite exception store",
  },
  {
    id: "EXC-2025-002",
    asset: "USDT",
    reason: "balance differs from ledger inventory or reporting cash",
    owner: "Niran C. (Ops)",
    status: "Resolved" as const,
    source: "SQLite exception store",
    approvedBy: "Preecha S. (Risk)",
  },
];

export const POSITIONS = [
  {
    sym: "BTC-USDT",
    qty: 42.5,
    px: 68_412.1,
    mv: 2_907_514.25,
    upnl: 118_442.1,
    rpnl: 42_100.55,
    fx: 0,
    src: "Binance",
  },
  {
    sym: "ETH-USDT",
    qty: 810.0,
    px: 3_412.55,
    mv: 2_764_165.5,
    upnl: -22_004.1,
    rpnl: 18_402.2,
    fx: 0,
    src: "Binance",
  },
  {
    sym: "AAPL",
    qty: 12_000,
    px: 224.32,
    mv: 2_691_840.0,
    upnl: 74_112.0,
    rpnl: 12_004.22,
    fx: 0,
    src: "IBKR",
  },
  {
    sym: "MSFT",
    qty: 6_500,
    px: 431.18,
    mv: 2_802_670.0,
    upnl: 61_402.3,
    rpnl: 0,
    fx: 0,
    src: "IBKR",
  },
  {
    sym: "NVDA",
    qty: 3_200,
    px: 132.44,
    mv: 423_808.0,
    upnl: -14_002.1,
    rpnl: 90_120.44,
    fx: 0,
    src: "IBKR",
  },
  {
    sym: "EURUSD",
    qty: 5_000_000,
    px: 1.0842,
    mv: 5_421_000.0,
    upnl: 8_400.0,
    rpnl: 3_200.0,
    fx: 8_400.0,
    src: "IBKR",
  },
  {
    sym: "SOL-USD",
    qty: 1_200,
    px: 178.3,
    mv: 213_960.0,
    upnl: 12_400.1,
    rpnl: 4_002.11,
    fx: 0,
    src: "Coinbase",
  },
];

export const RISK_LIMITS = [
  {
    name: "Gross Exposure",
    cur: 0.87,
    soft: 1.0,
    hard: 1.25,
    status: "OK" as const,
    trend: [0.72, 0.78, 0.81, 0.83, 0.85, 0.87],
  },
  {
    name: "Net Exposure",
    cur: 0.42,
    soft: 0.6,
    hard: 0.8,
    status: "OK" as const,
    trend: [0.3, 0.34, 0.38, 0.4, 0.41, 0.42],
  },
  {
    name: "Concentration (single name)",
    cur: 0.093,
    soft: 0.08,
    hard: 0.12,
    status: "Warn" as const,
    trend: [0.06, 0.07, 0.08, 0.085, 0.09, 0.093],
  },
  {
    name: "Daily Loss",
    cur: 0.0064,
    soft: -0.01,
    hard: -0.02,
    status: "OK" as const,
    trend: [-0.003, -0.001, 0.002, 0.004, 0.005, 0.006],
  },
  {
    name: "Max Drawdown",
    cur: -0.0684,
    soft: -0.1,
    hard: -0.15,
    status: "OK" as const,
    trend: [-0.02, -0.03, -0.05, -0.06, -0.065, -0.068],
  },
  {
    name: "Leverage",
    cur: 1.32,
    soft: 1.5,
    hard: 2.0,
    status: "OK" as const,
    trend: [1.1, 1.15, 1.22, 1.28, 1.3, 1.32],
  },
  {
    name: "Stale Prices",
    cur: 3,
    soft: 5,
    hard: 10,
    status: "OK" as const,
    trend: [1, 2, 2, 3, 3, 3],
  },
];

export const STRESS = [
  { scenario: "BTC −10%", pnl: -412_003, pct: -0.0032 },
  { scenario: "Global Equities −5%", pnl: -684_212, pct: -0.0053 },
  { scenario: "USD/THB +3%", pnl: -122_004, pct: -0.0009 },
  { scenario: "Binance unavailable 24h", pnl: -84_442, pct: -0.0007 },
  { scenario: "Combined tail", pnl: -1_402_881, pct: -0.0109 },
];

export const PAPER_ORDERS = [
  {
    id: "PO-88201",
    sym: "BTC-USDT",
    side: "BUY",
    qty: 4.5,
    limit: 68_100.0,
    maker: "PM (Somchai)",
    checker: null,
    checks: "OK",
    status: "Awaiting Checker",
  },
  {
    id: "PO-88202",
    sym: "AAPL",
    side: "SELL",
    qty: 2_000,
    limit: 224.0,
    maker: "PM (Somchai)",
    checker: "COO (Anong)",
    checks: "OK",
    status: "Approved",
  },
  {
    id: "PO-88203",
    sym: "ETH-USDT",
    side: "BUY",
    qty: 200,
    limit: 3_450.0,
    maker: "PM (Somchai)",
    checker: null,
    checks: "Breach: concentration",
    status: "Blocked",
  },
];

export const REPORTS_DATA = [
  {
    name: "Monthly Factsheet — Nov 2025",
    period: "Nov 2025",
    status: "Draft",
    version: "v0.3",
    by: "COO (Anong)",
    reviewed: "—",
    checksum: "9f2a…c14e",
  },
  {
    name: "Performance Tear Sheet — YTD 2025",
    period: "YTD 2025",
    status: "Reviewed",
    version: "v1.2",
    by: "PM (Somchai)",
    reviewed: "Auditor (Read-only)",
    checksum: "b83c…7291",
  },
  {
    name: "Exposure Report — 2025-11-14",
    period: "2025-11-14",
    status: "Final",
    version: "v1.0",
    by: "Risk (Preecha)",
    reviewed: "COO (Anong)",
    checksum: "42df…0a5b",
  },
  {
    name: "Reconciliation Pack — Nov W2",
    period: "Nov W2 2025",
    status: "Final",
    version: "v1.0",
    by: "Ops (Niran)",
    reviewed: "COO (Anong)",
    checksum: "1ce0…88fa",
  },
  {
    name: "Audit Evidence Pack — Q3 2025",
    period: "Q3 2025",
    status: "Locked",
    version: "v2.0",
    by: "COO (Anong)",
    reviewed: "Auditor (Read-only)",
    checksum: "77aa…dd21",
  },
];

const AUDIT_EVENT_START_MS = Date.UTC(2025, 10, 15, 17, 45, 4);
const AUDIT_EVENT_INTERVAL_MS = 53 * 60 * 1000;

export const AUDIT_EVENTS = Array.from({ length: 22 }).map((_, i) => ({
  id: `AUD-${String(50021 - i).padStart(6, "0")}`,
  // The fixture is append-only: newest event first, then a steady historic sequence.
  ts: new Date(AUDIT_EVENT_START_MS - i * AUDIT_EVENT_INTERVAL_MS)
    .toISOString()
    .slice(0, 19)
    .replace("T", " "),
  actor: ["PM (Somchai)", "COO (Anong)", "Risk (Preecha)", "Ops (Niran)", "Auditor (Read-only)"][
    i % 5
  ],
  action: [
    "nav.lock.attempt",
    "recon.approve",
    "order.paper.submit",
    "limit.update",
    "report.generate",
    "account.sync",
  ][i % 6],
  entity: [
    "NAV-2025-11-14",
    "BRK-2202",
    "PO-88201",
    "LIM-CONC",
    "RPT-EXP-1114",
    "ACC-IBKR-DU-9821",
  ][i % 6],
  ip: "10.42." + (10 + (i % 40)) + "." + ((i * 7) % 255),
  hash: `${(0x9f2a + i).toString(16)}…${(0xc14e - i).toString(16)}`,
}));
