import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, FlaskConical, GitCompareArrows, LockKeyhole, XCircle } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/strategies")({
  head: () => ({ meta: [{ title: "Strategy Lab · Aegis Fund OS" }] }),
  component: StrategyLabPage,
});

const strategies = [
  {
    id: "STR-001",
    name: "Dual Grid 75/25",
    family: "Rule-based grid",
    universe: "BTC, ETH · 4h",
    owner: "Quant Research",
    stage: "Approved research baseline",
    score: -0.0078,
    drawdown: -0.032,
    verdict: "Cash default",
    tone: "warning",
  },
  {
    id: "STR-002",
    name: "Percentile Regime Router",
    family: "Deterministic overlay",
    universe: "BTC, ETH · 4h",
    owner: "Quant Research",
    stage: "Validation passed",
    score: 0.0142,
    drawdown: -0.021,
    verdict: "Paper eligible",
    tone: "positive",
  },
  {
    id: "STR-003",
    name: "Funding Relative Value",
    family: "Market neutral",
    universe: "BTC/ETH perps",
    owner: "Research Queue",
    stage: "Hypothesis",
    score: 0,
    drawdown: 0,
    verdict: "Not tested",
    tone: "info",
  },
  {
    id: "STR-004",
    name: "RL Grid Governor",
    family: "Reinforcement learning",
    universe: "BTC · 4h",
    owner: "Archived",
    stage: "Gate failed",
    score: -0.0197,
    drawdown: -0.067,
    verdict: "Blocked",
    tone: "negative",
  },
] as const;

const gates = [
  { name: "Held-out split", note: "No parameter fitting on evaluation window", pass: true },
  { name: "Minimum 3 seeds", note: "Reproducibility evidence attached", pass: true },
  { name: "Robust score > cash", note: "Return - 2 x max drawdown", pass: false },
  { name: "Cost & funding model", note: "Spread, fees, slippage and funding included", pass: true },
  { name: "Independent promotion vote", note: "Scripted ValidationGate is final", pass: true },
];

function pct(value: number) {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function toneClass(tone: string) {
  if (tone === "positive") return "border-positive/35 text-positive";
  if (tone === "negative") return "border-destructive/35 text-destructive";
  if (tone === "warning") return "border-warning/35 text-warning";
  return "border-info/35 text-info";
}

function StrategyLabPage() {
  const [selectedId, setSelectedId] = useState("STR-001");
  const selected = useMemo(
    () => strategies.find((s) => s.id === selectedId) ?? strategies[0],
    [selectedId],
  );
  const passed = gates.filter((g) => g.pass).length;

  return (
    <AppShell>
      <PageHeader
        kicker="P1 · Research governance"
        title="Strategy Lab"
        subtitle="Compare deterministic candidates, preserve negative results and promote only through scripted validation gates."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => toast("Comparison workspace prepared (demo)")}
            >
              <GitCompareArrows className="h-3.5 w-3.5" /> Compare
            </Button>
            <Button size="sm" onClick={() => toast.success("Research run drafted (demo)")}>
              <FlaskConical className="h-3.5 w-3.5" /> New research run
            </Button>
          </>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Research boundary"
          text="Candidates can be evaluated and marked paper-eligible, but this workspace cannot activate a live strategy."
        />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Candidates" value="4" sub="1 baseline · 1 blocked" />
          <MetricCard label="Paper eligible" value="1" tone="positive" sub="Deterministic only" />
          <MetricCard
            label="Open hypotheses"
            value="1"
            tone="warning"
            sub="Criteria not declared"
          />
          <MetricCard label="Validation policy" value="5 gates" sub="Thresholds locked" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
          <Panel
            title="Strategy registry"
            subtitle="Click a row to inspect evidence and gate status"
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular">
                <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b border-border/60">
                    <th className="py-2 pr-4 text-left font-medium">Strategy</th>
                    <th className="py-2 pr-4 text-left font-medium">Universe</th>
                    <th className="py-2 pr-4 text-left font-medium">Stage</th>
                    <th className="py-2 pr-4 text-right font-medium">Robust score</th>
                    <th className="py-2 text-left font-medium">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((strategy) => (
                    <tr
                      key={strategy.id}
                      onClick={() => setSelectedId(strategy.id)}
                      className={`cursor-pointer border-b border-border/40 hover:bg-accent/30 ${selectedId === strategy.id ? "bg-primary/5" : ""}`}
                    >
                      <td className="py-3 pr-4">
                        <div className="font-medium">{strategy.name}</div>
                        <div className="font-mono text-[10px] text-muted-foreground">
                          {strategy.id} · {strategy.family}
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {strategy.universe}
                      </td>
                      <td className="py-3 pr-4 text-xs">{strategy.stage}</td>
                      <td
                        className={`py-3 pr-4 text-right font-mono ${strategy.score > 0 ? "text-positive" : strategy.score < 0 ? "text-destructive" : "text-muted-foreground"}`}
                      >
                        {strategy.score ? pct(strategy.score) : "—"}
                      </td>
                      <td className="py-3">
                        <Badge variant="outline" className={toneClass(strategy.tone)}>
                          {strategy.verdict}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title={selected.name} subtitle={`${selected.id} · ${selected.owner}`}>
            <Tabs defaultValue="gate">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="gate">Validation gate</TabsTrigger>
                <TabsTrigger value="evidence">Evidence</TabsTrigger>
              </TabsList>
              <TabsContent value="gate" className="mt-4 space-y-4">
                <div>
                  <div className="mb-1.5 flex justify-between text-xs">
                    <span>Gate completion</span>
                    <span className="num">
                      {passed}/{gates.length}
                    </span>
                  </div>
                  <Progress value={(passed / gates.length) * 100} className="h-2" />
                </div>
                <ul className="space-y-2">
                  {gates.map((gate) => (
                    <li
                      key={gate.name}
                      className="flex gap-2 rounded-md border border-border/60 bg-background/35 p-2.5"
                    >
                      {gate.pass ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                      ) : (
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                      )}
                      <div>
                        <div className="text-sm font-medium">{gate.name}</div>
                        <div className="text-[11px] text-muted-foreground">{gate.note}</div>
                      </div>
                    </li>
                  ))}
                </ul>
                <Button className="w-full" disabled>
                  <LockKeyhole className="h-3.5 w-3.5" /> Live promotion unavailable
                </Button>
              </TabsContent>
              <TabsContent value="evidence" className="mt-4 space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-md border border-border/60 p-3">
                    <div className="text-[11px] uppercase text-muted-foreground">Robust score</div>
                    <div className="mt-1 font-mono font-semibold">
                      {selected.score ? pct(selected.score) : "Not run"}
                    </div>
                  </div>
                  <div className="rounded-md border border-border/60 p-3">
                    <div className="text-[11px] uppercase text-muted-foreground">Max drawdown</div>
                    <div className="mt-1 font-mono font-semibold">
                      {selected.drawdown ? pct(selected.drawdown) : "Not run"}
                    </div>
                  </div>
                </div>
                <div className="rounded-md border border-border/60 p-3 text-xs text-muted-foreground">
                  Evidence is demo metadata derived from the local validation log. Synthetic or
                  single-split results never qualify as real-market evidence.
                </div>
              </TabsContent>
            </Tabs>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
