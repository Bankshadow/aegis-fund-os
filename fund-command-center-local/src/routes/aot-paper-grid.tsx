import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AOT_PAPER_RULES,
  calculatePaperGrid,
  type PaperGridConfig,
  type PaperStrategyStatus,
} from "@/lib/aot-paper-domain";
import { createAotPaperStrategy } from "@/lib/aot-paper.functions";
import { runAotPaperGridSimulation } from "@/lib/aot-paper-simulation";
import { ArrowLeft, Calculator, Pause, Play, Save, ShieldAlert, Square } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/aot-paper-grid")({
  head: () => ({ meta: [{ title: "AOT Paper Grid · Aegis Fund OS" }] }),
  component: AotPaperGridPage,
});
const thb = (value: string | number) =>
  new Intl.NumberFormat("th-TH", { style: "currency", currency: "THB" }).format(Number(value));
const time = () =>
  new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Bangkok",
    timeZoneName: "short",
  }).format(new Date());
function Field({
  label,
  children,
  note,
}: {
  label: string;
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium">
      {label}
      {children}
      {note && <span className="text-xs font-normal text-muted-foreground">{note}</span>}
    </label>
  );
}
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-background/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

function AotPaperGridPage() {
  const [config, setConfig] = useState<PaperGridConfig>({
    name: "AOT Core Grid",
    lowerPrice: "36.00",
    upperPrice: "44.00",
    referencePrice: "40.00",
    initialCash: "100000",
    initialInventory: "3000",
    levelCount: 8,
    mode: "ARITHMETIC",
    oneWayCostPct: "0.20",
    slippagePct: "0.05",
    maxPositionValue: "300000",
    maxActiveOrders: 20,
  });
  const [status, setStatus] = useState<PaperStrategyStatus>("DRAFT");
  const [simulation, setSimulation] = useState<ReturnType<typeof runAotPaperGridSimulation> | null>(
    null,
  );
  const calculation = useMemo(() => calculatePaperGrid(config), [config]);
  const blocked = calculation.validation.some((item) => item.level === "BLOCKED");
  const update = <K extends keyof PaperGridConfig>(key: K, value: PaperGridConfig[K]) =>
    setConfig((current) => ({ ...current, [key]: value }));
  const save = async () => {
    try {
      await createAotPaperStrategy({ data: { ...config, actorId: "local-maker@aegis" } });
      toast.success("Paper strategy draft saved to D1.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Draft save blocked");
    }
  };
  return (
    <AppShell>
      <PageHeader
        kicker="SET · AOT · PAPER SIMULATION"
        title={config.name}
        subtitle="Grid Planner and Paper Trading console. Market Data Source: Manual Paper Input · Historical Data: Not Connected."
        actions={
          <>
            <Badge className="border-warning/50 bg-warning/10 text-warning" variant="outline">
              {status}
            </Badge>
            <Button variant="outline" asChild>
              <Link to="/bots">
                <ArrowLeft className="h-4 w-4" />
                Bots cockpit
              </Link>
            </Button>
          </>
        }
      />
      <div className="space-y-5 p-6">
        <SafetyBanner
          title="PAPER TRADING — NO REAL MARKET ORDERS"
          text="This environment only simulates trading. No orders are sent to a broker, SET, or exchange."
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Environment" value="Paper Simulation" />
          <Metric label="Market data source" value="Manual Paper Input" />
          <Metric label="Strategy calculation" value={time()} />
          <Metric
            label="Last simulated price"
            value={simulation ? `${config.referencePrice} THB · ${time()}` : "Not applied"}
          />
        </div>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1.5fr)_minmax(280px,0.8fr)]">
          <Panel
            title="Strategy configuration"
            subtitle="AOT and its SET rules are domain configuration, not UI constants."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Strategy name">
                <Input value={config.name} onChange={(e) => update("name", e.target.value)} />
              </Field>
              <Field label="Grid type">
                <select
                  aria-label="Grid type"
                  className="h-9 rounded-md border bg-transparent px-3"
                  value={config.mode}
                  onChange={(e) => update("mode", e.target.value as PaperGridConfig["mode"])}
                >
                  <option value="ARITHMETIC">Arithmetic</option>
                  <option value="GEOMETRIC">Geometric</option>
                </select>
              </Field>
              {(
                [
                  ["Reference price", "referencePrice"],
                  ["Lower price", "lowerPrice"],
                  ["Upper price", "upperPrice"],
                  ["Initial cash", "initialCash"],
                  ["Initial AOT inventory", "initialInventory"],
                  ["One-way cost (%)", "oneWayCostPct"],
                  ["Estimated slippage (%)", "slippagePct"],
                  ["Maximum position value", "maxPositionValue"],
                ] as Array<[string, keyof PaperGridConfig]>
              ).map(([label, key]) => (
                <Field
                  key={key}
                  label={`${label} (THB${key === "initialInventory" ? " / shares" : ""})`}
                >
                  <Input
                    inputMode="decimal"
                    value={String(config[key])}
                    onChange={(e) => update(key, e.target.value as never)}
                  />
                </Field>
              ))}
              <Field label="Price intervals">
                <Input
                  type="number"
                  min={3}
                  value={config.levelCount}
                  onChange={(e) => update("levelCount", Number(e.target.value))}
                />
              </Field>
              <Field label="Maximum active orders">
                <Input
                  type="number"
                  min={1}
                  value={config.maxActiveOrders}
                  onChange={(e) => update("maxActiveOrders", Number(e.target.value))}
                />
              </Field>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => toast.success("Grid preview recalculated locally.")}
              >
                <Calculator className="h-4 w-4" />
                Run Grid Preview
              </Button>
              <Button disabled={blocked} onClick={save}>
                <Save className="h-4 w-4" />
                Save Draft
              </Button>
            </div>
          </Panel>
          <Panel
            title="Price chart & grid visualization"
            subtitle="Static preview of configured paper levels; no quote stream is connected."
          >
            <div className="relative h-[310px] overflow-hidden rounded-md border bg-gradient-to-b from-muted/50 to-background p-4">
              <div className="absolute inset-x-4 top-6 border-t border-dashed border-warning/70" />
              <div className="absolute inset-x-4 bottom-6 border-t border-dashed border-positive/60" />
              {calculation.levels.map((level, index) => (
                <div
                  key={level.index}
                  className="absolute left-4 right-4 flex items-center gap-2"
                  style={{
                    top: `${12 + index * (76 / Math.max(1, calculation.levels.length - 1))}%`,
                  }}
                >
                  <span className="w-20 text-xs font-mono">฿{level.price}</span>
                  <span
                    className={`h-px flex-1 ${level.side === "BUY" ? "bg-positive/60" : level.side === "SELL" ? "bg-warning/60" : "bg-foreground/70"}`}
                  />
                  <Badge variant="outline">{level.side}</Badge>
                </div>
              ))}
              <div className="absolute bottom-2 left-4 text-xs text-muted-foreground">
                Lower boundary
              </div>
              <div className="absolute right-4 top-2 text-xs text-muted-foreground">
                Upper boundary
              </div>
            </div>
          </Panel>
          <Panel
            title="Capital, inventory & risk"
            subtitle="Projected resources reserved by open paper orders."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Metric label="Required cash" value={thb(calculation.requiredCash)} />
              <Metric
                label="Required AOT inventory"
                value={`${calculation.requiredInventory} shares`}
              />
              <Metric label="Maximum capital deployed" value={thb(calculation.maxPositionValue)} />
              <Metric
                label="Board lot / tick"
                value={`${AOT_PAPER_RULES.boardLot} / ฿${AOT_PAPER_RULES.tickSize}`}
              />
              <Metric label="Current status" value={status} />
              <Metric
                label="Risk status"
                value={
                  blocked
                    ? "BLOCKED"
                    : calculation.validation.some((x) => x.level === "WARNING")
                      ? "WARNING"
                      : "PASS"
                }
              />
            </div>
            <div className="mt-4 space-y-2">
              {calculation.validation.map((item) => (
                <div
                  key={item.code}
                  className={`rounded border p-2 text-xs ${item.level === "BLOCKED" ? "border-destructive/40 text-destructive" : item.level === "WARNING" ? "border-warning/40 text-warning" : "border-positive/40 text-positive"}`}
                >
                  <strong>{item.level}</strong> · {item.message}
                </div>
              ))}
            </div>
          </Panel>
        </div>
        <Panel
          title="Paper strategy actions"
          subtitle="Lifecycle actions are enabled only for valid paper states; persistence requires a verified identity."
        >
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={blocked || status !== "DRAFT"}
              onClick={() => setStatus("PENDING_APPROVAL")}
            >
              Request Approval
            </Button>
            <Button disabled={status !== "APPROVED"} onClick={() => setStatus("RUNNING")}>
              <Play className="h-4 w-4" />
              Start Paper Strategy
            </Button>
            <Button disabled={status !== "RUNNING"} onClick={() => setStatus("PAUSED")}>
              <Pause className="h-4 w-4" />
              Pause
            </Button>
            <Button disabled={status !== "PAUSED"} onClick={() => setStatus("RUNNING")}>
              <Play className="h-4 w-4" />
              Resume
            </Button>
            <Button
              disabled={status !== "RUNNING" && status !== "PAUSED"}
              variant="outline"
              onClick={() => setStatus("STOPPED")}
            >
              <Square className="h-4 w-4" />
              Stop Strategy
            </Button>
          </div>
        </Panel>
        <Tabs defaultValue="ladder">
          <TabsList className="h-auto flex-wrap justify-start">
            <TabsTrigger value="ladder">Grid Ladder</TabsTrigger>
            <TabsTrigger value="orders">Orders & Fills</TabsTrigger>
            <TabsTrigger value="pnl">Position & P&amp;L</TabsTrigger>
            <TabsTrigger value="simulation">Simulation / Backtest</TabsTrigger>
            <TabsTrigger value="audit">Audit Log</TabsTrigger>
          </TabsList>
          <TabsContent value="ladder">
            <Panel title="Grid ladder" subtitle="REFERENCE remains visible and has no order.">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-sm">
                  <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      {[
                        "Grid",
                        "Side",
                        "Price",
                        "Quantity",
                        "Notional",
                        "Paired exit",
                        "Gross",
                        "Costs + slip",
                        "Net",
                        "Return",
                        "Status",
                      ].map((x) => (
                        <th className="p-2" key={x}>
                          {x}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {calculation.levels.map((row) => (
                      <tr key={row.index} className="border-b border-border/50">
                        <td className="p-2">{row.index}</td>
                        <td className="p-2">
                          <Badge variant="outline">{row.side}</Badge>
                        </td>
                        <td className="p-2 font-mono">฿{row.price}</td>
                        <td className="p-2">{row.quantity}</td>
                        <td className="p-2">{thb(row.notional)}</td>
                        <td className="p-2">{row.pairedPrice ? `฿${row.pairedPrice}` : "—"}</td>
                        <td className="p-2">{thb(row.grossProfit)}</td>
                        <td className="p-2">
                          {thb(Number(row.buyCost) + Number(row.sellCost) + Number(row.slippage))}
                        </td>
                        <td className="p-2 text-positive">{thb(row.netProfit)}</td>
                        <td className="p-2">{row.returnOnCapital}%</td>
                        <td className="p-2">{row.side === "REFERENCE" ? "NO ORDER" : "PREVIEW"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="orders">
            <Panel title="Open orders & fill history">
              <p className="text-sm text-muted-foreground">
                No strategy is running. After an approved strategy starts, paper orders and
                simulated fills are stored in D1. CSV export is intentionally deferred until
                persistent records exist.
              </p>
            </Panel>
          </TabsContent>
          <TabsContent value="pnl">
            <Panel title="Position & P&L">
              <div className="grid gap-3 sm:grid-cols-3">
                <Metric label="Grid profit" value="฿0.00" />
                <Metric label="Asset holding P&L" value="฿0.00" />
                <Metric label="Total P&L" value="฿0.00" />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Grid-cycle profit and asset holding P&amp;L remain separate by design.
              </p>
            </Panel>
          </TabsContent>
          <TabsContent value="simulation">
            <Panel
              title="Synthetic opening test"
              subtitle="Three deterministic synthetic OHLCV paths; this is a system test, never historical market evidence."
            >
              <Button
                disabled={blocked}
                onClick={() => {
                  try {
                    setSimulation(
                      runAotPaperGridSimulation({
                        lowerPrice: config.lowerPrice,
                        upperPrice: config.upperPrice,
                        referencePrice: config.referencePrice,
                        investment: config.initialCash,
                        gridCount: config.levelCount,
                        mode: config.mode,
                        assumedOneWayCostPct: config.oneWayCostPct,
                      }),
                    );
                    toast.success(
                      "Synthetic paths completed locally. No market-data request was made.",
                    );
                  } catch (error) {
                    toast.error(
                      error instanceof Error ? error.message : "Simulation failed closed",
                    );
                  }
                }}
              >
                <ShieldAlert className="h-4 w-4" />
                Run 3-seed opening test
              </Button>
              {simulation && (
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {simulation.map((row) => (
                    <Metric
                      key={row.seed}
                      label={`Seed ${row.seed} · train / hold-out`}
                      value={`${row.trainBars} / ${row.holdoutBars} bars · ${row.trainFillCandidates} / ${row.holdoutFillCandidates} candidates`}
                    />
                  ))}
                </div>
              )}
              <p className="mt-4 text-sm text-muted-foreground">
                Historical market data is not currently connected.
              </p>
            </Panel>
          </TabsContent>
          <TabsContent value="audit">
            <Panel title="Audit log">
              <p className="text-sm text-muted-foreground">
                Draft creation, validation, approvals, lifecycle transitions, prices, orders, fills,
                and risk events are written as immutable D1 paper audit events once a verified
                identity saves a strategy.
              </p>
            </Panel>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
