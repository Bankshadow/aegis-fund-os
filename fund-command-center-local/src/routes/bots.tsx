import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { BotStateBadge, EnvironmentBadge } from "@/components/bots/bot-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  getGridBotGovernance,
  startBinanceTestnetGridBot,
  stopBinanceTestnetGridBot,
  syncAllRunningTestnetGrids,
  transitionGridBotRuntime,
} from "@/lib/grid-bot-governance.functions";
import type { RuntimeState } from "@/lib/grid-bot-governance";
import type { BotRecord } from "@/lib/grid-bot-repository";
import { Bot, ChartNoAxesCombined, CircleDollarSign, Clock3, Landmark, Plus, ShieldCheck, StopCircle } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/bots")({
  head: () => ({ meta: [{ title: "Grid Bot Cockpit · Aegis Fund OS" }] }),
  loader: async () => {
    try {
      return { ...(await getGridBotGovernance()), storageAvailable: true as const, error: "" };
    } catch (error) {
      return {
        bots: [],
        events: [],
        profitByBot: {} as Record<string, { orderCount: number; estimatedCycleProfit: string }>,
        auditValid: false,
        publicTestMode: false,
        storageAvailable: false as const,
        error: error instanceof Error ? error.message : "Governance storage unavailable",
      };
    }
  },
  component: BotsCockpit,
});

const numberConfig = (value: string | number | boolean | null | undefined) => {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
};

type ProfitSummary = { orderCount: number; estimatedCycleProfit: string };

function CompactStatus({ bot }: { bot: BotRecord }) {
  const iconClass = "h-4 w-4";
  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex items-center gap-2 text-muted-foreground">
        <Tooltip><TooltipTrigger aria-label={`Environment: ${bot.environment}`}><Landmark className={`${iconClass} ${bot.environment === "BINANCE_TESTNET" ? "text-info" : ""}`} /></TooltipTrigger><TooltipContent>Environment: {bot.environment.replaceAll("_", " ")}</TooltipContent></Tooltip>
        <Tooltip><TooltipTrigger aria-label={`Approval: ${bot.state}`}><ShieldCheck className={`${iconClass} ${bot.state === "APPROVED" ? "text-positive" : "text-warning"}`} /></TooltipTrigger><TooltipContent>Approval: {bot.state.replaceAll("_", " ")}</TooltipContent></Tooltip>
        <Tooltip><TooltipTrigger aria-label={`Runtime: ${bot.runtimeState}`}><Clock3 className={`${iconClass} ${bot.runtimeState === "RUNNING" ? "text-positive" : ""}`} /></TooltipTrigger><TooltipContent>Runtime: {bot.runtimeState}</TooltipContent></Tooltip>
      </div>
    </TooltipProvider>
  );
}

function DetailMetric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div><div className="text-xs text-muted-foreground">{label}</div><div className="mt-1 font-medium">{value}</div>{note && <div className="mt-1 text-[11px] text-muted-foreground">{note}</div>}</div>;
}

function BotCard({ bot, profit, working, command }: { bot: BotRecord; profit?: ProfitSummary; working: boolean; command: (next: Exclude<RuntimeState, "IDLE">) => void }) {
  const projected = profit && profit.orderCount > 0 ? Number(profit.estimatedCycleProfit).toFixed(2) : null;
  const tp = String(bot.configuration.takeProfit || "—");
  const sl = String(bot.configuration.stopLoss || "—");
  return <article className="rounded-xl border border-border/70 bg-card/50 p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-info/30 bg-info/10 text-info"><Bot className="h-5 w-5" /></div><div className="min-w-0"><Link to="/bots/$botId" params={{ botId: bot.id }} className="block truncate font-semibold hover:text-primary">{bot.name}</Link><div className="mt-0.5 font-mono text-sm text-muted-foreground">{bot.pair} · {bot.id}</div></div></div>
      <CompactStatus bot={bot} />
    </div>
    <div className="mt-5 grid overflow-hidden rounded-lg border md:grid-cols-2">
      <div className="bg-background/30 p-4"><div className="text-xs text-muted-foreground">Actual investment</div><div className="mt-1 text-2xl font-semibold">{fmtMoney(numberConfig(bot.configuration.investment))}</div><div className="mt-1 text-xs text-muted-foreground">Allocated Testnet capital</div></div>
      <div className="border-t bg-positive/5 p-4 md:border-l md:border-t-0"><div className="flex items-center gap-1 text-xs text-muted-foreground"><ChartNoAxesCombined className="h-3.5 w-3.5" /> Grid profit potential</div><div className="mt-1 text-2xl font-semibold text-positive">{projected ? `~$${projected}` : "—"}</div><div className="mt-1 text-xs text-muted-foreground">{projected ? "Estimate across active grid cycles" : "No acknowledged exchange orders"}</div></div>
    </div>
    <div className="mt-5 grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
      <DetailMetric label="Grid profit" value={projected ? `~$${projected}` : "—"} note="Estimate · awaiting fills" />
      <DetailMetric label="Realized P/L" value="Awaiting reconciliation" note="No fill is treated as realized profit" />
      <DetailMetric label="Price range" value={`${String(bot.configuration.lower ?? "—")} – ${String(bot.configuration.upper ?? "—")}`} note={`${String(bot.configuration.grids ?? "—")} grids · ${String(bot.configuration.mode ?? "—")}`} />
      <DetailMetric label="Active orders" value={`${profit?.orderCount ?? 0} orders`} note={bot.runtimeState === "RUNNING" ? "Exchange acknowledged" : "Not running"} />
      <DetailMetric label="Take profit / Stop loss" value={`${tp} / ${sl}`} />
      <DetailMetric label="Last update" value={new Date(bot.updatedAt).toLocaleString()} />
      <DetailMetric label="Bot version" value={`v${bot.version}`} />
      <DetailMetric label="Cycle status" value={bot.runtimeState === "RUNNING" ? "Monitoring orders" : bot.runtimeState} />
    </div>
    <div className="mt-5 flex flex-wrap gap-2 border-t pt-4"><Button size="sm" variant="outline" asChild><Link to="/bots/$botId" params={{ botId: bot.id }}>Detail</Link></Button><Button size="sm" variant="outline" asChild><Link to="/bots/$botId/profit" params={{ botId: bot.id }}><CircleDollarSign className="h-3.5 w-3.5" />Grid profit</Link></Button>
      {bot.state === "APPROVED" && bot.runtimeState === "IDLE" && <Button size="sm" disabled={working} onClick={() => command("RUNNING")}>Start Testnet</Button>}
      {(bot.runtimeState === "RUNNING" || bot.runtimeState === "PAUSED") && <Button size="sm" variant="destructive" disabled={working} onClick={() => command("STOPPED")}><StopCircle className="h-3.5 w-3.5" />Stop</Button>}
    </div>
  </article>;
}

function BotsCockpit() {
  const initial = Route.useLoaderData();
  const [bots, setBots] = useState(initial.bots);
  const [q, setQ] = useState("");
  const [working, setWorking] = useState<string | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const hasRunningTestnet = bots.some(
    (bot) => bot.environment === "BINANCE_TESTNET" && bot.runtimeState === "RUNNING",
  );
  // Human-triggered batch reconcile — the same driver a scheduled cron would run.
  const syncAll = async () => {
    setSyncingAll(true);
    try {
      const { results } = await syncAllRunningTestnetGrids({ data: { actorId: "local-operator@aegis" } });
      const placed = results.reduce((sum, r) => sum + ("summary" in r ? r.summary.placed : 0), 0);
      const filled = results.reduce((sum, r) => sum + ("summary" in r ? r.summary.filled : 0), 0);
      const errors = results.filter((r) => "error" in r).length;
      toast.success(`Synced ${results.length} running bot(s): ${filled} filled, ${placed} replenished${errors ? `, ${errors} failed` : ""}.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Batch reconcile failed closed");
    } finally {
      setSyncingAll(false);
    }
  };
  const visible = useMemo(
    () =>
      bots.filter((bot) =>
        `${bot.name} ${bot.pair} ${bot.environment}`.toLowerCase().includes(q.toLowerCase()),
      ),
    [bots, q],
  );
  const allocated = bots.reduce((sum, bot) => sum + numberConfig(bot.configuration.investment), 0);
  const command = async (botId: string, nextState: Exclude<RuntimeState, "IDLE">) => {
    setWorking(botId);
    try {
      const current = bots.find((bot) => bot.id === botId);
      if (!current) throw new Error("Bot not found");
      const updated =
        current.environment === "BINANCE_TESTNET" && nextState === "RUNNING"
          ? (await startBinanceTestnetGridBot({ data: { botId, actorId: "local-operator@aegis" } })).bot
          : current.environment === "BINANCE_TESTNET" && nextState === "STOPPED"
            ? await stopBinanceTestnetGridBot({ data: { botId, actorId: "local-operator@aegis" } })
            : await transitionGridBotRuntime({ data: { botId, nextState, actorId: "local-operator@aegis" } });
      setBots((items) => items.map((bot) => (bot.id === botId ? updated : bot)));
      toast.success(`${botId} → ${nextState}; durable audit event appended.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Runtime command failed closed");
    } finally {
      setWorking(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        kicker={initial.publicTestMode ? "PUBLIC TEST MODE · MUTATIONS OPEN · TESTNET ONLY" : "DURABLE GOVERNANCE · BINANCE SPOT TESTNET"}
        title="Spot Grid Bot Cockpit"
        subtitle={
          initial.publicTestMode
            ? "Public research build — no login; anyone can create/start/reconcile testnet bots. No real funds."
            : "D1-backed bot fleet, approval state and audited runtime controls."
        }
        actions={
          <div className="flex gap-2">
            {hasRunningTestnet && (
              <Button variant="outline" disabled={syncingAll} onClick={syncAll}>
                {syncingAll ? "Syncing..." : "Sync all running"}
              </Button>
            )}
            <Button asChild>
              <Link to="/bots/new">
                <Plus className="h-4 w-4" />
                Create Grid Bot
              </Link>
            </Button>
          </div>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Testnet execution is isolated from real funds"
          text="Approved BINANCE_TESTNET bots place and cancel LIMIT orders only at testnet.binance.vision. Demo and Paper remain local projections; Mainnet is unavailable."
        />
        {!initial.storageAvailable && (
          <Panel title="Storage unavailable">
            <p className="text-sm text-destructive">
              {initial.error}. Fleet mutations are blocked.
            </p>
          </Panel>
        )}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard demo={false} label="Durable bots" value={bots.length} />
          <MetricCard
            demo={false}
            label="Running"
            value={bots.filter((bot) => bot.runtimeState === "RUNNING").length}
          />
          <MetricCard demo={false} label="Allocated" value={fmtMoney(allocated)} />
          <MetricCard
            demo={false}
            label="Audit chain"
            value={initial.auditValid ? "Verified" : "Blocked"}
            tone={initial.auditValid ? "positive" : "negative"}
          />
        </div>
        <Panel
          title="Bot Fleet"
          subtitle="Only durable D1 records are shown; fixture bots have been removed."
          actions={
            <Input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Filter bot, pair, environment"
              className="h-8 w-64"
            />
          }
        >
          {visible.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No durable grid bots found. Create a draft to begin.
            </div>
          ) : (
            <>
              <div className="grid gap-4 xl:grid-cols-2">
                {visible.map((bot) => (
                  <BotCard
                    key={bot.id}
                    bot={bot}
                    profit={initial.profitByBot[bot.id]}
                    working={working === bot.id}
                    command={(nextState) => command(bot.id, nextState)}
                  />
                ))}
              </div>
              <div className="hidden overflow-x-auto">
              <table className="w-full min-w-[1050px] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-muted-foreground">
                    {[
                      "Bot",
                      "Pair",
                      "Environment",
                      "Approval",
                      "Runtime",
                      "Range",
                      "Investment",
                      "Grid profit",
                      "Version",
                      "Updated",
                      "Actions",
                    ].map((heading) => (
                      <th className="p-2" key={heading}>
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((bot) => (
                    <tr className="border-t border-border/50" key={bot.id}>
                      <td className="p-2">
                        <Link
                          to="/bots/$botId"
                          params={{ botId: bot.id }}
                          className="font-medium hover:text-primary"
                        >
                          {bot.name}
                        </Link>
                        <div className="font-mono text-[10px] text-muted-foreground">{bot.id}</div>
                      </td>
                      <td className="p-2 font-mono">{bot.pair}</td>
                      <td className="p-2">
                        <EnvironmentBadge value={bot.environment} />
                      </td>
                      <td className="p-2">
                        <Badge variant="outline">{bot.state.replaceAll("_", " ")}</Badge>
                      </td>
                      <td className="p-2">
                        <BotStateBadge value={bot.runtimeState} />
                      </td>
                      <td className="p-2">
                        {String(bot.configuration.lower ?? "—")} –{" "}
                        {String(bot.configuration.upper ?? "—")}
                      </td>
                      <td className="p-2">
                        {fmtMoney(numberConfig(bot.configuration.investment))}
                      </td>
                      <td className="p-2">
                        {(initial.profitByBot[bot.id]?.orderCount ?? 0) > 0 ? (
                          <>
                            <div className="font-mono text-positive">
                              ~${Number(initial.profitByBot[bot.id].estimatedCycleProfit).toFixed(2)}
                            </div>
                            <div className="text-[10px] text-muted-foreground">estimate · awaiting fills</div>
                          </>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="p-2">v{bot.version}</td>
                      <td className="p-2 text-xs">{new Date(bot.updatedAt).toLocaleString()}</td>
                      <td className="p-2">
                        <div className="flex gap-1">
                          <Button size="sm" variant="outline" asChild>
                            <Link to="/bots/$botId" params={{ botId: bot.id }}>
                              View
                            </Link>
                          </Button>
                          <Button size="sm" variant="outline" asChild>
                            <Link to="/bots/$botId/profit" params={{ botId: bot.id }}>
                              Grid profit
                            </Link>
                          </Button>
                          {bot.state === "APPROVED" && bot.runtimeState === "IDLE" && (
                            <Button
                              size="sm"
                              disabled={working === bot.id}
                              onClick={() => command(bot.id, "RUNNING")}
                            >
                              {bot.environment === "BINANCE_TESTNET" ? "Start Testnet" : "Start"}
                            </Button>
                          )}
                          {bot.runtimeState === "RUNNING" && bot.environment !== "BINANCE_TESTNET" && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={working === bot.id}
                              onClick={() => command(bot.id, "PAUSED")}
                            >
                              Pause
                            </Button>
                          )}
                          {bot.runtimeState === "PAUSED" && bot.environment !== "BINANCE_TESTNET" && (
                            <Button
                              size="sm"
                              disabled={working === bot.id}
                              onClick={() => command(bot.id, "RUNNING")}
                            >
                              Resume
                            </Button>
                          )}
                          {(bot.runtimeState === "RUNNING" || bot.runtimeState === "PAUSED") && (
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={working === bot.id}
                              onClick={() => command(bot.id, "STOPPED")}
                            >
                              Stop
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
