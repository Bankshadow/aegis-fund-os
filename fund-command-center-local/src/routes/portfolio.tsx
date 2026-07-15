import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useEffect } from "react";
import { useServerFn } from "@tanstack/react-start";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney, fmtPct, fmtNum } from "@/components/metric-card";
import { DemoTag } from "@/components/demo-tag";
import { KPIS, POSITIONS, MONTHLY_RETURNS, NAV_SERIES, FX_VALUATION } from "@/lib/demo-data";
import { evaluateDailyClose } from "@/lib/daily-close";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Lock, CheckCircle2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { getOperationsSnapshot } from "@/lib/operations.functions";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip as RTooltip,
} from "recharts";

export const Route = createFileRoute("/portfolio")({
  head: () => ({ meta: [{ title: "Portfolio & NAV · Aegis Fund OS" }] }),
  component: PortfolioPage,
});

function heatColor(r: number | null) {
  if (r === null) return "bg-muted/40 text-muted-foreground";
  const abs = Math.min(Math.abs(r) * 20, 1);
  if (r > 0) return `text-positive-foreground`;
  return `text-destructive-foreground`;
}
function heatStyle(r: number | null): React.CSSProperties {
  if (r === null) return {};
  const abs = Math.min(Math.abs(r) * 25, 0.85);
  const base = r >= 0 ? "oklch(0.66 0.13 155" : "oklch(0.58 0.19 25";
  return { background: `${base} / ${abs.toFixed(2)})` };
}

function PortfolioPage() {
  const readOperations = useServerFn(getOperationsSnapshot);
  const [operations, setOperations] = useState<Awaited<ReturnType<typeof getOperationsSnapshot>> | null>(null);
  useEffect(() => { void readOperations().then(setOperations).catch(() => setOperations(null)); }, [readOperations]);
  const fxSnapshot = operations?.fx ?? FX_VALUATION;
  const [lockOpen, setLockOpen] = useState(false);
  const [checks, setChecks] = useState({
    data: true,
    prices: true,
    recon: false,
    fx: true,
    fees: true,
  });
  const [reviewer, setReviewer] = useState<string>("");
  const [navState, setNavState] = useState<"Provisional" | "Locked">("Provisional");
  const MAKER = "Anong K. (COO)";
  const closeDecision = evaluateDailyClose({ state: navState, maker: MAKER, reviewer, checks });
  const canLock = closeDecision.canLock;

  const totals = POSITIONS.reduce(
    (s, p) => ({
      mv: s.mv + p.mv,
      upnl: s.upnl + p.upnl,
      rpnl: s.rpnl + p.rpnl,
      fx: s.fx + p.fx,
    }),
    { mv: 0, upnl: 0, rpnl: 0, fx: 0 },
  );

  return (
    <AppShell>
      <PageHeader
        kicker="NAV Close · 2025-11-14"
        title="Portfolio & NAV"
        subtitle="Positions, performance, and the close checklist. NAV states: Provisional → Clean → Locked."
        actions={
          <>
            <Badge
              variant="outline"
              className={`uppercase tracking-wider ${navState === "Locked" ? "text-positive border-positive/40 bg-positive/10" : "text-info border-info/40 bg-info/10"}`}
            >
              {navState}
            </Badge>
            {navState === "Locked" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setNavState("Provisional");
                  setReviewer("");
                  toast("NAV unlocked (demo)");
                }}
              >
                <Lock className="h-3.5 w-3.5" /> Unlock (demo)
              </Button>
            ) : (
              <Button size="sm" onClick={() => setLockOpen(true)}>
                <Lock className="h-3.5 w-3.5" /> Lock NAV…
              </Button>
            )}
          </>
        }
      />

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="NAV" value={fmtMoney(KPIS.nav)} sub="Provisional" />
          <MetricCard label="TWR YTD" value={fmtPct(KPIS.twr)} tone="positive" />
          <MetricCard label="MWR YTD" value={fmtPct(KPIS.mwr)} tone="positive" />
          <MetricCard label="Unrealized P&L" value={fmtMoney(KPIS.unrealized)} tone="positive" />
          <MetricCard label="Realized P&L" value={fmtMoney(KPIS.realized)} tone="positive" />
          <MetricCard label="Fees" value={fmtMoney(KPIS.fees)} sub="Mgmt + perf accrual" />
        </div>

        <Panel title="FX valuation" subtitle={`Reporting currency ${fxSnapshot.reportingCurrency} · ${operations?.source === "persisted_snapshot" ? "Persisted snapshot" : FX_VALUATION.source}`}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div>
              <div className="text-xs text-muted-foreground">Valuation snapshot</div>
              <div className="num text-lg font-semibold">{fmtMoney(fxSnapshot.totalBaseValue, fxSnapshot.reportingCurrency, 2)}</div>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <Badge variant="outline" className={fxSnapshot.status === "Approved" ? "text-positive border-positive/40 bg-positive/10" : "text-warning border-warning/40 bg-warning/10"}>{fxSnapshot.status}</Badge>
              <div className="mt-1">As of {fxSnapshot.asOf}</div>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {fxSnapshot.rates.map((fx) => (
              <div key={fx.pair} className="rounded-md border border-border/60 bg-background/40 p-3">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{fx.pair}</span><span className="text-positive">{fx.status}</span>
                </div>
                <div className="num mt-1 text-sm font-semibold">{fx.rate.toFixed(4)}</div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="grid gap-6 xl:grid-cols-3">
          <Panel title="NAV curve" className="xl:col-span-2">
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={NAV_SERIES.slice(-90)}
                  margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="navG2" x1="0" y1="0" x2="0" y2="1">
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
                    formatter={(v: number) => fmtMoney(v)}
                  />
                  <Area
                    type="monotone"
                    dataKey="nav"
                    stroke="oklch(0.72 0.11 205)"
                    strokeWidth={2}
                    fill="url(#navG2)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Drawdown" subtitle="Current & max">
            <div className="space-y-3">
              <div>
                <div className="text-[11px] uppercase text-muted-foreground tracking-wider">
                  Current
                </div>
                <div className="num text-2xl font-semibold text-warning">
                  {fmtPct(KPIS.drawdown)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase text-muted-foreground tracking-wider">
                  Max (rolling 1Y)
                </div>
                <div className="num text-2xl font-semibold text-destructive">
                  {fmtPct(KPIS.maxDrawdown)}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase text-muted-foreground tracking-wider">
                  Recovery
                </div>
                <div className="num text-sm">14 trading days (median)</div>
              </div>
            </div>
          </Panel>
        </div>

        <Panel title="Positions" subtitle="As of 2025-11-14 close (provisional)">
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Symbol</th>
                  <th className="text-right py-2 pr-4 font-medium">Quantity</th>
                  <th className="text-right py-2 pr-4 font-medium">Price</th>
                  <th className="text-right py-2 pr-4 font-medium">Market value</th>
                  <th className="text-right py-2 pr-4 font-medium">Unrealized</th>
                  <th className="text-right py-2 pr-4 font-medium">Realized</th>
                  <th className="text-right py-2 pr-4 font-medium">FX impact</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {POSITIONS.map((p) => (
                  <tr key={p.sym} className="border-b border-border/40 hover:bg-accent/30">
                    <td className="py-2 pr-4 font-mono font-medium">{p.sym}</td>
                    <td className="py-2 pr-4 text-right num">
                      {fmtNum(p.qty, p.qty < 1000 ? 1 : 0)}
                    </td>
                    <td className="py-2 pr-4 text-right num">{fmtMoney(p.px, "USD", 2)}</td>
                    <td className="py-2 pr-4 text-right num font-medium">
                      {fmtMoney(p.mv, "USD", 0)}
                    </td>
                    <td
                      className={`py-2 pr-4 text-right num ${p.upnl >= 0 ? "text-positive" : "text-destructive"}`}
                    >
                      {fmtMoney(p.upnl, "USD", 0)}
                    </td>
                    <td className="py-2 pr-4 text-right num">{fmtMoney(p.rpnl, "USD", 0)}</td>
                    <td className="py-2 pr-4 text-right num text-muted-foreground">
                      {p.fx ? fmtMoney(p.fx, "USD", 0) : "—"}
                    </td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground">{p.src}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border/70 font-semibold">
                  <td className="py-2 pr-4">Total</td>
                  <td />
                  <td />
                  <td className="py-2 pr-4 text-right num">{fmtMoney(totals.mv, "USD", 0)}</td>
                  <td
                    className={`py-2 pr-4 text-right num ${totals.upnl >= 0 ? "text-positive" : "text-destructive"}`}
                  >
                    {fmtMoney(totals.upnl, "USD", 0)}
                  </td>
                  <td className="py-2 pr-4 text-right num">{fmtMoney(totals.rpnl, "USD", 0)}</td>
                  <td className="py-2 pr-4 text-right num text-muted-foreground">
                    {fmtMoney(totals.fx, "USD", 0)}
                  </td>
                  <td />
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="grid gap-6 xl:grid-cols-3">
          <Panel title="Monthly returns" subtitle="2025 · vs benchmark" className="xl:col-span-2">
            <div className="grid grid-cols-6 md:grid-cols-12 gap-1.5">
              {MONTHLY_RETURNS.map((m) => (
                <div
                  key={m.m}
                  className="rounded-md border border-border/50 p-2 text-center"
                  style={heatStyle(m.r)}
                >
                  <div className={`text-[10px] uppercase tracking-wider ${heatColor(m.r)}`}>
                    {m.m}
                  </div>
                  <div className={`num text-xs font-semibold ${heatColor(m.r)}`}>
                    {m.r === null ? "—" : fmtPct(m.r)}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                YTD total <span className="text-foreground num">{fmtPct(KPIS.ytdReturn)}</span> vs
                bench <span className="text-foreground num">+6.20%</span>
              </span>
              <DemoTag />
            </div>
          </Panel>

          <Panel title="Close checklist" subtitle="All items required to lock">
            <ul className="space-y-2 text-sm">
              {(
                [
                  ["data", "Data freshness — all adapters"],
                  ["prices", "Pricing completeness (0 stale)"],
                  ["recon", "Reconciliation zero unresolved"],
                  ["fx", "FX rates ingested"],
                  ["fees", "Fee accruals posted"],
                ] as const
              ).map(([k, label]) => (
                <li
                  key={k}
                  className="flex items-start gap-2.5 rounded-md border border-border/60 bg-background/40 p-2.5"
                >
                  <Checkbox
                    checked={checks[k]}
                    onCheckedChange={(v) => setChecks((c) => ({ ...c, [k]: !!v }))}
                    className="mt-0.5"
                  />
                  <div className="text-sm">{label}</div>
                  {checks[k] && (
                    <CheckCircle2 className="h-3.5 w-3.5 text-positive ml-auto mt-0.5" />
                  )}
                </li>
              ))}
              <li className="flex items-start gap-2.5 rounded-md border border-border/60 bg-background/40 p-2.5">
                <Checkbox checked={!!reviewer && reviewer !== MAKER} disabled className="mt-0.5" />
                <div className="text-sm">Reviewer approval (Four-Eyes)</div>
                {!!reviewer && reviewer !== MAKER && (
                  <CheckCircle2 className="ml-auto mt-0.5 h-3.5 w-3.5 text-positive" />
                )}
              </li>
              <li
                className={`rounded-md border p-2.5 text-xs ${closeDecision.canLock ? "border-positive/40 bg-positive/5" : "border-warning/40 bg-warning/10"}`}
              >
                <div className="font-medium">Close control: {closeDecision.state}</div>
                {closeDecision.blockers.length > 0 && (
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
                    {closeDecision.blockers.map((blocker) => (
                      <li key={blocker}>{blocker}</li>
                    ))}
                  </ul>
                )}
              </li>
            </ul>
          </Panel>
        </div>
      </div>

      <Dialog open={lockOpen} onOpenChange={setLockOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lock className="h-4 w-4" /> Lock NAV — 2025-11-14
            </DialogTitle>
            <DialogDescription>
              Locking NAV is irreversible. It seals positions, prices, FX and fees for the date. A
              reversing journal is required to modify a locked NAV.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border border-info/40 bg-info/10 p-3 text-xs space-y-2">
            <div className="flex items-center gap-2 text-info font-medium">
              <ShieldCheck className="h-3.5 w-3.5" /> Four-Eyes
            </div>
            <div className="text-muted-foreground">
              Maker: <span className="text-foreground">{MAKER}</span>
            </div>
            <div>
              <label className="text-muted-foreground">Independent reviewer (≠ maker)</label>
              <select
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                aria-label="Independent reviewer"
                className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-xs"
              >
                <option value="">— select reviewer —</option>
                {[
                  "Somchai P. (PM)",
                  "Preecha S. (Risk)",
                  "Niran C. (Ops)",
                  "External Auditor (Read-only)",
                ].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
                <option value={MAKER}>{MAKER} (invalid — same as maker)</option>
              </select>
              {reviewer && reviewer === MAKER && (
                <div className="mt-1 text-destructive">Reviewer must differ from the maker.</div>
              )}
            </div>
          </div>
          {closeDecision.blockers.length > 0 && (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
              {closeDecision.blockers.join(" · ")}
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setLockOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!canLock}
              title={
                !canLock
                  ? "All checklist items and an independent reviewer are required"
                  : "Seal NAV for the date (demo)"
              }
              onClick={() => {
                setNavState("Locked");
                setLockOpen(false);
                toast.success(`NAV locked (demo) · reviewer ${reviewer}`);
              }}
            >
              Confirm lock (demo)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
