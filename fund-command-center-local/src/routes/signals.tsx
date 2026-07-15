import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CheckCircle2, Eye, RadioTower } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/signals")({
  head: () => ({ meta: [{ title: "Signals · Aegis Fund OS" }] }),
  component: SignalsPage,
});

type SignalRow = {
  id: string;
  time: string;
  source: string;
  symbol: string;
  signal: "LONG" | "SHORT" | "FLAT";
  confidence: number;
  regime: string;
  reason: string;
  status: "New" | "Reviewed" | "Expired";
};

const initialSignals: SignalRow[] = [
  {
    id: "SIG-2401",
    time: "10:46:02",
    source: "Percentile Router",
    symbol: "BTC/USDT",
    signal: "FLAT",
    confidence: 92,
    regime: "High volatility",
    reason: "Price percentile crossed 90th band; grid eligibility suspended.",
    status: "New",
  },
  {
    id: "SIG-2400",
    time: "10:41:18",
    source: "Funding RV Observer",
    symbol: "BTC-PERP / ETH-PERP",
    signal: "SHORT",
    confidence: 76,
    regime: "Relative value",
    reason: "Funding spread widened to 2.1 standard deviations.",
    status: "New",
  },
  {
    id: "SIG-2399",
    time: "10:30:44",
    source: "Dual Grid 75/25",
    symbol: "ETH/USDT",
    signal: "LONG",
    confidence: 68,
    regime: "Sideways",
    reason: "Lower grid zone touched with positive cost-adjusted edge estimate.",
    status: "Reviewed",
  },
  {
    id: "SIG-2398",
    time: "09:52:13",
    source: "Risk Overlay",
    symbol: "PORTFOLIO",
    signal: "FLAT",
    confidence: 100,
    regime: "Limit alert",
    reason: "Gross exposure approached 95% soft limit.",
    status: "Reviewed",
  },
  {
    id: "SIG-2397",
    time: "09:10:05",
    source: "Dual Grid 75/25",
    symbol: "BTC/USDT",
    signal: "LONG",
    confidence: 61,
    regime: "Sideways",
    reason: "Signal expired before paper bot acknowledgement.",
    status: "Expired",
  },
];

function signalClass(signal: SignalRow["signal"]) {
  if (signal === "LONG") return "border-positive/35 text-positive";
  if (signal === "SHORT") return "border-warning/35 text-warning";
  return "border-info/35 text-info";
}

function SignalsPage() {
  const [signals, setSignals] = useState(initialSignals);
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(initialSignals[0].id);
  const rows = useMemo(
    () => signals.filter((s) => filter === "all" || s.status.toLowerCase() === filter),
    [signals, filter],
  );
  const selected = signals.find((s) => s.id === selectedId) ?? signals[0];

  const review = (id: string) => {
    setSignals((items) => items.map((s) => (s.id === id ? { ...s, status: "Reviewed" } : s)));
    toast.success("Signal marked reviewed. No order was created.");
  };

  return (
    <AppShell>
      <PageHeader
        kicker="P2 · Decision support"
        title="Signals"
        subtitle="Explainable signal inbox with regime, confidence and operator acknowledgement."
        actions={
          <Button size="sm" onClick={() => toast("Signal feed refreshed (demo)")}>
            <RadioTower className="h-3.5 w-3.5" /> Refresh feed
          </Button>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Signals are advisory"
          text="Reviewing or acknowledging a signal never creates an order. Execution remains a separate paper-only workflow."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="New signals"
            value={String(signals.filter((s) => s.status === "New").length)}
            tone="warning"
          />
          <MetricCard label="Sources online" value="4 / 4" tone="positive" />
          <MetricCard label="Median confidence" value="76%" />
          <MetricCard label="Orders created" value="0" sub="Advisory boundary" />
        </div>
        <div className="grid gap-6 xl:grid-cols-[1.65fr_1fr]">
          <Panel
            title="Signal inbox"
            subtitle="Newest first"
            actions={
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="reviewed">Reviewed</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                </SelectContent>
              </Select>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular">
                <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b border-border/60">
                    <th className="py-2 pr-4 text-left">Time</th>
                    <th className="py-2 pr-4 text-left">Source</th>
                    <th className="py-2 pr-4 text-left">Symbol</th>
                    <th className="py-2 pr-4 text-left">Signal</th>
                    <th className="py-2 pr-4 text-right">Confidence</th>
                    <th className="py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((signal) => (
                    <tr
                      key={signal.id}
                      onClick={() => setSelectedId(signal.id)}
                      className={`cursor-pointer border-b border-border/40 hover:bg-accent/30 ${selectedId === signal.id ? "bg-primary/5" : ""}`}
                    >
                      <td className="py-3 pr-4">
                        <div>{signal.time}</div>
                        <div className="font-mono text-[10px] text-muted-foreground">
                          {signal.id}
                        </div>
                      </td>
                      <td className="py-3 pr-4">{signal.source}</td>
                      <td className="py-3 pr-4 font-mono text-xs">{signal.symbol}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="outline" className={signalClass(signal.signal)}>
                          {signal.signal}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-right font-mono">{signal.confidence}%</td>
                      <td className="py-3 text-xs text-muted-foreground">{signal.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title={selected.id} subtitle={`${selected.source} · ${selected.symbol}`}>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className={signalClass(selected.signal)}>
                  {selected.signal}
                </Badge>
                <span className="text-xs text-muted-foreground">{selected.regime}</span>
              </div>
              <div>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span>Confidence</span>
                  <span className="font-mono">{selected.confidence}%</span>
                </div>
                <Progress value={selected.confidence} className="h-2" />
              </div>
              <div className="rounded-md border border-border/60 bg-background/35 p-3">
                <div className="mb-1 text-[11px] uppercase tracking-wider text-muted-foreground">
                  Rationale
                </div>
                <p className="text-sm leading-relaxed">{selected.reason}</p>
              </div>
              <div className="rounded-md border border-border/60 p-3 text-xs text-muted-foreground">
                Feature timestamp: {selected.time} ICT · no look-ahead inputs · cost model attached
                · source hash 18a2…9c4f
              </div>
              <Button
                className="w-full"
                variant={selected.status === "Reviewed" ? "outline" : "default"}
                disabled={selected.status === "Reviewed" || selected.status === "Expired"}
                onClick={() => review(selected.id)}
              >
                {selected.status === "Reviewed" ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
                {selected.status === "Reviewed"
                  ? "Reviewed"
                  : selected.status === "Expired"
                    ? "Signal expired"
                    : "Mark reviewed"}
              </Button>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
