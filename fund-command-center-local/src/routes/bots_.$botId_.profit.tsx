import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  getGridBotGovernance,
  getGridBotOrders,
  getGridBotTestnetStatus,
  syncBinanceTestnetGridBot,
} from "@/lib/grid-bot-governance.functions";
import { projectGridCycleProfit, projectedGridProfitTotal } from "@/lib/grid-profit";

export const Route = createFileRoute("/bots_/$botId_/profit")({
  head: () => ({ meta: [{ title: "Grid Profit Projection ยท Aegis Fund OS" }] }),
  loader: async ({ params }) => {
    const [governance, orders] = await Promise.all([getGridBotGovernance(), getGridBotOrders({ data: { botId: params.botId } })]);
    const bot = governance.bots.find((item) => item.id === params.botId) ?? null;
    let exchangeStatus: Awaited<ReturnType<typeof getGridBotTestnetStatus>> | null = null;
    let exchangeError = "";
    if (bot?.environment === "BINANCE_TESTNET") {
      try { exchangeStatus = await getGridBotTestnetStatus({ data: { botId: bot.id } }); }
      catch (error) { exchangeError = error instanceof Error ? error.message : "Exchange verification unavailable"; }
    }
    return { bot, projections: bot ? orders.map((order) => projectGridCycleProfit(bot, order)) : [], exchangeStatus, exchangeError };
  },
  component: GridProfitPage,
});

function GridProfitPage() {
  const { bot, projections, exchangeStatus, exchangeError } = Route.useLoaderData();
  const { botId } = Route.useParams();
  const router = useRouter();
  const [reconciling, setReconciling] = useState(false);
  const total = projectedGridProfitTotal(projections);
  // The grid runtime loop is human-triggered here: one click polls the exchange,
  // marks fills, and places the paired replenishment orders that keep the grid
  // cycling. It fails closed on a non-RUNNING bot and appends a durable event.
  const canReconcile = bot?.environment === "BINANCE_TESTNET" && bot.runtimeState === "RUNNING";
  const reconcile = async () => {
    setReconciling(true);
    try {
      const result = await syncBinanceTestnetGridBot({ data: { botId, actorId: "local-operator@aegis" } });
      toast.success(
        result.changed
          ? `Reconciled: ${result.summary.filled} filled, ${result.summary.placed} replenished, ${result.summary.reconciliationRequired} to review.`
          : "No grid change since last poll.",
      );
      await router.invalidate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Grid reconciliation failed closed");
    } finally {
      setReconciling(false);
    }
  };
  return <AppShell><PageHeader kicker={botId} title="Grid Profit per Cycle" subtitle={bot ? `${bot.name} ยท fee-aware Testnet projection` : "Bot not found"} actions={<div className="flex gap-2">{canReconcile && <Button disabled={reconciling} onClick={reconcile}>{reconciling ? "Reconciling..." : "Reconcile fills"}</Button>}<Button variant="outline" asChild><Link to="/bots/$botId" params={{ botId }}>Bot detail</Link></Button></div>} />
    <div className="space-y-6 p-6"><Panel title="Profit status" subtitle="Only completed and reconciled fills can become realized P/L."><div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-md border p-4"><div className="text-xs text-muted-foreground">Active grid orders</div><div className="mt-1 text-2xl font-semibold">{projections.length}</div></div>
      <div className="rounded-md border p-4"><div className="text-xs text-muted-foreground">Maximum projected cycles</div><div className="mt-1 text-2xl font-semibold text-positive">{total} USDT</div></div>
      <div className="rounded-md border p-4"><div className="text-xs text-muted-foreground">Realized P/L</div><div className="mt-1 text-sm font-medium">{exchangeStatus ? exchangeStatus.realizedPnl === null ? "Reconciliation required" : `${exchangeStatus.realizedPnl} USDT` : "Verification unavailable"}</div></div>
    </div><p className="mt-4 text-sm text-muted-foreground">{exchangeStatus ? `Exchange verified ${exchangeStatus.matchingOpenOrderCount}/${exchangeStatus.ledgerOrderCount} open orders · ${exchangeStatus.matchingTradeCount} fills observed · ${new Date(exchangeStatus.checkedAt).toLocaleString()}` : exchangeError || "Current orders are exchange acknowledgements, not fills. No projected value is presented as realized P/L."}</p></Panel>
    <Panel title="Per-grid projection" subtitle="Target is the adjacent grid price; estimate deducts 0.10% fee on entry and exit.">{projections.length === 0 ? <p className="py-10 text-center text-sm text-muted-foreground">No exchange-acknowledged Testnet orders exist for this bot.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead><tr className="text-left text-xs uppercase text-muted-foreground">{["Grid", "Entry", "Cycle target", "Quantity", "Est. fees", "Est. profit / cycle", "Order status", "Realized P/L"].map((heading) => <th className="p-2" key={heading}>{heading}</th>)}</tr></thead><tbody>{projections.map((item) => <tr className="border-t" key={item.gridIndex}><td className="p-2">{item.gridIndex} <span className="text-xs text-muted-foreground">{item.side}</span></td><td className="p-2 font-mono">{item.entryPrice}</td><td className="p-2 font-mono">{item.targetPrice}</td><td className="p-2 font-mono">{item.quantity}</td><td className="p-2 font-mono">{item.estimatedFees}</td><td className="p-2 font-mono text-positive">{item.estimatedCycleProfit} USDT</td><td className="p-2">{item.orderStatus}</td><td className="p-2 text-muted-foreground">Awaiting fill reconciliation</td></tr>)}</tbody></table></div>}</Panel></div>
  </AppShell>;
}
