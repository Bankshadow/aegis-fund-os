import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney, fmtPct } from "@/components/metric-card";
import { PaperBadge, StatusDot } from "@/components/demo-tag";
import { KPIS, RISK_LIMITS, STRESS, PAPER_ORDERS, EXPOSURE_CCY, EXPOSURE_STRATEGY } from "@/lib/demo-data";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ShieldOff, Check, X, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/risk")({
  head: () => ({ meta: [{ title: "Risk Center · Aegis Fund OS" }] }),
  component: RiskPage,
});

type PaperOrder = (typeof PAPER_ORDERS)[number] & { checker: string | null };

const CURRENT_USER = "COO (Anong)";

function RiskPage() {
  const [selectedScen, setSelectedScen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(STRESS.map((s) => [s.scenario, false]))
  );
  const [orders, setOrders] = useState<PaperOrder[]>(() => PAPER_ORDERS.map((o) => ({ ...o })));

  const combined = useMemo(() => {
    const selected = STRESS.filter((s) => selectedScen[s.scenario]);
    return selected.reduce((acc, s) => ({ pnl: acc.pnl + s.pnl, pct: acc.pct + s.pct }), { pnl: 0, pct: 0 });
  }, [selectedScen]);
  const selectedCount = Object.values(selectedScen).filter(Boolean).length;

  const updateOrder = (id: string, patch: Partial<PaperOrder>) => setOrders((os) => os.map((o) => (o.id === id ? { ...o, ...patch } : o)));

  return (
    <AppShell>
      <PageHeader
        kicker="Risk Center · Paper environment"
        title="Risk & Limits"
        subtitle="Exposure gauges, stress scenarios, and paper-order approval queue. No live execution path exists."
        actions={<PaperBadge />}
      />
      <div className="p-6 space-y-6">
        <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning flex items-start gap-2">
          <TriangleAlert className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <div className="font-medium">PAPER / NON-LIVE environment</div>
            <div className="text-xs text-warning/80">All orders route to paper/testnet/sandbox adapters. Live execution is architecturally absent.</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="Gross Exposure" value={fmtPct(KPIS.grossExposure, 1)} sub="Soft 100% · Hard 125%" tone="warning" />
          <MetricCard label="Net Exposure" value={fmtPct(KPIS.netExposure, 1)} sub="Soft 60% · Hard 80%" />
          <MetricCard label="Concentration" value={fmtPct(0.093, 1)} sub="Single name · Soft 8%" tone="warning" />
          <MetricCard label="Daily Loss" value={fmtPct(KPIS.dailyReturn, 2)} sub="Soft −1% · Hard −2%" tone="positive" />
          <MetricCard label="Max DD" value={fmtPct(KPIS.maxDrawdown)} sub="Soft −10% · Hard −15%" />
          <MetricCard label="Leverage" value="1.32×" sub="Soft 1.5× · Hard 2.0×" />
        </div>

        <Panel title="Risk limits" subtitle="Utilization vs soft/hard thresholds">
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Limit</th>
                  <th className="text-right py-2 pr-4 font-medium">Current</th>
                  <th className="text-right py-2 pr-4 font-medium">Soft</th>
                  <th className="text-right py-2 pr-4 font-medium">Hard</th>
                  <th className="text-left py-2 pr-4 font-medium w-[26%]">Utilization</th>
                  <th className="text-left py-2 pr-4 font-medium">Trend</th>
                  <th className="text-left py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {RISK_LIMITS.map((l) => {
                  const util = Math.min(Math.abs(l.cur / l.hard) * 100, 100);
                  const isPct = !l.name.includes("Leverage") && !l.name.includes("Stale");
                  const fmt = (v: number) => isPct ? fmtPct(v, 2) : (l.name.includes("Leverage") ? `${v.toFixed(2)}×` : String(v));
                  return (
                    <tr key={l.name} className="border-b border-border/40">
                      <td className="py-2 pr-4 font-medium">{l.name}</td>
                      <td className="py-2 pr-4 text-right num">{fmt(l.cur)}</td>
                      <td className="py-2 pr-4 text-right num text-muted-foreground">{fmt(l.soft)}</td>
                      <td className="py-2 pr-4 text-right num text-muted-foreground">{fmt(l.hard)}</td>
                      <td className="py-2 pr-4"><Progress value={util} className="h-1.5" /></td>
                      <td className="py-2 pr-4">
                        <svg viewBox="0 0 60 20" className="h-4 w-16">
                          <polyline
                            fill="none"
                            stroke={l.status === "OK" ? "oklch(0.66 0.13 155)" : "oklch(0.78 0.15 78)"}
                            strokeWidth="1.5"
                            points={l.trend.map((v, i) => {
                              const min = Math.min(...l.trend), max = Math.max(...l.trend);
                              const y = 18 - ((v - min) / (max - min || 1)) * 16;
                              return `${(i / (l.trend.length - 1)) * 60},${y}`;
                            }).join(" ")}
                          />
                        </svg>
                      </td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <StatusDot tone={l.status === "OK" ? "positive" : "warning"} />
                          {l.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="Exposure decomposition" subtitle="Strategy · currency">
            <div className="space-y-4">
              <div>
                <div className="text-[11px] uppercase text-muted-foreground tracking-wider mb-1.5">By strategy</div>
                <ul className="space-y-1.5">
                  {EXPOSURE_STRATEGY.map((s) => (
                    <li key={s.name} className="flex items-center gap-3 text-xs">
                      <span className="w-40 truncate">{s.name}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-accent/60 overflow-hidden">
                        <div className="h-full bg-primary" style={{ width: `${s.gross * 100}%` }} />
                      </div>
                      <span className="num w-14 text-right text-muted-foreground">{fmtPct(s.gross,1)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="text-[11px] uppercase text-muted-foreground tracking-wider mb-1.5">By currency</div>
                <ul className="space-y-1.5">
                  {EXPOSURE_CCY.map((c) => (
                    <li key={c.name} className="flex items-center gap-3 text-xs">
                      <span className="w-16">{c.name}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-accent/60 overflow-hidden">
                        <div className="h-full bg-info" style={{ width: `${c.value}%` }} />
                      </div>
                      <span className="num w-14 text-right text-muted-foreground">{c.value}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>

          <Panel
            title="Stress scenarios"
            subtitle="Toggle scenarios to combine estimated NAV impact"
            actions={
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span>Combined:</span>
                <span className={`num font-semibold ${selectedCount === 0 ? "text-muted-foreground" : "text-destructive"}`}>
                  {fmtMoney(combined.pnl, "USD", 0)} · {fmtPct(combined.pct, 2)}
                </span>
              </div>
            }
          >
            <ul className="space-y-2">
              {STRESS.map((s) => {
                const active = !!selectedScen[s.scenario];
                return (
                  <li key={s.scenario}>
                    <label className={`flex items-center gap-3 rounded-md border px-3 py-2 cursor-pointer transition-colors ${active ? "border-primary/50 bg-primary/5" : "border-border/60 bg-background/40 hover:border-border"}`}>
                      <Checkbox checked={active} onCheckedChange={(v) => setSelectedScen((m) => ({ ...m, [s.scenario]: !!v }))} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium truncate">{s.scenario}</div>
                        <div className="text-[11px] text-muted-foreground">Historical + factor-based</div>
                      </div>
                      <div className="text-right">
                        <div className="num text-sm font-semibold text-destructive">{fmtMoney(s.pnl, "USD", 0)}</div>
                        <div className="num text-[11px] text-muted-foreground">{fmtPct(s.pct, 2)}</div>
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
            {selectedCount > 0 && (
              <div className="mt-3 rounded-md border border-destructive/40 bg-destructive/5 p-2.5 text-xs">
                <span className="text-muted-foreground">Estimated combined impact on NAV ({selectedCount} scenario{selectedCount > 1 ? "s" : ""}):</span>{" "}
                <span className="num font-semibold text-destructive">{fmtMoney(combined.pnl, "USD", 0)} · {fmtPct(combined.pct, 2)}</span>
                <div className="mt-1 text-[10px] text-muted-foreground">Linear approximation — correlations not modeled (demo).</div>
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Paper order approval queue" subtitle="Maker / Checker · limit checks · no live execution">
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Order</th>
                  <th className="text-left py-2 pr-4 font-medium">Symbol</th>
                  <th className="text-left py-2 pr-4 font-medium">Side</th>
                  <th className="text-right py-2 pr-4 font-medium">Qty</th>
                  <th className="text-right py-2 pr-4 font-medium">Limit</th>
                  <th className="text-left py-2 pr-4 font-medium">Maker</th>
                  <th className="text-left py-2 pr-4 font-medium">Checker</th>
                  <th className="text-left py-2 pr-4 font-medium">Checks</th>
                  <th className="text-left py-2 pr-4 font-medium">Status</th>
                  <th className="text-right py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const makerConflict = o.maker === CURRENT_USER;
                  const canApprove = o.status !== "Blocked" && o.status !== "Approved" && !makerConflict;
                  return (
                    <tr key={o.id} className="border-b border-border/40">
                      <td className="py-2 pr-4 font-mono text-xs">{o.id}</td>
                      <td className="py-2 pr-4 font-mono">{o.sym}</td>
                      <td className="py-2 pr-4"><Badge variant="outline" className={`text-[10px] ${o.side === "BUY" ? "border-positive/50 text-positive" : "border-destructive/50 text-destructive"}`}>{o.side}</Badge></td>
                      <td className="py-2 pr-4 text-right num">{o.qty}</td>
                      <td className="py-2 pr-4 text-right num">{fmtMoney(o.limit, "USD", 2)}</td>
                      <td className="py-2 pr-4 text-xs">{o.maker}</td>
                      <td className="py-2 pr-4 text-xs">{o.checker ?? <span className="text-muted-foreground">—</span>}</td>
                      <td className={`py-2 pr-4 text-xs ${o.checks.startsWith("Breach") ? "text-destructive" : "text-positive"}`}>{o.checks}</td>
                      <td className="py-2 pr-4"><Badge variant="outline" className="text-[10px]">{o.status}</Badge></td>
                      <td className="py-2 text-right">
                        <div className="inline-flex gap-1">
                          <TooltipProvider delayDuration={100}>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span>
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    aria-label={`Approve ${o.id}`}
                                    className="h-7 w-7 text-positive"
                                    disabled={!canApprove}
                                    onClick={() => {
                                      updateOrder(o.id, { checker: CURRENT_USER, status: "Approved" });
                                      toast.success(`${o.id} approved by ${CURRENT_USER} (demo, paper)`);
                                    }}
                                  ><Check className="h-3.5 w-3.5" /></Button>
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="left">
                                {o.status === "Blocked" ? "Blocked by risk check" : makerConflict ? "Maker cannot self-approve" : o.status === "Approved" ? "Already approved" : "Approve as checker (demo)"}
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label={`Reject ${o.id}`}
                            className="h-7 w-7 text-destructive"
                            disabled={o.status === "Blocked"}
                            onClick={() => { updateOrder(o.id, { status: "Blocked", checker: null }); toast.error(`${o.id} rejected (demo)`); }}
                          ><X className="h-3.5 w-3.5" /></Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Kill switch" subtitle="Halts all paper-order routing — demo control, non-live">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="flex-1 min-w-[280px]">
              <p className="text-sm text-muted-foreground">
                Engaging the kill switch would prevent any new order intents (paper) from reaching adapters,
                cancel resting paper orders, and require a two-officer release. In this prototype the control
                is disabled — there is no live execution path to interrupt.
              </p>
            </div>
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Button size="lg" disabled variant="destructive" className="opacity-70">
                      <ShieldOff className="h-4 w-4" /> Engage kill switch
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="left">Demo prototype — no live execution to halt.</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

