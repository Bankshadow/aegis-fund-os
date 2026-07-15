import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useEffect } from "react";
import { useServerFn } from "@tanstack/react-start";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney, fmtPct } from "@/components/metric-card";
import { RECON_METRICS, RECON_BREAKS, RECON_STAGES, PERSISTED_EXCEPTIONS } from "@/lib/demo-data";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertTriangle, CheckCircle2, Lock, XCircle, UserCheck } from "lucide-react";
import { toast } from "sonner";
import { getOperationsSnapshot } from "@/lib/operations.functions";

export const Route = createFileRoute("/reconciliation")({
  head: () => ({ meta: [{ title: "Reconciliation · Aegis Fund OS" }] }),
  component: ReconPage,
});

type BaseBreak = (typeof RECON_BREAKS)[number];
type BreakStatus = "Imported" | "Matched" | "Exception" | "Reviewed" | "Locked";
type Break = Omit<BaseBreak, "status"> & { status: BreakStatus; assignee: string; maker: string; reviewer: string | null };

const CURRENT_USER = "Anong K. (COO)";
const OPERATORS = ["Anong K. (COO)", "Somchai P. (PM)", "Preecha S. (Risk)", "Niran C. (Ops)"];

function sevBadge(s: Break["severity"]) {
  const map = {
    High: "border-destructive/50 bg-destructive/10 text-destructive",
    Medium: "border-warning/50 bg-warning/10 text-warning",
    Low: "border-info/50 bg-info/10 text-info",
  };
  return map[s];
}

function ReconPage() {
  const readOperations = useServerFn(getOperationsSnapshot);
  const [operations, setOperations] = useState<Awaited<ReturnType<typeof getOperationsSnapshot>> | null>(null);
  useEffect(() => { void readOperations().then(setOperations).catch(() => setOperations(null)); }, [readOperations]);
  const [breaks, setBreaks] = useState<Break[]>(() =>
    RECON_BREAKS.map((b) => ({ ...b, status: b.status as BreakStatus, assignee: b.owner, maker: CURRENT_USER, reviewer: null }))
  );
  const [selId, setSelId] = useState<string | null>(null);
  const sel = useMemo(() => breaks.find((b) => b.id === selId) ?? null, [breaks, selId]);

  const update = (id: string, patch: Partial<Break>) => setBreaks((bs) => bs.map((b) => (b.id === id ? { ...b, ...patch } : b)));

  const openBreaks = breaks.filter((b) => b.status === "Exception").length;
  const reviewedCount = breaks.filter((b) => b.status === "Reviewed").length;
  const lockedCount = breaks.filter((b) => b.status === "Locked").length;


  return (
    <AppShell>
      <PageHeader
        kicker="Operational workflow"
        title="Reconciliation"
        subtitle="Match ingested platform records against the ledger. All approvals require four-eyes."
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Match rate" value={fmtPct(RECON_METRICS.matchRate, 2)} tone="positive" />
          <MetricCard label="Open exceptions" value={openBreaks} tone={openBreaks > 0 ? "warning" : "positive"} />
          <MetricCard label="Reviewed / Locked" value={`${reviewedCount} / ${lockedCount}`} sub="Awaiting checker → sealed" />
          <MetricCard label="Unresolved value" value={fmtMoney(RECON_METRICS.unresolvedValue, "USD", 0)} />
        </div>

        <Panel title="Persisted exception records" subtitle="Read-only snapshot from the durable exception store">
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Record</th>
                  <th className="text-left py-2 pr-4 font-medium">Asset</th>
                  <th className="text-left py-2 pr-4 font-medium">Reason</th>
                  <th className="text-left py-2 pr-4 font-medium">Owner</th>
                  <th className="text-left py-2 pr-4 font-medium">Status</th>
                  <th className="text-left py-2 font-medium">Checker</th>
                </tr>
              </thead>
              <tbody>
                {(operations?.exceptions.length ? operations.exceptions : PERSISTED_EXCEPTIONS).map((exception) => (
                  <tr key={exception.id} className="border-b border-border/40">
                    <td className="py-2 pr-4 font-mono text-xs">{exception.id}</td>
                    <td className="py-2 pr-4">{exception.asset}</td>
                    <td className="py-2 pr-4 text-xs">{exception.reason}</td>
                    <td className="py-2 pr-4 text-xs">{exception.owner}</td>
                    <td className="py-2 pr-4"><Badge variant="outline" className={exception.status === "Open" ? "text-warning border-warning/40" : "text-positive border-positive/40"}>{exception.status}</Badge></td>
                    <td className="py-2 text-xs text-muted-foreground">{"approvedBy" in exception ? exception.approvedBy : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Board" subtitle="Imported → Matched → Exception → Reviewed → Locked">
          <div className="grid gap-3 md:grid-cols-5">
            {RECON_STAGES.map((stage) => {
              const items = breaks.filter((b) => b.status === stage);
              const auto = { Imported: 214, Matched: 198, Reviewed: 5, Locked: 189 } as Record<string, number>;
              return (
                <div key={stage} className="rounded-md border border-border/60 bg-background/30">
                  <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{stage}</div>
                    <Badge variant="outline" className="text-[10px] num">{(auto[stage] ?? 0) + items.length}</Badge>
                  </div>
                  <div className="p-2 space-y-2 min-h-[140px]">
                    {items.map((b) => (
                      <button
                        key={b.id}
                        onClick={() => setSelId(b.id)}
                        className="w-full text-left rounded-md border border-border/60 bg-card/60 p-2 hover:border-primary/40 hover:bg-card focus:outline-none focus:ring-2 focus:ring-primary/40"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[11px]">{b.id}</span>
                          <span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${sevBadge(b.severity)}`}>{b.severity}</span>
                        </div>
                        <div className="mt-1 text-xs">{b.reason}</div>
                        <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground num">
                          <span>{b.source}</span>
                          <span>Δ {fmtMoney(b.delta, "USD", 2)}</span>
                        </div>
                      </button>
                    ))}
                    {items.length === 0 && <div className="text-[11px] text-muted-foreground py-2 text-center">—</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="Exceptions" subtitle="Source vs ledger deltas">
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Break</th>
                  <th className="text-left py-2 pr-4 font-medium">Severity</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-right py-2 pr-4 font-medium">Source val</th>
                  <th className="text-right py-2 pr-4 font-medium">Ledger val</th>
                  <th className="text-right py-2 pr-4 font-medium">Δ</th>
                  <th className="text-left py-2 pr-4 font-medium">Reason</th>
                  <th className="text-left py-2 pr-4 font-medium">Assignee</th>
                  <th className="text-left py-2 pr-4 font-medium">Age</th>
                  <th className="text-left py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {breaks.map((b) => (
                  <tr key={b.id} onClick={() => setSelId(b.id)} className="border-b border-border/40 hover:bg-accent/30 cursor-pointer">
                    <td className="py-2 pr-4 font-mono text-xs">{b.id}</td>
                    <td className="py-2 pr-4"><span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase ${sevBadge(b.severity)}`}>{b.severity}</span></td>
                    <td className="py-2 pr-4">{b.source}</td>
                    <td className="py-2 pr-4 text-right num">{fmtMoney(b.sourceVal, "USD", 2)}</td>
                    <td className="py-2 pr-4 text-right num">{fmtMoney(b.ledgerVal, "USD", 2)}</td>
                    <td className="py-2 pr-4 text-right num text-warning">{fmtMoney(b.delta, "USD", 2)}</td>
                    <td className="py-2 pr-4 text-xs">{b.reason}</td>
                    <td className="py-2 pr-4 text-xs">{b.assignee}</td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground">{b.age}</td>
                    <td className="py-2"><Badge variant="outline" className="text-[10px]">{b.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Sheet open={!!sel} onOpenChange={(o) => !o && setSelId(null)}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          {sel && (() => {
            const canLock = sel.status === "Reviewed" && !!sel.reviewer && sel.reviewer !== sel.maker;
            const canReview = sel.status === "Exception";
            return (
              <>
                <SheetHeader>
                  <SheetTitle className="flex items-center gap-2">
                    <span className="font-mono">{sel.id}</span>
                    <span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${sevBadge(sel.severity)}`}>{sel.severity}</span>
                    <Badge variant="outline" className="ml-auto text-[10px]">{sel.status}</Badge>
                  </SheetTitle>
                </SheetHeader>
                <div className="mt-4 px-4 pb-6 space-y-4">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-md border border-border/60 p-2.5">
                      <div className="text-[11px] uppercase text-muted-foreground tracking-wider">Source</div>
                      <div className="num font-semibold">{fmtMoney(sel.sourceVal)}</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">{sel.source}</div>
                    </div>
                    <div className="rounded-md border border-border/60 p-2.5">
                      <div className="text-[11px] uppercase text-muted-foreground tracking-wider">Ledger</div>
                      <div className="num font-semibold">{fmtMoney(sel.ledgerVal)}</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">GL entry</div>
                    </div>
                  </div>
                  <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
                    <div className="flex items-center gap-2 text-warning font-medium"><AlertTriangle className="h-3.5 w-3.5" /> Delta {fmtMoney(sel.delta)}</div>
                    <div className="mt-1 text-xs text-muted-foreground">Reason code: <span className="text-foreground">{sel.reason}</span> · Age {sel.age}</div>
                  </div>

                  <div className="rounded-md border border-border/60 p-3">
                    <div className="text-sm font-medium mb-2">Evidence timeline</div>
                    <ol className="space-y-2 text-xs">
                      <li className="flex gap-2"><span className="text-muted-foreground num w-12">08:12</span><span>Imported source record from {sel.source}</span></li>
                      <li className="flex gap-2"><span className="text-muted-foreground num w-12">08:22</span><span>Auto-matched to GL journal — delta flagged</span></li>
                      <li className="flex gap-2"><span className="text-muted-foreground num w-12">09:03</span><span>Assigned to {sel.assignee}</span></li>
                      <li className="flex gap-2"><span className="text-muted-foreground num w-12">09:41</span><span>Note added: awaiting confirmation from custodian</span></li>
                      {sel.status !== "Exception" && (
                        <li className="flex gap-2"><span className="text-positive num w-12">now</span><span>Status → <span className="font-medium">{sel.status}</span> (demo)</span></li>
                      )}
                    </ol>
                  </div>

                  <div>
                    <label className="text-xs font-medium">Reassign to</label>
                    <Select value={sel.assignee} onValueChange={(v) => { update(sel.id, { assignee: v }); toast(`Reassigned to ${v} (demo)`); }}>
                      <SelectTrigger className="h-8 mt-1 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {OPERATORS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-xs font-medium">Add note</label>
                    <Textarea placeholder="Describe root cause or resolution…" className="mt-1 h-20 text-sm" />
                  </div>

                  <div className="rounded-md border border-info/40 bg-info/10 p-3 text-xs space-y-1">
                    <div className="flex items-center gap-2 text-info font-medium"><UserCheck className="h-3.5 w-3.5" /> Four-Eyes control</div>
                    <div className="text-muted-foreground">Maker: <span className="text-foreground">{sel.maker}</span></div>
                    <div className="text-muted-foreground">Checker: <span className="text-foreground">{sel.reviewer ?? "—"}</span></div>
                    {!sel.reviewer && (
                      <div className="pt-1">
                        <Select
                          onValueChange={(v) => {
                            if (v === sel.maker) { toast.error("Maker cannot also be checker"); return; }
                            update(sel.id, { reviewer: v });
                            toast.success(`Checker set: ${v} (demo)`);
                          }}
                        >
                          <SelectTrigger className="h-8 text-xs" aria-label="Assign checker"><SelectValue placeholder="Assign checker (≠ maker)" /></SelectTrigger>
                          <SelectContent>
                            {OPERATORS.filter((o) => o !== sel.maker).map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!canReview}
                      onClick={() => { update(sel.id, { status: "Reviewed" }); toast.success("Marked reviewed (demo)"); }}
                    ><CheckCircle2 className="h-3.5 w-3.5" /> Mark reviewed</Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => { update(sel.id, { status: "Exception", reviewer: null }); toast.error("Rejected — sent back to exception (demo)"); }}
                    ><XCircle className="h-3.5 w-3.5" /> Reject</Button>
                    <Button
                      size="sm"
                      disabled={!canLock}
                      title={!canLock ? "Requires Reviewed status and a checker different from maker" : "Seal this break"}
                      onClick={() => { update(sel.id, { status: "Locked" }); toast.success(`${sel.id} sealed (demo)`); }}
                    ><Lock className="h-3.5 w-3.5" /> {canLock ? "Lock" : "Lock (Four-Eyes required)"}</Button>
                  </div>
                </div>
              </>
            );
          })()}
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}
