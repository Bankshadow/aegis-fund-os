import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, LockKeyhole, ShieldCheck, XCircle } from "lucide-react";
import { getLoopLineageSnapshot } from "@/lib/loop-lineage.functions";

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

function decisionTone(decision: string) {
  if (decision === "paper_review") return "border-positive/35 text-positive";
  if (decision === "kill") return "border-destructive/35 text-destructive";
  return "border-warning/35 text-warning";
}

function decisionLabel(decision: string) {
  if (decision === "paper_review") return "Paper review";
  if (decision === "kill") return "Killed";
  if (decision === "revise") return "Revise";
  return "Unresolved";
}

function StrategyLabPage() {
  const readLineage = useServerFn(getLoopLineageSnapshot);
  const [lineage, setLineage] = useState<
    Awaited<ReturnType<typeof getLoopLineageSnapshot>> | null
  >(null);
  const [lineageError, setLineageError] = useState(false);
  useEffect(() => {
    void readLineage()
      .then((snapshot) => {
        setLineage(snapshot);
        setLineageError(false);
      })
      .catch(() => {
        setLineage(null);
        setLineageError(true);
      });
  }, [readLineage]);
  const [selectedId, setSelectedId] = useState("STR-001");
  const selected = useMemo(
    () => strategies.find((s) => s.id === selectedId) ?? strategies[0],
    [selectedId],
  );
  const passed = gates.filter((g) => g.pass).length;
  const persisted = lineage?.source === "verified_loop_lineage";
  const verdicts = lineage?.summary.verdictCounts;

  return (
    <AppShell>
      <PageHeader
        kicker="P1 · Research governance"
        title="Strategy Lab"
        subtitle="Compare deterministic candidates, preserve negative results and promote only through scripted validation gates."
        actions={
          <>
            <Badge variant="outline" className={persisted ? "border-positive/40 text-positive" : "border-warning/40 text-warning"}>
              {persisted ? "Verified lineage" : lineageError ? "Lineage unavailable" : "Demo fallback"}
            </Badge>
            <Badge variant="outline" className="border-info/40 text-info">
              <ShieldCheck className="mr-1 h-3.5 w-3.5" /> Read-only
            </Badge>
          </>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Research boundary"
          text="Candidates can be evaluated and marked paper-eligible, but this workspace cannot activate a live strategy."
        />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="Experiments"
            value={lineage?.summary.experimentCount ?? "—"}
            sub={persisted ? "Verified hash chain" : "Lineage not configured"}
            demo={!persisted}
          />
          <MetricCard
            label="Paper approved"
            value={lineage?.summary.reviewCounts.approved_for_paper ?? "—"}
            tone="positive"
            sub={`${lineage?.summary.reviewCounts.pending ?? 0} pending independent review`}
            demo={!persisted}
          />
          <MetricCard
            label="Killed / revise"
            value={verdicts ? `${verdicts.kill ?? 0} / ${verdicts.revise ?? 0}` : "—"}
            tone="warning"
            sub="Negative evidence retained"
            demo={!persisted}
          />
          <MetricCard
            label="Drift tasks"
            value={lineage?.summary.openDriftTaskCount ?? "—"}
            sub="Research queue only"
            demo={!persisted}
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
          <Panel
            title="Loop experiment lineage"
            subtitle={persisted ? `Verified · generated ${lineage.generatedAt}` : "Configure AEGIS_LOOP_SNAPSHOT_JSON or server path"}
          >
            {lineageError ? (
              <div className="rounded-md border border-destructive/35 bg-destructive/5 p-4 text-sm text-destructive">
                The configured lineage snapshot failed server-side validation. No experiment data was displayed.
              </div>
            ) : lineage?.experiments.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left font-medium">Experiment</th>
                      <th className="py-2 pr-4 text-left font-medium">Datasets</th>
                      <th className="py-2 pr-4 text-right font-medium">Robust score</th>
                      <th className="py-2 text-left font-medium">Verdict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lineage.experiments.map((experiment) => (
                      <tr key={experiment.recordHash} className="border-b border-border/40">
                        <td className="py-3 pr-4">
                          <div className="font-mono text-xs font-semibold">{experiment.experimentId}</div>
                          <div className="max-w-xl text-xs text-muted-foreground">{experiment.hypothesis}</div>
                          <div className="mt-1 text-[10px] text-muted-foreground">Maker: {experiment.maker}</div>
                          <div className="mt-1 font-mono text-[10px] text-muted-foreground">{experiment.recordHash.slice(0, 12)}…</div>
                        </td>
                        <td className="py-3 pr-4 text-xs text-muted-foreground">{experiment.datasets.join(", ")}</td>
                        <td className="py-3 pr-4 text-right font-mono">
                          {experiment.meanRobustScore == null ? "—" : pct(experiment.meanRobustScore)}
                        </td>
                        <td className="py-3">
                          <Badge variant="outline" className={decisionTone(experiment.decision)}>
                            {decisionLabel(experiment.decision)}
                          </Badge>
                          {experiment.reasons[0] && <div className="mt-1 max-w-xs text-[10px] text-muted-foreground">{experiment.reasons[0]}</div>}
                          {experiment.paperReview && (
                            <div className="mt-2 max-w-xs rounded border border-border/50 p-2 text-[10px] text-muted-foreground">
                              <div className="font-medium text-foreground">
                                {experiment.paperReview.decision === "approved_for_paper" ? "Approved for paper" : "Paper review rejected"}
                              </div>
                              <div>Reviewer: {experiment.paperReview.reviewer}</div>
                              <div>{experiment.paperReview.rationale}</div>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-md border border-border/60 bg-background/35 p-4 text-sm text-muted-foreground">
                No persisted Loop experiments are configured. Static strategy metadata below remains demo-only.
              </div>
            )}
          </Panel>

          <Panel title="Drift research queue" subtitle="Alerts cannot change strategy parameters">
            {lineage?.driftTasks.length ? (
              <ul className="space-y-2">
                {lineage.driftTasks.map((task) => (
                  <li key={task.taskId} className="rounded-md border border-border/60 bg-background/35 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{task.strategy}</span>
                      <Badge variant="outline" className="border-warning/35 text-warning">Research only</Badge>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{task.dataset} · {task.observedAt}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {task.signals.map((signal) => <Badge key={signal} variant="secondary" className="text-[10px]">{signal}</Badge>)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded-md border border-border/60 p-4 text-sm text-muted-foreground">No open drift research tasks.</div>
            )}
          </Panel>
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
