import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney, fmtPct, fmtNum } from "@/components/metric-card";
import { DemoTag, StatusDot } from "@/components/demo-tag";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import {
  KPIS,
  NAV_SERIES,
  ALLOCATION_ASSET,
  ALLOCATION_PLATFORM,
  EXPOSURE_STRATEGY,
  EXPOSURE_CCY,
  ACCOUNTS,
} from "@/lib/demo-data";
import { AlertTriangle, CheckCircle2, Clock, Download, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Overview · Aegis Fund OS" },
      {
        name: "description",
        content: "Executive overview of NAV, exposure, control posture, and platform health.",
      },
    ],
  }),
  component: Overview,
});

const CHART_COLORS = [
  "oklch(0.72 0.11 205)",
  "oklch(0.66 0.13 155)",
  "oklch(0.78 0.15 78)",
  "oklch(0.65 0.15 300)",
  "oklch(0.72 0.09 30)",
];

function Overview() {
  const [range, setRange] = useState<"1M" | "3M" | "YTD" | "1Y">("YTD");
  const [showBench, setShowBench] = useState(true);
  const [allocTab, setAllocTab] = useState<"asset" | "platform">("asset");
  const rangeMap = { "1M": 22, "3M": 66, YTD: 140, "1Y": 200 };
  const series = NAV_SERIES.slice(-rangeMap[range]);
  const allocData = allocTab === "asset" ? ALLOCATION_ASSET : ALLOCATION_PLATFORM;

  return (
    <AppShell>
      <PageHeader
        kicker="Executive Overview · 2025-11-14"
        title="Today's operational posture"
        subtitle="Provisional NAV, control queue, and platform health across paper/testnet adapters."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => toast.success("Snapshot exported (demo)")}
            >
              <Download className="h-3.5 w-3.5" /> Export snapshot
            </Button>
            <Button
              size="sm"
              onClick={() =>
                toast("NAV close initiated (demo) — checklist opens in Portfolio & NAV")
              }
            >
              Begin NAV close
            </Button>
          </>
        }
      />

      <div className="p-6 space-y-6">
        {/* KPI grid */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
          <MetricCard
            label="NAV"
            value={fmtMoney(KPIS.nav, "USD", 0)}
            sub={`Δ ${fmtMoney(KPIS.nav - KPIS.navPrev, "USD", 0)} vs prev`}
            tone="default"
            className="lg:col-span-2"
          />
          <MetricCard
            label="Net P&L (D)"
            value={fmtMoney(KPIS.netPnl, "USD", 0)}
            sub="Trade date"
            tone="positive"
          />
          <MetricCard
            label="Available Cash"
            value={fmtMoney(KPIS.cash, "USD", 0)}
            sub="Across venues"
          />
          <MetricCard
            label="Drawdown"
            value={fmtPct(KPIS.drawdown)}
            sub={`Max ${fmtPct(KPIS.maxDrawdown)}`}
            tone="negative"
          />
          <MetricCard label="Daily" value={fmtPct(KPIS.dailyReturn)} tone="positive" />
          <MetricCard label="MTD" value={fmtPct(KPIS.mtdReturn)} tone="positive" />
          <MetricCard label="YTD" value={fmtPct(KPIS.ytdReturn)} tone="positive" />
          <MetricCard
            label="Gross Exp."
            value={fmtPct(KPIS.grossExposure, 1)}
            sub="of NAV"
            tone="warning"
          />
          <MetricCard label="Net Exp." value={fmtPct(KPIS.netExposure, 1)} sub="of NAV" />
        </div>

        {/* NAV chart + allocation */}
        <div className="grid gap-6 xl:grid-cols-3">
          <Panel
            className="xl:col-span-2"
            title="NAV & cumulative return"
            subtitle="Fund vs custom global benchmark (60/40 equity/bonds proxy)"
            actions={
              <div className="flex items-center gap-2">
                <Toggle
                  size="sm"
                  pressed={showBench}
                  onPressedChange={setShowBench}
                  aria-label="Toggle benchmark overlay"
                  className="h-7 px-2 text-[11px] data-[state=on]:bg-primary/15 data-[state=on]:text-primary"
                >
                  Benchmark
                </Toggle>
                <Tabs value={range} onValueChange={(v) => setRange(v as never)}>
                  <TabsList className="h-7">
                    {(["1M", "3M", "YTD", "1Y"] as const).map((r) => (
                      <TabsTrigger key={r} value={r} className="h-6 text-[11px] px-2.5">
                        {r}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </div>
            }
          >
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="navG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.72 0.11 205)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="oklch(0.72 0.11 205)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    stroke="oklch(0.32 0.025 258)"
                    strokeDasharray="2 3"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="d"
                    tick={{ fill: "oklch(0.68 0.02 250)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    tick={{ fill: "oklch(0.68 0.02 250)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={70}
                    tickFormatter={(v) => `${(v / 1_000_000).toFixed(1)}M`}
                  />
                  <RTooltip
                    contentStyle={{
                      background: "oklch(0.22 0.028 258)",
                      border: "1px solid oklch(0.32 0.025 258)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "oklch(0.86 0.012 240)" }}
                    formatter={(v: number, k: string) => [
                      fmtMoney(v),
                      k === "nav" ? "NAV" : "Benchmark",
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="nav"
                    stroke="oklch(0.72 0.11 205)"
                    strokeWidth={2}
                    fill="url(#navG)"
                  />
                  {showBench && (
                    <Area
                      type="monotone"
                      dataKey="bench"
                      stroke="oklch(0.68 0.02 250)"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      fill="none"
                    />
                  )}
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-primary" /> Fund NAV
              </span>
              {showBench && (
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-muted-foreground/60" /> Benchmark (60/40)
                </span>
              )}
              <span className="ml-2 text-[10px] uppercase tracking-wider">
                Window: {range} · {series.length}d
              </span>
              <DemoTag className="ml-auto" />
            </div>
          </Panel>

          <Panel
            title="Allocation"
            subtitle={allocTab === "asset" ? "By asset class · % of NAV" : "By platform · % of NAV"}
            actions={
              <Tabs value={allocTab} onValueChange={(v) => setAllocTab(v as never)}>
                <TabsList className="h-7">
                  <TabsTrigger value="asset" className="h-6 text-[11px] px-2.5">
                    Asset
                  </TabsTrigger>
                  <TabsTrigger value="platform" className="h-6 text-[11px] px-2.5">
                    Platform
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            }
          >
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={allocData}
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    stroke="oklch(0.19 0.028 258)"
                  >
                    {allocData.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <RTooltip
                    contentStyle={{
                      background: "oklch(0.22 0.028 258)",
                      border: "1px solid oklch(0.32 0.025 258)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(v: number) => `${v}%`}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="mt-2 space-y-1.5 text-xs">
              {allocData.map((a, i) => (
                <li key={a.name} className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-sm shrink-0"
                    style={{ background: CHART_COLORS[i] }}
                  />
                  <span className="truncate">{a.name}</span>
                  <span className="ml-auto num text-muted-foreground">{a.value}%</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        {/* Exposure + Platform Health */}
        <div className="grid gap-6 xl:grid-cols-3">
          <Panel title="Exposure by strategy" subtitle="Gross vs net" className="xl:col-span-2">
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={EXPOSURE_STRATEGY}
                  layout="vertical"
                  margin={{ left: 20, right: 20, top: 8, bottom: 0 }}
                >
                  <CartesianGrid
                    stroke="oklch(0.32 0.025 258)"
                    strokeDasharray="2 3"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{ fill: "oklch(0.68 0.02 250)", fontSize: 10 }}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: "oklch(0.86 0.012 240)", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={140}
                  />
                  <RTooltip
                    contentStyle={{
                      background: "oklch(0.22 0.028 258)",
                      border: "1px solid oklch(0.32 0.025 258)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(v: number) => fmtPct(v, 1)}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: "oklch(0.68 0.02 250)" }} />
                  <Bar
                    dataKey="gross"
                    name="Gross"
                    fill="oklch(0.72 0.11 205)"
                    radius={[0, 3, 3, 0]}
                  />
                  <Bar dataKey="net" name="Net" fill="oklch(0.66 0.13 155)" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Currency exposure" subtitle="% of NAV">
            <ul className="space-y-2.5">
              {EXPOSURE_CCY.map((c, i) => (
                <li key={c.name} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">{c.name}</span>
                    <span className="num text-muted-foreground">{c.value}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-accent/60 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${c.value}%`,
                        background: CHART_COLORS[i % CHART_COLORS.length],
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        {/* Platform health & exceptions */}
        <div className="grid gap-6 xl:grid-cols-3">
          <Panel
            title="Platform health"
            subtitle="Adapters, freshness, source"
            className="xl:col-span-2"
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular">
                <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b border-border/60">
                    <th className="text-left py-2 pr-4 font-medium">Platform</th>
                    <th className="text-left py-2 pr-4 font-medium">Alias</th>
                    <th className="text-left py-2 pr-4 font-medium">Env</th>
                    <th className="text-right py-2 pr-4 font-medium">Cash</th>
                    <th className="text-right py-2 pr-4 font-medium">Mkt Value</th>
                    <th className="text-left py-2 pr-4 font-medium">Status</th>
                    <th className="text-left py-2 pr-4 font-medium">Last sync</th>
                  </tr>
                </thead>
                <tbody>
                  {ACCOUNTS.map((a) => {
                    const needsIntegrationAttention =
                      a.status === "Degraded" || a.status === "Disconnected";
                    return (
                      <tr key={a.id} className="border-b border-border/40 hover:bg-accent/30">
                        <td className="py-2 pr-4 font-medium">{a.platform}</td>
                        <td className="py-2 pr-4 text-muted-foreground font-mono text-xs">
                          {a.alias}
                        </td>
                        <td className="py-2 pr-4">
                          <Badge variant="outline" className="text-[10px] uppercase">
                            {a.env}
                          </Badge>
                        </td>
                        <td className="py-2 pr-4 text-right num">{fmtMoney(a.cash, "USD", 0)}</td>
                        <td className="py-2 pr-4 text-right num">{fmtMoney(a.mv, "USD", 0)}</td>
                        <td className="py-2 pr-4">
                          {needsIntegrationAttention ? (
                            <Link
                              to="/integrations"
                              className="inline-flex items-center gap-1.5 rounded-sm text-xs underline-offset-4 hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              aria-label={`Open Integrations for ${a.platform}, currently ${a.status}`}
                            >
                              <StatusDot tone={a.status === "Degraded" ? "warning" : "muted"} />
                              {a.status}
                            </Link>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <StatusDot
                                tone={
                                  a.status === "Healthy"
                                    ? "positive"
                                    : a.status === "Degraded"
                                      ? "warning"
                                      : a.status === "Stale"
                                        ? "warning"
                                        : "muted"
                                }
                              />
                              {a.status}
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground num">
                          {a.lastSync}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Control queue" subtitle="Exceptions & SLA">
            <ul className="space-y-2">
              {[
                {
                  sev: "warning",
                  title: "3 reconciliation exceptions",
                  owner: "N. Suriya",
                  age: "2d · SLA 3d",
                  icon: AlertTriangle,
                },
                {
                  sev: "warning",
                  title: "Coinbase adapter degraded",
                  owner: "Ops",
                  age: "6m",
                  icon: AlertTriangle,
                },
                {
                  sev: "info",
                  title: "NAV close awaiting reviewer",
                  owner: "COO",
                  age: "2h · SLA 4h",
                  icon: Clock,
                },
                {
                  sev: "positive",
                  title: "FX rates ingested",
                  owner: "System",
                  age: "12m",
                  icon: CheckCircle2,
                },
                {
                  sev: "positive",
                  title: "Risk limits within band",
                  owner: "Risk",
                  age: "1h",
                  icon: ShieldCheck,
                },
              ].map((c, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2.5 rounded-md border border-border/60 bg-background/40 p-2.5"
                >
                  <c.icon
                    className={`h-4 w-4 mt-0.5 shrink-0 ${c.sev === "warning" ? "text-warning" : c.sev === "positive" ? "text-positive" : "text-info"}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm truncate">{c.title}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {c.owner} · {c.age}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        {/* Close timeline + posture */}
        <div className="grid gap-6 xl:grid-cols-3">
          <Panel title="Recent close timeline" className="xl:col-span-2">
            <ol className="relative border-l border-border/60 ml-2 space-y-4">
              {[
                {
                  t: "2025-11-14 08:04 ICT",
                  label: "Ingestion complete",
                  note: "All adapters returned prices & positions",
                  tone: "positive",
                },
                {
                  t: "2025-11-14 08:22 ICT",
                  label: "Ledger posted",
                  note: `${fmtNum(482)} entries · trial balance in balance`,
                  tone: "positive",
                },
                {
                  t: "2025-11-14 09:10 ICT",
                  label: "Reconciliation ran",
                  note: "98.4% matched · 7 exceptions raised",
                  tone: "warning",
                },
                {
                  t: "2025-11-14 09:41 ICT",
                  label: "NAV computed (provisional)",
                  note: `${fmtMoney(KPIS.nav)} · awaiting reviewer`,
                  tone: "info",
                },
                { t: "—", label: "NAV lock", note: "Pending Four-Eyes approval", tone: "muted" },
              ].map((e, i) => (
                <li key={i} className="ml-4">
                  <div
                    className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border border-background ${e.tone === "positive" ? "bg-positive" : e.tone === "warning" ? "bg-warning" : e.tone === "info" ? "bg-info" : "bg-muted-foreground/50"}`}
                  />
                  <div className="text-[11px] text-muted-foreground num">{e.t}</div>
                  <div className="text-sm font-medium">{e.label}</div>
                  <div className="text-xs text-muted-foreground">{e.note}</div>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel title="Today's control posture">
            <div className="space-y-3 text-sm leading-relaxed">
              <p className="text-muted-foreground">
                Fund is trading within all soft limits. One concentration warning on a single-name
                equity is under review by risk. Coinbase sandbox adapter is degraded; positions are
                marked stale and excluded from provisional NAV until reconnected.{" "}
                <span className="text-foreground">สถานะโดยรวม: อยู่ในกรอบการควบคุม</span>.
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md border border-positive/30 bg-positive/5 px-2.5 py-2">
                  <div className="text-positive font-medium">Data freshness</div>
                  <div className="text-muted-foreground">3 of 4 adapters fresh</div>
                </div>
                <div className="rounded-md border border-warning/30 bg-warning/5 px-2.5 py-2">
                  <div className="text-warning font-medium">Open breaks</div>
                  <div className="text-muted-foreground">7 · 2 aged &gt; 24h</div>
                </div>
                <div className="rounded-md border border-info/30 bg-info/5 px-2.5 py-2">
                  <div className="text-info font-medium">NAV state</div>
                  <div className="text-muted-foreground">Provisional</div>
                </div>
                <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-2">
                  <div className="font-medium">Approvals</div>
                  <div className="text-muted-foreground">1 pending reviewer</div>
                </div>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
