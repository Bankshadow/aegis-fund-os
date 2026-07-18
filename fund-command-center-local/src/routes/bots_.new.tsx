import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { buildExactGridPreview, type BotEnvironment, type GridMode } from "@/lib/grid-bot-domain";
import { readBinancePaperGridFeed } from "@/lib/binance-testnet.functions";
import { createAndStartTestnetGridBot, createGovernedGridBot } from "@/lib/grid-bot-governance.functions";
import { ArrowLeft, ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/bots_/new")({
  head: () => ({ meta: [{ title: "Create Grid Bot · Aegis Fund OS" }] }),
  loader: () => readBinancePaperGridFeed(),
  component: CreateBot,
});
const steps = [
  "Market & Environment",
  "Grid Strategy",
  "Risk & Controls",
  "Grid Preview",
  "Review & Submit",
];
function CreateBot() {
  const navigate = useNavigate();
  const feed = Route.useLoaderData();
  const mid = feed.midPrice ?? 64242;
  const [step, setStep] = useState(0);
  const [name, setName] = useState("BTC Institutional Range");
  const [env, setEnv] = useState<BotEnvironment>("PAPER");
  const [lower, setLower] = useState(String(Math.round(mid * 0.9)));
  const [upper, setUpper] = useState(String(Math.round(mid * 1.1)));
  const [grids, setGrids] = useState(20);
  const [mode, setMode] = useState<GridMode>("ARITHMETIC");
  const [investment, setInvestment] = useState("12000");
  const [tp, setTp] = useState("");
  const [sl, setSl] = useState("");
  const [maxDd, setMaxDd] = useState("8");
  const [ack, setAck] = useState(false);
  const [saving, setSaving] = useState(false);
  const preview = useMemo(() => {
    try {
      return {
        rows: buildExactGridPreview({
          lowerPrice: lower,
          upperPrice: upper,
          currentPrice: String(mid),
          investment,
          gridCount: grids,
          mode,
          feeRatePct: "0.1",
          tickSize: String(feed.tickSize ?? 0.01),
          stepSize: String(feed.stepSize ?? 0.00001),
          minNotional: String(feed.minNotional ?? 5),
        }),
        error: null,
      };
    } catch (e) {
      return { rows: [], error: e instanceof Error ? e.message : "Invalid parameters" };
    }
  }, [lower, upper, mid, investment, grids, mode, feed]);
  const risk =
    Number(investment) > 25000 ? "BLOCKED" : Number(maxDd) > 10 ? "PASS_WITH_WARNING" : "PASS";
  const canNext =
    (step !== 0 || name.trim().length > 0) &&
    (step !== 1 || !preview.error) &&
    (step !== 2 || risk !== "BLOCKED") &&
    (step !== 3 || !preview.error);
  const submitForApproval = async () => {
    if (!ack && step === 4) {
      toast.error("Please acknowledge the risk disclosure before creating the bot.");
      return;
    }
    setSaving(true);
    try {
      const request = {
        data: {
          name,
          environment: env,
          pair: "BTCUSDT",
          makerId: "local-maker@aegis",
          idempotencyKey: crypto.randomUUID(),
          submit: env !== "BINANCE_TESTNET",
          configuration: {
            lower,
            upper,
            grids,
            mode,
            investment,
            takeProfit: tp,
            stopLoss: sl,
            maxDrawdownPct: maxDd,
          },
        },
      };
      if (env === "BINANCE_TESTNET") {
        const result = await createAndStartTestnetGridBot(request);
        toast.success(`${result.bot.id} is RUNNING on Binance Spot Testnet (${result.orders.length} LIMIT orders).`);
        await navigate({ to: "/bots/$botId", params: { botId: result.bot.id } });
      } else {
        const bot = await createGovernedGridBot(request);
        toast.success(`${bot.id} saved as ${bot.state}. No exchange order sent.`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Governance storage failed closed");
    } finally {
      setSaving(false);
    }
  };
  return (
    <AppShell>
      <PageHeader
        kicker="Five-step controlled workflow"
        title="Create Spot Grid Bot"
        subtitle="Exact-decimal preview · Demo/Paper/Testnet only"
        actions={
          <Button variant="outline" asChild>
            <Link to="/bots">
              <ArrowLeft className="h-4 w-4" />
              Cockpit
            </Link>
          </Button>
        }
      />
      <div className="space-y-5 p-6">
        <div>
          <div className="mb-2 flex justify-between text-xs text-muted-foreground">
            <span>
              Step {step + 1} of 5 · {steps[step]}
            </span>
            <span>{(step + 1) * 20}%</span>
          </div>
          <Progress value={(step + 1) * 20} />
        </div>
        <Panel
          title={steps[step]}
          subtitle="Material changes are routed through existing Maker–Checker controls"
        >
          {step === 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Bot name">
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Field label="Exchange connection">
                <Input value="Binance Spot Testnet" disabled />
              </Field>
              <Field label="Environment">
                <select
                  aria-label="Environment"
                  value={env}
                  onChange={(e) => setEnv(e.target.value as BotEnvironment)}
                  className="h-9 w-full rounded-md border bg-transparent px-3"
                >
                  <option value="DEMO">DEMO</option>
                  <option value="PAPER">PAPER</option>
                  <option value="BINANCE_TESTNET">BINANCE TESTNET (read-only)</option>
                  <option disabled>LIVE (disabled)</option>
                </select>
              </Field>
              <Field label="Trading pair">
                <Input value="BTCUSDT" disabled />
              </Field>
              <Market label="Current price" value={String(mid)} />
              <Market label="Available BTC" value={String(feed.btcFree ?? "Unavailable")} />
              <Market label="Available USDT" value={String(feed.usdtFree ?? "Unavailable")} />
              <div className="rounded-md border p-3 text-sm">
                Connection: <Badge variant="outline">{feed.status}</Badge>
                <Button variant="link" asChild>
                  <Link to="/integrations">Manage in Integrations</Link>
                </Button>
              </div>
            </div>
          )}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <div className="mb-2 text-sm font-medium">
                  Deterministic recommendation profiles
                </div>
                <div className="grid gap-3 md:grid-cols-4">
                  {[
                    ["Short-Term Sideways", 0.95, 1.05, 30],
                    ["Balanced Range", 0.9, 1.1, 20],
                    ["Wide Volatility Range", 0.85, 1.15, 24],
                    ["Long-Term Accumulation", 0.75, 1.25, 36],
                  ].map(([label, lo, hi, n]) => (
                    <button
                      key={String(label)}
                      className="rounded-md border p-3 text-left hover:border-primary"
                      onClick={() => {
                        setLower(String(Math.round(mid * Number(lo))));
                        setUpper(String(Math.round(mid * Number(hi))));
                        setGrids(Number(n));
                      }}
                    >
                      <div className="font-medium">{label}</div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        ATR/volatility rule set · Medium confidence
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Lower price">
                  <Input type="number" value={lower} onChange={(e) => setLower(e.target.value)} />
                </Field>
                <Field label="Upper price">
                  <Input type="number" value={upper} onChange={(e) => setUpper(e.target.value)} />
                </Field>
                <Field label="Number of grids">
                  <Input
                    type="number"
                    min={2}
                    max={200}
                    value={grids}
                    onChange={(e) => setGrids(Number(e.target.value))}
                  />
                </Field>
                <Field label="Grid mode">
                  <select
                    aria-label="Grid mode"
                    value={mode}
                    onChange={(e) => setMode(e.target.value as GridMode)}
                    className="h-9 w-full rounded-md border bg-transparent px-3"
                  >
                    <option value="ARITHMETIC">Arithmetic</option>
                    <option value="GEOMETRIC">Geometric</option>
                  </select>
                </Field>
                <Field label="Investment">
                  <Input
                    type="number"
                    value={investment}
                    onChange={(e) => setInvestment(e.target.value)}
                  />
                </Field>
                <div className="flex items-end gap-2">
                  {[5, 10, 15].map((p) => (
                    <Button
                      key={p}
                      variant="outline"
                      onClick={() => {
                        setLower(String(Math.round(mid * (1 - p / 100))));
                        setUpper(String(Math.round(mid * (1 + p / 100))));
                      }}
                    >
                      ±{p}%
                    </Button>
                  ))}
                </div>
              </div>
              {preview.error && <div className="text-sm text-destructive">{preview.error}</div>}
            </div>
          )}
          {step === 2 && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Take-profit price">
                  <Input
                    type="number"
                    value={tp}
                    onChange={(e) => setTp(e.target.value)}
                    placeholder="Optional"
                  />
                </Field>
                <Field label="Stop-loss price">
                  <Input
                    type="number"
                    value={sl}
                    onChange={(e) => setSl(e.target.value)}
                    placeholder="Optional"
                  />
                </Field>
                <Field label="Maximum drawdown (%)">
                  <Input type="number" value={maxDd} onChange={(e) => setMaxDd(e.target.value)} />
                </Field>
                <Field label="Maximum open orders">
                  <Input value={String(grids)} disabled />
                </Field>
                <Field label="Stop behavior">
                  <select className="h-9 w-full rounded-md border bg-transparent px-3">
                    <option>Cancel orders and retain assets</option>
                    <option>Complete active cycle before stopping</option>
                    <option>Emergency stop immediately</option>
                  </select>
                </Field>
                <Field label="Start condition">
                  <select className="h-9 w-full rounded-md border bg-transparent px-3">
                    <option>Start immediately</option>
                    <option>Start at trigger price</option>
                    <option>Schedule start</option>
                  </select>
                </Field>
              </div>
              <div
                className={`rounded-md border p-4 ${risk === "BLOCKED" ? "border-destructive/50" : "border-positive/40"}`}
              >
                <div className="flex items-center gap-2 font-medium">
                  <ShieldAlert className="h-4 w-4" />
                  Risk Center result: {risk}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  Fund bot-cap limit 25,000 USDT · proposed {investment} USDT · remaining{" "}
                  {Math.max(0, 25000 - Number(investment)).toLocaleString()} USDT
                </div>
              </div>
            </div>
          )}
          {step === 3 && (
            <Preview
              rows={preview.rows}
              error={preview.error}
              lower={lower}
              upper={upper}
              current={String(mid)}
            />
          )}{" "}
          {step === 4 && (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                {[
                  ["Bot", name],
                  ["Environment", env],
                  ["Pair", "BTCUSDT"],
                  ["Range", `${lower}–${upper}`],
                  ["Grid", `${grids} · ${mode}`],
                  ["Investment", `${investment} USDT`],
                  ["Risk", risk],
                  ["Orders", String(preview.rows.length)],
                  ["Strategy", "Dual Grid 75/25 · v1.4"],
                ].map(([k, v]) => (
                  <div className="rounded-md border p-3" key={k}>
                    <div className="text-xs text-muted-foreground">{k}</div>
                    <div className="mt-1 font-medium">{v}</div>
                  </div>
                ))}
              </div>
              <label className="flex gap-2 rounded-md border p-4 text-sm">
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
                <span>
                  I understand that projected returns are estimates and actual outcomes depend on
                  market movement, execution price, liquidity, fees, and system availability.
                </span>
              </label>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() =>
                    toast("Simulation preview already calculated locally. No order sent.")
                  }
                >
                  Run Simulation
                </Button>
                <Button
                  disabled={!ack || risk === "BLOCKED" || saving}
                  onClick={submitForApproval}
                >
                  {env === "BINANCE_TESTNET" ? "Create & Start Testnet Bot" : "Create Bot for Approval"}
                </Button>
                <Button
                  disabled={!ack || risk === "BLOCKED" || env === "BINANCE_TESTNET"}
                  onClick={() =>
                    toast("Paper runner remains disabled until its governed execution phase.")
                  }
                >
                  Start Paper Bot
                </Button>
              </div>
            </div>
          )}
        </Panel>
        <div className="flex justify-between">
          <Button variant="outline" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            <ArrowLeft />
            Back
          </Button>
          {step < 4 && (
            <Button disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
              Continue
              <ArrowRight />
            </Button>
          )}
        </div>
      </div>
    </AppShell>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1 text-xs text-muted-foreground">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Market({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono">{value}</div>
    </div>
  );
}
function Preview({
  rows,
  error,
  lower,
  upper,
  current,
}: {
  rows: ReturnType<typeof buildExactGridPreview>;
  error: string | null;
  lower: string;
  upper: string;
  current: string;
}) {
  return (
    <div className="space-y-4">
      <div className="relative h-48 overflow-hidden rounded-md border bg-background/40">
        <div className="absolute inset-x-6 top-5 border-t border-warning">
          <span className="text-xs">Upper {upper}</span>
        </div>
        <div className="absolute inset-x-6 top-1/2 border-t-2 border-info">
          <span className="text-xs">Current {current}</span>
        </div>
        <div className="absolute inset-x-6 bottom-5 border-t border-positive">
          <span className="text-xs">Lower {lower}</span>
        </div>
        {rows.slice(0, 20).map((r, i) => (
          <div
            key={i}
            className={`absolute inset-x-20 border-t ${r.side === "BUY" ? "border-positive/25" : "border-warning/25"}`}
            style={{ top: `${10 + (i / Math.min(rows.length, 20)) * 80}%` }}
          />
        ))}
      </div>
      {error ? (
        <div className="text-destructive">{error}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                {["Grid", "Side", "Price", "Quantity", "Quote", "Fee", "Net profit", "State"].map(
                  (h) => (
                    <th className="p-2 text-left" key={h}>
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr className="border-t" key={r.grid}>
                  <td className="p-2">{r.grid}</td>
                  <td className="p-2">{r.side}</td>
                  <td className="p-2">{r.price}</td>
                  <td className="p-2">{r.quantity}</td>
                  <td className="p-2">{r.quoteValue}</td>
                  <td className="p-2">{r.estimatedFee}</td>
                  <td className="p-2">{r.estimatedNetProfit}</td>
                  <td className="p-2">
                    <Badge variant="outline">{r.initialState}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
