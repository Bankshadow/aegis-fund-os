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
import { getFixedGeometryWalkForward } from "@/lib/walk-forward.functions";
import { COSTS as RESEARCH_COSTS, type FixedGeometryResult } from "@/lib/aot-walkforward";
import { generateSyntheticAotBars, runAotPaperGridSimulation } from "@/lib/aot-paper-simulation";
import {
  analyzeMarketData,
  parseMarketCsv,
  runAotBacktest,
  type BacktestRun,
  type EndTreatment,
  type ExecutionMode,
  type MarketBar,
} from "@/lib/aot-backtest";
import { ArrowLeft, Calculator, Pause, Play, Save, ShieldAlert, Square } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
  const [historicalBars, setHistoricalBars] = useState<MarketBar[]>([]);
  const [intrabarBars, setIntrabarBars] = useState<MarketBar[]>([]);
  const [dataWarnings, setDataWarnings] = useState<string[]>([]);
  const [backtest, setBacktest] = useState<BacktestRun | null>(null);
  const [syntheticBacktests, setSyntheticBacktests] = useState<BacktestRun[]>([]);
  const [curveWindow, setCurveWindow] = useState<"ALL" | "30" | "90" | "180">("ALL");
  const [endTreatment, setEndTreatment] = useState<EndTreatment>("MARK_TO_MARKET");
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("CONSERVATIVE_OHLC");
  const [oosCheck, setOosCheck] = useState<FixedGeometryResult | null>(null);
  const [oosRunning, setOosRunning] = useState(false);
  const calculation = useMemo(() => calculatePaperGrid(config), [config]);
  const dataQuality = useMemo(() => analyzeMarketData(historicalBars), [historicalBars]);
  const insights = useMemo(() => {
    if (!backtest) return [];
    const items: Array<{ id: string; severity: "info" | "warning" | "critical"; title: string; detail: string }> = [];
    if (backtest.metrics.maxDrawdown > 30)
      items.push({ id: "DD_LIMIT", severity: "critical", title: "Drawdown exceeds 30% review limit", detail: `Observed ${backtest.metrics.maxDrawdown.toFixed(2)}% max drawdown.` });
    if (backtest.metrics.completedCycles < 30)
      items.push({ id: "SAMPLE_SIZE", severity: "warning", title: "Small realized-cycle sample", detail: `${backtest.metrics.completedCycles} completed cycles; validate with more history.` });
    if (backtest.metrics.unrealizedPnl > Math.abs(backtest.metrics.netPnl) * 0.5)
      items.push({ id: "INVENTORY_DEPENDENCE", severity: "warning", title: "Return depends materially on open inventory", detail: `Unrealized P/L is ${thb(backtest.metrics.unrealizedPnl)}; review liquidation and path risk.` });
    items.push({ id: "OOS_STATUS", severity: "warning", title: "Out-of-sample validation is not tested", detail: "This run is research evidence only; do not promote from full-period results alone." });
    return items;
  }, [backtest]);
  const blocked = calculation.validation.some((item) => item.level === "BLOCKED");
  const visibleCurve = useMemo(() => {
    if (!backtest) return [];
    if (curveWindow === "ALL") return backtest.equityCurve;
    return backtest.equityCurve.slice(-Number(curveWindow));
  }, [backtest, curveWindow]);
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
          title="Out-of-sample check — ตรวจ config นี้กับ 18 ช่วงที่ไม่เคยเห็น"
          subtitle="ตัวเลข backtest ด้านล่างเป็น in-sample เสมอ เพราะคุณเลือก geometry เองโดยเห็นกราฟแล้ว · ปุ่มนี้เอา geometry เดิมไปวัดบนข้อมูล AOT 2005–2026 ชุดเดียวกับงานวิจัย โดยไม่มีการเลือกอะไรจากข้อมูลที่ใช้วัด"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={oosRunning || !(Number(config.upperPrice) > Number(config.lowerPrice))}
              onClick={async () => {
                setOosRunning(true);
                try {
                  const result = await getFixedGeometryWalkForward({
                    data: {
                      lowerPrice: Number(config.lowerPrice),
                      upperPrice: Number(config.upperPrice),
                      gridCount: config.levelCount,
                      gridType: config.mode,
                      commissionRate: Number(config.oneWayCostPct),
                      slippageRate: Number(config.slippagePct),
                    },
                  });
                  setOosCheck(result);
                  toast.success(`ตรวจแล้ว ${result.summary.folds} ช่วง`);
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "Out-of-sample check failed");
                } finally {
                  setOosRunning(false);
                }
              }}
            >
              {oosRunning ? "กำลังรัน 18 ช่วง + ทดสอบความไว…" : "ทดสอบ config นี้แบบ walk-forward"}
            </Button>
            <Button variant="outline" asChild>
              <Link to="/walk-forward" search={{ variant: "baseline" }}>
                ดูบทเรียนเต็มใน Walk-Forward Lab →
              </Link>
            </Button>
          </div>

          {oosCheck && (
            <div className="mt-4 grid gap-4">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-muted-foreground">
                      <th className="p-2">แบบที่วัด</th>
                      <th className="p-2">คะแนนรวม (robust)</th>
                      <th className="p-2">แพ้/ชนะการถือเฉย ๆ</th>
                      <th className="p-2">ขาดทุนหนักสุด</th>
                      <th className="p-2">ช่วงที่ได้เทรดจริง</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { key: "abs", label: "ราคาตามที่ตั้งไว้เป๊ะ", row: oosCheck.summary.absolute },
                      { key: "sca", label: "รูปทรงเดิม ปรับระดับราคาตามยุค", row: oosCheck.summary.scaled },
                    ].map((entry) => (
                      <tr className="border-t" key={entry.key}>
                        <td className="p-2">{entry.label}</td>
                        <td className={`p-2 font-mono ${entry.row.meanRobust >= 0 ? "text-positive" : "text-destructive"}`}>
                          {entry.row.meanRobust.toFixed(2)}
                        </td>
                        <td className={`p-2 font-mono ${entry.row.meanAlpha >= 0 ? "text-positive" : "text-destructive"}`}>
                          {entry.row.meanAlpha.toFixed(2)}
                        </td>
                        <td className="p-2 font-mono">{entry.row.meanDrawdown.toFixed(1)}%</td>
                        <td className={`p-2 font-mono ${entry.row.engagedPct < 50 ? "text-destructive" : ""}`}>
                          {entry.row.engagedPct.toFixed(0)}%
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t text-muted-foreground">
                      <td className="p-2">ถือเฉย ๆ (คู่เทียบ)</td>
                      <td className="p-2 font-mono">{oosCheck.summary.meanBuyAndHoldRobust.toFixed(2)}</td>
                      <td className="p-2 font-mono">—</td>
                      <td className="p-2 font-mono">—</td>
                      <td className="p-2 font-mono">—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="rounded-md border p-3">
                <div className="text-xs text-muted-foreground">
                  ความไวต่อพารามิเตอร์ — ขยับจำนวนชั้น (±2) และความกว้าง (±10%) รวม{" "}
                  {oosCheck.summary.perturbationCount} แบบ
                </div>
                <div className="mt-1 flex flex-wrap items-baseline gap-2">
                  <span
                    className={`text-2xl font-semibold ${oosCheck.summary.flatSurfacePct >= 60 ? "text-positive" : "text-destructive"}`}
                  >
                    {oosCheck.summary.flatSurfacePct.toFixed(1)}%
                  </span>
                  <span className="text-xs text-muted-foreground">
                    ของแบบที่ขยับแล้วยังได้คะแนนเป็นบวก · เกณฑ์งานวิจัยต้อง ≥ 60% · ช่วงห่างคะแนนเฉลี่ยในแต่ละช่วง{" "}
                    {oosCheck.summary.meanPerturbationSpread.toFixed(1)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  ถ้าตัวเลขนี้ต่ำ แปลว่าผลดีอยู่ได้เฉพาะค่าที่ตั้งไว้เป๊ะ ๆ ขยับนิดเดียวก็พัง — นั่นคือ
                  “บังเอิญเจอจุดที่สวย” ไม่ใช่ความได้เปรียบที่ใช้ได้จริง
                </p>
              </div>
              <div className="rounded-md border border-warning/40 bg-warning/5 p-3 text-sm">
                <div className="mb-1 font-semibold">อ่านผลยังไง</div>
                <ul className="grid gap-1 text-muted-foreground">
                  <li>
                    • <strong>แถวแรก</strong> คือ grid ของคุณที่ราคาเป๊ะ ๆ — AOT วิ่งจากราว 5 ถึง 64 บาทในช่วงนี้
                    ถ้า "ช่วงที่ได้เทรดจริง" ต่ำ แปลว่า grid ของคุณอยู่คนละระดับราคากับตลาดในยุคนั้น ๆ
                    ไม่ใช่ว่ากลยุทธ์แย่ แต่มันผูกกับยุคที่คุณวาดมัน
                  </li>
                  <li>
                    • <strong>แถวสอง</strong> คงรูปทรงและจำนวนชั้นเดิม แต่ย้ายระดับราคาตามแต่ละยุค
                    (คำนวณจากข้อมูลช่วงตั้งค่าเท่านั้น ไม่แอบดูอนาคต) — แถวนี้บอกว่า <em>รูปทรง</em> ของ grid
                    มีค่าจริงไหม
                  </li>
                  <li>
                    • เทียบกับแถวล่างสุดเสมอ: คะแนนต้องมากกว่า 0 ถึงจะผ่านเกณฑ์ และควรดีกว่าการถือเฉย ๆ
                  </li>
                </ul>
              </div>
            </div>
          )}
        </Panel>

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
              title="Historical simulation / backtest"
              subtitle="Import OHLCV CSV to run the deterministic AOT engine. Synthetic paths remain a separate system test."
            >
              <div className="grid gap-3 rounded-md border border-border/60 bg-background/30 p-3 md:grid-cols-[1fr_auto_auto] md:items-end">
                <Field
                  label="Historical OHLCV CSV"
                  note="Columns: timestamp/date, open, high, low, close; optional adjustedClose, volume."
                >
                  <Input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      const parsed = parseMarketCsv(await file.text());
                      setHistoricalBars(parsed.bars);
                      setDataWarnings(parsed.warnings.map((warning) => warning.message));
                      setBacktest(null);
                      setSyntheticBacktests([]);
                      if (parsed.warnings.some((warning) => warning.severity === "BLOCKED"))
                        toast.error("Historical data validation blocked the run");
                      else toast.success(`Loaded ${parsed.bars.length} historical bars`);
                    }}
                  />
                </Field>
                <Field label="Intrabar OHLCV CSV (optional)" note="Use 1m/5m bars for Intrabar exact execution; these bars are never used for signal calculation.">
                  <Input type="file" accept=".csv,text/csv" onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    const parsed = parseMarketCsv(await file.text());
                    setIntrabarBars(parsed.bars);
                    if (parsed.warnings.some((warning) => warning.severity === "BLOCKED")) toast.error("Intrabar data validation blocked exact execution");
                    else toast.success(`Loaded ${parsed.bars.length} intrabar bars`);
                  }} />
                </Field>
                <Field label="End treatment">
                  <select
                    aria-label="Backtest end treatment"
                    className="h-9 rounded-md border bg-transparent px-3"
                    value={endTreatment}
                    onChange={(event) => setEndTreatment(event.target.value as EndTreatment)}
                  >
                    <option value="MARK_TO_MARKET">Mark-to-market</option>
                    <option value="FORCE_CLOSE">Force close</option>
                    <option value="KEEP_OPEN">Keep open</option>
                  </select>
                </Field>
                <Field label="Execution mode" note="Intrabar exact requires a lower-timeframe dataset; otherwise the engine falls back conservatively.">
                  <select aria-label="Execution mode" className="h-9 rounded-md border bg-transparent px-3" value={executionMode} onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)}>
                    <option value="CONSERVATIVE_OHLC">Conservative OHLC</option>
                    <option value="INTRABAR_EXACT">Intrabar exact</option>
                    <option value="OPTIMISTIC_OHLC">Optimistic OHLC (comparison)</option>
                    <option value="WORST_CASE">Worst-case path</option>
                  </select>
                </Field>
                <Button
                  disabled={!historicalBars.length || dataWarnings.length > 0}
                  onClick={() => {
                    try {
                      const result = runAotBacktest(
                        {
                          symbol: "AOT",
                          startDate: historicalBars[0].timestamp.slice(0, 10),
                          endDate: historicalBars[historicalBars.length - 1].timestamp.slice(0, 10),
                          initialCapital: Number(config.initialCash),
                          initialCash: Number(config.initialCash),
                          initialInventory: Number(config.initialInventory),
                          lowerPrice: Number(config.lowerPrice),
                          upperPrice: Number(config.upperPrice),
                          gridCount: config.levelCount,
                          gridType: config.mode,
                          tickSize: Number(AOT_PAPER_RULES.tickSize),
                          boardLot: Number(AOT_PAPER_RULES.boardLot),
                          commissionRate: Number(config.oneWayCostPct),
                          // Match the research cost model (src/lib/aot-walkforward.ts
                          // COSTS); this was 0 here, so the same inputs gave slightly
                          // different numbers on this page than in the E-series.
                          exchangeFeeRate: RESEARCH_COSTS.exchangeFeeRate,
                          vatRate: 7,
                          slippageRate: Number(config.slippagePct),
                          fillModel: "CONSERVATIVE",
                          endTreatment,
                          dividendInclusion: true,
                          dividendReinvestment: false,
                          cashConstraint: true,
                          executionMode,
                        },
                        historicalBars,
                        [],
                        undefined,
                        intrabarBars,
                      );
                      setBacktest(result);
                      toast.success(
                        `Backtest completed: ${result.metrics.fills} fills, ${result.metrics.completedCycles} cycles`,
                      );
                    } catch (error) {
                      toast.error(
                        error instanceof Error ? error.message : "Backtest failed closed",
                      );
                    }
                  }}
                >
                  Run historical backtest
                </Button>
                <Button
                  variant="outline"
                  disabled={blocked}
                  onClick={() => {
                    try {
                      const seeds = [101, 202, 303];
                      const runs = seeds.map((seed) => {
                        const bars = generateSyntheticAotBars(config.referencePrice, seed, 120).map(
                          (bar, index) =>
                            ({
                              timestamp: new Date(Date.UTC(2024, 0, 1 + index)).toISOString(),
                              open: Number(bar.open),
                              high: Number(bar.high),
                              low: Number(bar.low),
                              close: Number(bar.close),
                              volume: bar.volume,
                            }) satisfies MarketBar,
                        );
                        return runAotBacktest(
                          {
                            symbol: "AOT-SYNTHETIC",
                            startDate: bars[0].timestamp.slice(0, 10),
                            endDate: bars[bars.length - 1].timestamp.slice(0, 10),
                            initialCapital: Number(config.initialCash),
                            initialCash: Number(config.initialCash),
                            initialInventory: Number(config.initialInventory),
                            lowerPrice: Number(config.lowerPrice),
                            upperPrice: Number(config.upperPrice),
                            gridCount: config.levelCount,
                            gridType: config.mode,
                            tickSize: Number(AOT_PAPER_RULES.tickSize),
                            boardLot: Number(AOT_PAPER_RULES.boardLot),
                            commissionRate: Number(config.oneWayCostPct),
                            exchangeFeeRate: 0,
                            vatRate: 7,
                            slippageRate: Number(config.slippagePct),
                            fillModel: "CONSERVATIVE",
                            endTreatment,
                            dividendInclusion: false,
                            dividendReinvestment: false,
                            cashConstraint: true,
                          },
                          bars,
                        );
                      });
                      setSyntheticBacktests(runs);
                      toast.success("Synthetic backtest completed across 3 deterministic seeds.");
                    } catch (error) {
                      toast.error(
                        error instanceof Error ? error.message : "Synthetic backtest failed closed",
                      );
                    }
                  }}
                >
                  Run synthetic test (3 seeds)
                </Button>
              </div>
              <div className="mt-3 rounded border border-warning/40 bg-warning/5 p-3 text-xs text-warning">
                Synthetic data is for wiring, validation and regression testing only. It is not
                historical-market evidence and must not be used to promote a strategy.
              </div>
              {dataWarnings.map((warning) => (
                <div
                  key={warning}
                  className="mt-3 rounded border border-destructive/40 p-2 text-xs text-destructive"
                >
                  BLOCKED · {warning}
                </div>
              ))}
              {backtest && (
                // The caveat belongs where the number is, not only in a side panel:
                // people read the headline figure first and the disclaimer never.
                <div className="mt-4 rounded-md border border-warning/50 bg-warning/10 p-3 text-sm">
                  <span className="font-semibold">ตัวเลขชุดนี้เป็น in-sample</span> — geometry ถูกเลือกโดยคนที่เห็นกราฟช่วงนี้แล้ว
                  ผลจึงดูดีได้เองโดยไม่ต้องมีความได้เปรียบจริง ใช้ปุ่ม “ทดสอบ config นี้แบบ walk-forward” ด้านบน
                  เพื่อดูผลบนช่วงที่ยังไม่เคยเห็น
                </div>
              )}
              {backtest && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    label="Final portfolio value"
                    value={thb(backtest.metrics.finalPortfolioValue)}
                  />
                  <Metric label="Net P/L" value={thb(backtest.metrics.netPnl)} />
                  <Metric
                    label="CAGR / Max DD"
                    value={`${backtest.metrics.cagr?.toFixed(2) ?? "—"}% / ${backtest.metrics.maxDrawdown.toFixed(2)}%`}
                  />
                  <Metric
                    label="Fills / cycles"
                    value={`${backtest.metrics.fills} / ${backtest.metrics.completedCycles}`}
                  />
                  <Metric
                    label="Realized / unrealized"
                    value={`${thb(backtest.metrics.realizedPnl)} / ${thb(backtest.metrics.unrealizedPnl)}`}
                  />
                  <Metric
                    label="Fees / slippage"
                    value={`${thb(backtest.metrics.totalFees)} / ${thb(backtest.metrics.totalSlippage)}`}
                  />
                  <Metric
                    label="Buy & hold / alpha"
                    value={`${backtest.metrics.buyAndHoldReturn?.toFixed(2) ?? "—"}% / ${backtest.metrics.alpha?.toFixed(2) ?? "—"}%`}
                  />
                  <Metric
                    label="Ending inventory / open lots"
                    value={`${backtest.metrics.endingInventory} / ${backtest.metrics.openLots}`}
                  />
                </div>
              )}
              {backtest && (
                <div className="mt-4 grid gap-4 lg:grid-cols-3">
                  <Panel title="P/L reconciliation" subtitle="Independent accounting check">
                    <div className="grid gap-2 text-sm">
                      <div className="flex justify-between">
                        <span>Initial equity</span>
                        <span>{thb(backtest.metrics.startEquity)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Ending cash</span>
                        <span>{thb(backtest.metrics.endingCash)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Ending inventory value</span>
                        <span>{thb(backtest.metrics.endingInventoryMarketValue)}</span>
                      </div>
                      <div className="flex justify-between border-t pt-2 font-semibold">
                        <span>Reported Net P/L</span>
                        <span>{thb(backtest.metrics.netPnl)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Realized + unrealized + dividends</span>
                        <span>
                          {thb(
                            backtest.metrics.realizedPnl +
                              backtest.metrics.unrealizedPnl +
                              backtest.metrics.dividendIncome,
                          )}
                        </span>
                      </div>
                      <div
                        className={`mt-1 rounded border p-2 text-xs ${backtest.metrics.isReconciled ? "border-positive/40 text-positive" : "border-destructive/40 text-destructive"}`}
                      >
                        {backtest.metrics.isReconciled
                          ? "Passed: difference within ฿0.01 tolerance"
                          : `Failed: difference ${thb(backtest.metrics.reconciliationDifference)}`}
                      </div>
                    </div>
                  </Panel>
                  <Panel title="Trade quality" subtitle="Only realized cycles are scored">
                    <div className="grid gap-2 text-sm sm:grid-cols-2">
                      <Metric
                        label="Win rate"
                        value={
                          backtest.metrics.winRate == null
                            ? "N/A"
                            : `${backtest.metrics.winRate.toFixed(2)}%`
                        }
                      />
                      <Metric
                        label="Profit factor"
                        value={
                          backtest.metrics.profitFactor == null
                            ? "N/A"
                            : backtest.metrics.profitFactor.toFixed(2)
                        }
                      />
                      <Metric
                        label="Expectancy / cycle"
                        value={
                          backtest.metrics.expectancyPerCycle == null
                            ? "N/A"
                            : thb(backtest.metrics.expectancyPerCycle)
                        }
                      />
                      <Metric
                        label="Avg win / loss"
                        value={
                          backtest.metrics.averageWin == null
                            ? "N/A"
                            : `${thb(backtest.metrics.averageWin)} / ${thb(backtest.metrics.averageLoss ?? 0)}`
                        }
                      />
                      <Metric
                        label="Max consecutive losses"
                        value={String(backtest.metrics.maxConsecutiveLosses)}
                      />
                      <Metric
                        label="Recovery / underwater"
                        value={`${backtest.metrics.longestRecoveryBars} bars / ${backtest.metrics.timeUnderwaterPct.toFixed(2)}%`}
                      />
                      <Metric
                        label="Peak capital utilization"
                        value={`${((backtest.metrics.maxCapitalDeployed / Math.max(backtest.metrics.startEquity, 1)) * 100).toFixed(2)}%`}
                      />
                      <Metric
                        label="Ending inventory exposure"
                        value={`${((backtest.metrics.endingInventoryMarketValue / Math.max(backtest.metrics.finalPortfolioValue, 1)) * 100).toFixed(2)}%`}
                      />
                    </div>
                  </Panel>
                  <Panel title="Backtest confidence" subtitle="What has and has not been tested">
                    <div className="grid gap-2 text-sm">
                      {[
                        ["P/L reconciliation", backtest.metrics.isReconciled ? "Passed" : "Failed"],
                        ["Look-ahead bias", "Passed: chronological OHLC"],
                        // These reflect the out-of-sample check above rather than
                        // being permanently "Not tested" with no way to act on it.
                        [
                          "Out-of-sample",
                          oosCheck ? `Tested: ${oosCheck.summary.folds} unseen periods` : "Not tested",
                        ],
                        [
                          "Walk-forward",
                          oosCheck
                            ? `Tested: robust ${oosCheck.summary.scaled.meanRobust.toFixed(2)} (shape-adjusted)`
                            : "Not tested",
                        ],
                        [
                          "Parameter sensitivity",
                          oosCheck
                            ? `Tested: ${oosCheck.summary.flatSurfacePct.toFixed(0)}% of ${oosCheck.summary.perturbationCount} nudged variants stay positive`
                            : "Not tested",
                        ],
                        [
                          "Ending positions",
                          backtest.metrics.endingInventory === 0
                            ? "Liquidated"
                            : "Open / mark-to-market",
                        ],
                      ].map(([label, value]) => (
                        <div
                          className="flex items-start justify-between gap-2 border-b border-border/40 pb-1"
                          key={label}
                        >
                          <span className="text-muted-foreground">{label}</span>
                          <span
                            className={
                              value === "Passed" || value === "Liquidated" || value.startsWith("Tested")
                                ? "text-positive"
                                : value === "Failed"
                                  ? "text-destructive"
                                  : "text-warning"
                            }
                          >
                            {value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Panel>
                </div>
              )}
              {backtest && (
                <div className="mt-4 rounded-md border border-warning/40 bg-warning/5 p-4 text-sm">
                  <div className="mb-2 font-semibold">Backtest interpretation</div>
                  <ul className="grid gap-1 text-muted-foreground">
                    {backtest.metrics.maxDrawdown > 30 && (
                      <li>
                        • High drawdown: {backtest.metrics.maxDrawdown.toFixed(2)}% requires
                        explicit risk-budget review.
                      </li>
                    )}
                    {backtest.metrics.unrealizedPnl >
                      Math.max(1, Math.abs(backtest.metrics.netPnl) * 0.5) && (
                      <li>
                        • A material share of profit is unrealized and depends on open inventory
                        valuation.
                      </li>
                    )}
                    {backtest.metrics.durationYears < 1 && (
                      <li>
                        • Annualized figures are based on less than one year and may be unstable.
                      </li>
                    )}
                    {backtest.metrics.completedCycles < 30 && (
                      <li>
                        • Sample size is limited: {backtest.metrics.completedCycles} completed
                        cycles.
                      </li>
                    )}
                    {backtest.metrics.completedCycles >= 30 &&
                      backtest.metrics.maxDrawdown <= 30 && (
                        <li>
                          • Results should still be validated out-of-sample before any promotion
                          decision.
                        </li>
                      )}
                  </ul>
                </div>
              )}
              {backtest && (
                <div className="mt-4 grid gap-4 lg:grid-cols-[1.15fr_1fr]">
                  <Panel title="Data lineage & reproducibility" subtitle="Every run is traceable and exportable">
                    <div className="grid gap-2 text-sm sm:grid-cols-2">
                      <Metric label="Run ID" value={backtest.metadata.runId} />
                      <Metric label="Configuration hash" value={backtest.metadata.configurationHash} />
                      <Metric label="Dataset" value={`${backtest.metadata.datasetId} / ${backtest.metadata.datasetVersion}`} />
                      <Metric label="Data source" value={backtest.metadata.dataSource} />
                      <Metric label="Engine / environment" value={`${backtest.metadata.engineVersion} / ${backtest.metadata.environment}`} />
                      <Metric label="Execution mode" value={`${backtest.metadata.executionMode}${backtest.metadata.intrabarFallback ? " / intrabar data unavailable" : ""}`} />
                      <Metric label="Timezone / currency" value={`${backtest.metadata.timezone} / ${backtest.metadata.currency}`} />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard?.writeText(backtest.metadata.runId); toast.success("Run ID copied"); }}>Copy Run ID</Button>
                      <Button size="sm" variant="outline" onClick={() => {
                        const blob = new Blob([JSON.stringify({ metadata: backtest.metadata, config: backtest.config }, null, 2)], { type: "application/json" });
                        const url = URL.createObjectURL(blob);
                        const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${backtest.metadata.runId}-configuration.json`; anchor.click(); URL.revokeObjectURL(url);
                      }}>Export configuration</Button>
                    </div>
                  </Panel>
                  <Panel title="Data quality report" subtitle="Validation is shown before relying on results">
                    <div className="grid gap-2 text-sm sm:grid-cols-2">
                      <Metric label="Bars" value={String(dataQuality.bars)} />
                      <Metric label="Duplicate timestamps" value={String(dataQuality.duplicates)} />
                      <Metric label="Missing OHLC" value={String(dataQuality.missingOhlcv)} />
                      <Metric label="Invalid prices" value={String(dataQuality.invalidPrices)} />
                      <Metric label="Negative volume" value={String(dataQuality.negativeVolume)} />
                      <Metric label="Abnormal gaps" value={String(dataQuality.abnormalGaps)} />
                    </div>
                    <div className={`mt-3 rounded border p-2 text-xs ${dataQuality.duplicates || dataQuality.missingOhlcv || dataQuality.invalidPrices ? "border-destructive/40 text-destructive" : "border-positive/40 text-positive"}`}>
                      {dataQuality.duplicates || dataQuality.missingOhlcv || dataQuality.invalidPrices ? "Blocked: data quality issues require review." : "Passed: no blocking OHLC quality issues detected."}
                    </div>
                  </Panel>
                  <Panel title="Deterministic insights" subtitle="Rule-based evidence linked to observed metrics">
                    <div className="space-y-2 text-sm">
                      {insights.map((item) => (
                        <div key={item.id} className={`rounded border p-2 ${item.severity === "critical" ? "border-destructive/50 text-destructive" : item.severity === "warning" ? "border-warning/50 text-warning" : "border-positive/50 text-positive"}`}>
                          <div className="font-medium">{item.title}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{item.id}: {item.detail}</div>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  <Panel title="Event-driven execution trace" subtitle={`${backtest.events.length} ordered events; market → decision → order → fill → ledger → valuation`}>
                    <div className="max-h-64 space-y-1 overflow-auto text-xs">
                      {backtest.events.slice(-16).map((event) => (
                        <div key={event.id} className="flex items-center gap-2 border-b border-border/30 pb-1">
                          <span className="w-8 text-muted-foreground">#{event.sequence}</span>
                          <span className="font-medium">{event.type}</span>
                          <span className="truncate text-muted-foreground">{event.timestamp}</span>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  <div className="rounded-md border border-border/60 bg-background/20 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold">Backtest report</div>
                        <div className="text-xs text-muted-foreground">
                          {backtest.config.symbol} · {backtest.config.startDate} →{" "}
                          {backtest.config.endDate}
                        </div>
                      </div>
                      <Badge variant="outline" className="border-warning/50 text-warning">
                        PAPER RESEARCH
                      </Badge>
                    </div>
                    <div className="grid gap-2 text-sm sm:grid-cols-2">
                      <div className="rounded border border-border/50 p-2">
                        <div className="text-xs text-muted-foreground">Grid / levels</div>
                        <div className="font-medium">
                          {backtest.config.gridType} / {backtest.config.gridCount}
                        </div>
                      </div>
                      <div className="rounded border border-border/50 p-2">
                        <div className="text-xs text-muted-foreground">Price range</div>
                        <div className="font-medium">
                          {backtest.config.lowerPrice.toFixed(2)} –{" "}
                          {backtest.config.upperPrice.toFixed(2)}
                        </div>
                      </div>
                      <div className="rounded border border-border/50 p-2">
                        <div className="text-xs text-muted-foreground">
                          Fill model / end treatment
                        </div>
                        <div className="font-medium">
                          {backtest.config.fillModel} / {backtest.config.endTreatment}
                        </div>
                      </div>
                      <div className="rounded border border-border/50 p-2">
                        <div className="text-xs text-muted-foreground">Costs / slippage</div>
                        <div className="font-medium">
                          {backtest.config.commissionRate.toFixed(2)}% /{" "}
                          {backtest.config.slippageRate.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 text-xs leading-5 text-muted-foreground">
                      This report uses conservative OHLC execution, cash constraints, board-lot
                      rounding and mark-to-market accounting. It is suitable for research review,
                      not a promise of future returns.
                    </div>
                  </div>
                  <div className="rounded-md border border-border/60 bg-background/20 p-4">
                    <div className="mb-3 text-sm font-semibold">Execution quality & open risk</div>
                    <div className="grid gap-2 text-sm sm:grid-cols-2">
                      <div>
                        <span className="text-muted-foreground">Fill rate</span>
                        <div className="font-semibold">
                          {backtest.metrics.orders
                            ? ((backtest.metrics.fills / backtest.metrics.orders) * 100).toFixed(1)
                            : "0.0"}
                          %
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Cycle completion</span>
                        <div className="font-semibold">
                          {backtest.metrics.fills
                            ? (
                                (backtest.metrics.completedCycles /
                                  Math.max(1, backtest.metrics.buyFills)) *
                                100
                              ).toFixed(1)
                            : "0.0"}
                          %
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Grid profit</span>
                        <div className="font-semibold">{thb(backtest.metrics.gridProfit)}</div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Ambiguous bars</span>
                        <div className="font-semibold">{backtest.metrics.ambiguousBars}</div>
                      </div>
                    </div>
                    {backtest.metrics.ambiguousBars > 0 && (
                      <div className="mt-3 rounded border border-warning/40 bg-warning/5 p-2 text-xs text-warning">
                        Intraday order is unknowable for {backtest.metrics.ambiguousBars} bar(s);
                        conservative fill handling was applied.
                      </div>
                    )}
                  </div>
                </div>
              )}
              {backtest && (
                <div className="mt-4 rounded-md border border-border/60 bg-background/20 p-3">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium">Equity & drawdown chart</div>
                      <div className="text-xs text-muted-foreground">
                        Showing {visibleCurve.length} of {backtest.equityCurve.length} bars
                      </div>
                    </div>
                    <select
                      aria-label="Backtest chart range"
                      className="h-9 rounded-md border bg-transparent px-3 text-sm"
                      value={curveWindow}
                      onChange={(event) =>
                        setCurveWindow(event.target.value as "ALL" | "30" | "90" | "180")
                      }
                    >
                      <option value="30">Last 30 bars</option>
                      <option value="90">Last 90 bars</option>
                      <option value="180">Last 180 bars</option>
                      <option value="ALL">All bars</option>
                    </select>
                  </div>
                  <div className="h-[280px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={visibleCurve.map((point) => ({
                          ...point,
                          label: point.timestamp.slice(0, 10),
                        }))}
                        margin={{ top: 8, right: 12, left: 8, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis dataKey="label" minTickGap={28} />
                        <YAxis
                          yAxisId="equity"
                          tickFormatter={(value) => `฿${Math.round(value / 1000)}k`}
                        />
                        <YAxis
                          yAxisId="drawdown"
                          orientation="right"
                          tickFormatter={(value) => `${value}%`}
                        />
                        <Tooltip
                          formatter={(value: number, name: string) =>
                            name === "Drawdown" ? `${value.toFixed(2)}%` : thb(value)
                          }
                        />
                        <Legend />
                        <Line
                          yAxisId="equity"
                          type="monotone"
                          dataKey="equity"
                          name="Equity"
                          stroke="#38bdf8"
                          dot={false}
                          strokeWidth={2}
                        />
                        <Line
                          yAxisId="equity"
                          type="monotone"
                          dataKey="cash"
                          name="Cash"
                          stroke="#a78bfa"
                          dot={false}
                          strokeWidth={1.5}
                        />
                        <Line
                          yAxisId="drawdown"
                          type="monotone"
                          dataKey="drawdown"
                          name="Drawdown"
                          stroke="#fb7185"
                          dot={false}
                          strokeWidth={1.5}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              {backtest && (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full min-w-[720px] text-sm">
                    <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                      <tr>
                        {["Timestamp", "Equity", "Cash", "Inventory value", "Drawdown"].map(
                          (header) => (
                            <th className="p-2" key={header}>
                              {header}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleCurve.map((point) => (
                        <tr className="border-b border-border/50" key={point.timestamp}>
                          <td className="p-2">{point.timestamp}</td>
                          <td className="p-2">{thb(point.equity)}</td>
                          <td className="p-2">{thb(point.cash)}</td>
                          <td className="p-2">{thb(point.inventoryValue)}</td>
                          <td className="p-2">{point.drawdown.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {backtest && backtest.metrics.monthly.length > 0 && (
                <div className="mt-4 overflow-x-auto">
                  <div className="mb-2 text-sm font-medium">Monthly return heatmap data</div>
                  <table className="w-full min-w-[520px] text-sm">
                    <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                      <tr>
                        {["Month", "Return", "Net P/L", "Cycles"].map((header) => (
                          <th className="p-2" key={header}>
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.metrics.monthly.map((point) => (
                        <tr
                          className="border-b border-border/50"
                          key={`${point.year}-${point.month}`}
                        >
                          <td className="p-2">
                            {point.year}-{point.month}
                          </td>
                          <td className="p-2">{point.return.toFixed(2)}%</td>
                          <td className="p-2">{thb(point.netPnl)}</td>
                          <td className="p-2">{point.cycles}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {backtest && backtest.metrics.annual.length > 0 && (
                <div className="mt-4 overflow-x-auto">
                  <div className="mb-2 text-sm font-medium">Annual performance review</div>
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                      <tr>
                        {["Year", "Return", "Net P/L", "Max DD", "Fills", "Cycles", "Alpha"].map(
                          (header) => (
                            <th className="p-2" key={header}>
                              {header}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.metrics.annual.map((row) => (
                        <tr className="border-b border-border/50" key={row.year}>
                          <td className="p-2 font-medium">{row.year}</td>
                          <td className="p-2">{row.return.toFixed(2)}%</td>
                          <td className="p-2">{thb(row.netPnl)}</td>
                          <td className="p-2">{row.maxDrawdown.toFixed(2)}%</td>
                          <td className="p-2">{row.fills}</td>
                          <td className="p-2">{row.completedCycles}</td>
                          <td className="p-2">
                            {row.alpha == null ? "—" : `${row.alpha.toFixed(2)}%`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {syntheticBacktests.length > 0 && (
                <div className="mt-4 overflow-x-auto">
                  <div className="mb-2 text-sm font-medium">Synthetic seed comparison</div>
                  <table className="w-full min-w-[560px] text-sm">
                    <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                      <tr>
                        {["Seed", "Final value", "Net P/L", "Max DD", "Fills / cycles"].map(
                          (header) => (
                            <th className="p-2" key={header}>
                              {header}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {[101, 202, 303].map((seed, index) => {
                        const run = syntheticBacktests[index];
                        return (
                          <tr className="border-b border-border/50" key={seed}>
                            <td className="p-2">{seed}</td>
                            <td className="p-2">{thb(run.metrics.finalPortfolioValue)}</td>
                            <td className="p-2">{thb(run.metrics.netPnl)}</td>
                            <td className="p-2">{run.metrics.maxDrawdown.toFixed(2)}%</td>
                            <td className="p-2">
                              {run.metrics.fills} / {run.metrics.completedCycles}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="mt-6 border-t border-border/60 pt-4">
                <div className="mb-2 text-sm font-medium">Synthetic opening test</div>
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
              </div>
              <p className="mt-4 text-sm text-muted-foreground">
                Imported historical data is validated before execution; no broker or exchange
                request is made.
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
