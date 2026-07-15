import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Bot, CirclePause, CirclePlay, LockKeyhole, Search, ShieldX } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/bots")({
  head: () => ({ meta: [{ title: "Bots & Orders · Aegis Fund OS" }] }),
  component: BotsPage,
});

type BotRow = {
  id: string;
  name: string;
  strategy: string;
  venue: string;
  mode: string;
  state: "Running" | "Paused" | "Stopped";
  pnl: number;
  capital: number;
  last: string;
};

const initialBots: BotRow[] = [
  {
    id: "BOT-P-104",
    name: "BTC Dual Grid",
    strategy: "Dual Grid 75/25",
    venue: "Binance Testnet",
    mode: "Paper",
    state: "Paused",
    pnl: 1842,
    capital: 125000,
    last: "18s ago",
  },
  {
    id: "BOT-P-105",
    name: "ETH Regime Grid",
    strategy: "Percentile Router",
    venue: "IBKR Paper",
    mode: "Paper",
    state: "Running",
    pnl: 734,
    capital: 90000,
    last: "4s ago",
  },
  {
    id: "BOT-R-012",
    name: "Funding RV Observer",
    strategy: "Funding Relative Value",
    venue: "Read-only feed",
    mode: "Observe",
    state: "Running",
    pnl: 0,
    capital: 0,
    last: "2s ago",
  },
];

const orders = [
  {
    id: "ORD-P-8821",
    time: "10:42:18",
    bot: "ETH Regime Grid",
    symbol: "ETH/USDT",
    side: "BUY",
    type: "LIMIT",
    qty: "1.80",
    price: "3,216.40",
    status: "Filled",
  },
  {
    id: "ORD-P-8820",
    time: "10:39:02",
    bot: "BTC Dual Grid",
    symbol: "BTC/USDT",
    side: "SELL",
    type: "LIMIT",
    qty: "0.08",
    price: "102,440.00",
    status: "Cancelled",
  },
  {
    id: "ORD-P-8819",
    time: "10:31:47",
    bot: "ETH Regime Grid",
    symbol: "ETH/USDT",
    side: "SELL",
    type: "LIMIT",
    qty: "1.75",
    price: "3,248.20",
    status: "Filled",
  },
  {
    id: "ORD-P-8818",
    time: "10:18:11",
    bot: "BTC Dual Grid",
    symbol: "BTC/USDT",
    side: "BUY",
    type: "LIMIT",
    qty: "0.08",
    price: "101,920.00",
    status: "Filled",
  },
];

function BotsPage() {
  const [bots, setBots] = useState(initialBots);
  const [q, setQ] = useState("");
  const filtered = useMemo(
    () =>
      bots.filter((b) =>
        `${b.name} ${b.strategy} ${b.venue}`.toLowerCase().includes(q.toLowerCase()),
      ),
    [bots, q],
  );

  const toggle = (id: string) => {
    setBots((rows) =>
      rows.map((bot) =>
        bot.id === id ? { ...bot, state: bot.state === "Running" ? "Paused" : "Running" } : bot,
      ),
    );
    toast.success("Paper bot state updated (local demo)");
  };

  const stopAll = () => {
    setBots((rows) => rows.map((bot) => ({ ...bot, state: "Stopped" })));
    toast.warning("All paper bots stopped. No external orders were sent.");
  };

  return (
    <AppShell>
      <PageHeader
        kicker="P1 · Paper execution cockpit"
        title="Bots & Orders"
        subtitle="Monitor paper bots, simulated order lifecycle and control posture without live execution capability."
        actions={
          <>
            <Button variant="destructive" size="sm" onClick={stopAll}>
              <ShieldX className="h-3.5 w-3.5" /> Stop all paper bots
            </Button>
            <Button size="sm" onClick={() => toast.success("Paper bot draft created (demo)")}>
              <Bot className="h-3.5 w-3.5" /> New paper bot
            </Button>
          </>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Live order gateway is hard-disabled"
          text="Controls below only mutate this local demo state. No API route, signer or live order transport is connected."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="Paper bots"
            value={String(bots.length)}
            sub={`${bots.filter((b) => b.state === "Running").length} running`}
          />
          <MetricCard
            label="Paper P&L (D)"
            value={fmtMoney(
              bots.reduce((sum, b) => sum + b.pnl, 0),
              "USD",
              0,
            )}
            tone="positive"
          />
          <MetricCard label="Open simulated orders" value="3" sub="Across 2 venues" />
          <MetricCard
            label="Live execution"
            value="Disabled"
            tone="warning"
            sub="No order transport"
          />
        </div>

        <Tabs defaultValue="bots" className="space-y-4">
          <TabsList>
            <TabsTrigger value="bots">Bot fleet</TabsTrigger>
            <TabsTrigger value="orders">Order blotter</TabsTrigger>
            <TabsTrigger value="controls">Execution controls</TabsTrigger>
          </TabsList>
          <TabsContent value="bots">
            <Panel
              title="Bot fleet"
              subtitle="Local paper and observer processes"
              actions={
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    className="h-8 w-60 pl-7 text-xs"
                    placeholder="Filter bots…"
                  />
                </div>
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left font-medium">Bot</th>
                      <th className="py-2 pr-4 text-left font-medium">Strategy</th>
                      <th className="py-2 pr-4 text-left font-medium">Venue</th>
                      <th className="py-2 pr-4 text-left font-medium">Mode</th>
                      <th className="py-2 pr-4 text-left font-medium">State</th>
                      <th className="py-2 pr-4 text-right font-medium">Paper P&L</th>
                      <th className="py-2 text-right font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((bot) => (
                      <tr key={bot.id} className="border-b border-border/40">
                        <td className="py-3 pr-4">
                          <div className="font-medium">{bot.name}</div>
                          <div className="font-mono text-[10px] text-muted-foreground">
                            {bot.id} · {bot.last}
                          </div>
                        </td>
                        <td className="py-3 pr-4 text-xs">{bot.strategy}</td>
                        <td className="py-3 pr-4 text-xs text-muted-foreground">{bot.venue}</td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline">{bot.mode}</Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={
                              bot.state === "Running"
                                ? "text-positive"
                                : bot.state === "Paused"
                                  ? "text-warning"
                                  : "text-muted-foreground"
                            }
                          >
                            {bot.state}
                          </span>
                        </td>
                        <td
                          className={`py-3 pr-4 text-right font-mono ${bot.pnl > 0 ? "text-positive" : ""}`}
                        >
                          {bot.capital ? fmtMoney(bot.pnl) : "—"}
                        </td>
                        <td className="py-3 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={bot.state === "Stopped"}
                            onClick={() => toggle(bot.id)}
                          >
                            {bot.state === "Running" ? (
                              <CirclePause className="h-3.5 w-3.5" />
                            ) : (
                              <CirclePlay className="h-3.5 w-3.5" />
                            )}
                            {bot.state === "Running" ? "Pause" : "Resume"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="orders">
            <Panel title="Simulated order blotter" subtitle="Paper lifecycle only · newest first">
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left">Order</th>
                      <th className="py-2 pr-4 text-left">Time</th>
                      <th className="py-2 pr-4 text-left">Bot</th>
                      <th className="py-2 pr-4 text-left">Symbol</th>
                      <th className="py-2 pr-4 text-left">Side</th>
                      <th className="py-2 pr-4 text-right">Qty</th>
                      <th className="py-2 pr-4 text-right">Limit</th>
                      <th className="py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.id} className="border-b border-border/40">
                        <td className="py-3 pr-4 font-mono text-xs">{order.id}</td>
                        <td className="py-3 pr-4 text-muted-foreground">{order.time}</td>
                        <td className="py-3 pr-4">{order.bot}</td>
                        <td className="py-3 pr-4 font-mono text-xs">{order.symbol}</td>
                        <td
                          className={`py-3 pr-4 font-medium ${order.side === "BUY" ? "text-positive" : "text-warning"}`}
                        >
                          {order.side}
                        </td>
                        <td className="py-3 pr-4 text-right">{order.qty}</td>
                        <td className="py-3 pr-4 text-right">{order.price}</td>
                        <td className="py-3">
                          <Badge variant="outline">{order.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="controls">
            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title="Environment controls" subtitle="Fail-closed execution posture">
                <ul className="space-y-2 text-sm">
                  {[
                    ["Live order transport", "Disabled"],
                    ["API key scope", "Read-only / testnet"],
                    ["Withdrawal scope", "Never allowed"],
                    ["Pre-trade risk checks", "Required"],
                    ["Four-eyes activation", "Required"],
                  ].map(([name, value]) => (
                    <li
                      key={name}
                      className="flex items-center justify-between rounded-md border border-border/60 p-2.5"
                    >
                      <span>{name}</span>
                      <span className="text-xs text-muted-foreground">{value}</span>
                    </li>
                  ))}
                </ul>
              </Panel>
              <Panel title="Activation gate">
                <div className="space-y-3 text-sm text-muted-foreground">
                  <p>
                    A bot can be drafted only from a paper-eligible deterministic strategy. Any
                    state change is written to the demo audit log.
                  </p>
                  <Button disabled className="w-full">
                    <LockKeyhole className="h-3.5 w-3.5" /> Live activation unavailable
                  </Button>
                </div>
              </Panel>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
