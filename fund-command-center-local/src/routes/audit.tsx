import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { AUDIT_EVENTS } from "@/lib/demo-data";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ShieldCheck, Search, LinkIcon } from "lucide-react";

export const Route = createFileRoute("/audit")({
  head: () => ({ meta: [{ title: "Audit Log · Aegis Fund OS" }] }),
  component: AuditPage,
});

function AuditPage() {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<(typeof AUDIT_EVENTS)[number] | null>(null);
  const rows = useMemo(() => AUDIT_EVENTS.filter((e) =>
    !q || `${e.id} ${e.actor} ${e.action} ${e.entity}`.toLowerCase().includes(q.toLowerCase())
  ), [q]);

  return (
    <AppShell>
      <PageHeader
        kicker="Immutable · Append-only"
        title="Audit Log"
        subtitle="Every state-changing action is captured with actor, entity, before/after, and a hash chain."
        actions={
          <div className="flex items-center gap-2 rounded-md border border-positive/40 bg-positive/5 px-2 py-1 text-xs text-positive">
            <ShieldCheck className="h-3.5 w-3.5" /> Chain integrity: verified
          </div>
        }
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Events (30d)" value="12,442" />
          <MetricCard label="Actors" value="17" sub="incl. system & auditor" />
          <MetricCard label="Chain height" value="AUD-050,021" sub="Latest hash 9f2a…c14e" />
          <MetricCard label="Integrity" value="Verified" tone="positive" sub="Last check 2m ago" />
        </div>

        <Panel
          title="Events"
          subtitle="Actor · Action · Entity · Hash"
          actions={
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter events…" className="h-8 w-64 pl-7 text-xs" />
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Event</th>
                  <th className="text-left py-2 pr-4 font-medium">Timestamp</th>
                  <th className="text-left py-2 pr-4 font-medium">Actor</th>
                  <th className="text-left py-2 pr-4 font-medium">Action</th>
                  <th className="text-left py-2 pr-4 font-medium">Entity</th>
                  <th className="text-left py-2 pr-4 font-medium">IP</th>
                  <th className="text-left py-2 font-medium">Hash</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => setSel(r)} className="border-b border-border/40 hover:bg-accent/30 cursor-pointer">
                    <td className="py-2 pr-4 font-mono text-xs">{r.id}</td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground num">{r.ts}</td>
                    <td className="py-2 pr-4">{r.actor}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{r.action}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{r.entity}</td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground num">{r.ip}</td>
                    <td className="py-2 font-mono text-xs">{r.hash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Evidence chain" subtitle="Latest 6 blocks">
          <div className="overflow-x-auto">
            <div className="flex items-center gap-2 py-2 min-w-max">
              {AUDIT_EVENTS.slice(0, 6).map((e, i) => (
                <div key={e.id} className="flex items-center gap-2">
                  <div className="rounded-md border border-border/70 bg-background/60 px-3 py-2 min-w-[160px]">
                    <div className="font-mono text-[10px] text-muted-foreground">{e.id}</div>
                    <div className="text-xs mt-0.5 truncate">{e.action}</div>
                    <div className="font-mono text-[10px] text-muted-foreground mt-1">{e.hash}</div>
                  </div>
                  {i < 5 && <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {sel && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono">{sel.id}</SheetTitle>
              </SheetHeader>
              <div className="mt-4 px-4 pb-6 space-y-3 text-sm">
                <div className="rounded-md border border-border/60 p-3 space-y-1.5">
                  <div className="flex justify-between"><span className="text-muted-foreground">Timestamp</span><span className="num">{sel.ts}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Actor</span><span>{sel.actor}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Action</span><span className="font-mono text-xs">{sel.action}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Entity</span><span className="font-mono text-xs">{sel.entity}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">IP</span><span className="num">{sel.ip}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Session</span><span className="font-mono text-xs">sess_a92f…41</span></div>
                </div>
                <div className="rounded-md border border-border/60 p-3">
                  <div className="text-xs font-medium mb-1">Before → After</div>
                  <pre className="rounded bg-background/60 p-2 text-[11px] font-mono overflow-x-auto">
{`- status: "Provisional"
+ status: "Locked"
+ locked_by: "${sel.actor}"
+ locked_at: "${sel.ts}"`}</pre>
                </div>
                <div className="rounded-md border border-positive/30 bg-positive/5 p-3 text-xs text-positive flex items-center gap-2">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Hash {sel.hash} · linked to previous block
                </div>
                <Button variant="outline" size="sm">Verify chain from this block</Button>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}

