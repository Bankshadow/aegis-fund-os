import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { getGridBotGovernance } from "@/lib/grid-bot-governance.functions";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ShieldCheck, ShieldAlert, Search, LinkIcon } from "lucide-react";

type GovernanceEventRow = Awaited<
  ReturnType<typeof getGridBotGovernance>
>["events"][number];

const shortHash = (hash: string) =>
  hash === "GENESIS" ? "GENESIS" : `${hash.slice(0, 10)}…${hash.slice(-6)}`;

const shortId = (id: string) => (id.length > 16 ? `${id.slice(0, 12)}…` : id);

export const Route = createFileRoute("/audit")({
  head: () => ({ meta: [{ title: "Audit Log · Aegis Fund OS" }] }),
  loader: async () => {
    try {
      const snapshot = await getGridBotGovernance();
      // Newest first — repository returns events in append (sequence) order.
      return {
        available: true,
        events: [...snapshot.events].reverse(),
        auditValid: snapshot.auditValid,
      };
    } catch {
      return { available: false, events: [] as GovernanceEventRow[], auditValid: false };
    }
  },
  component: AuditPage,
});

function AuditPage() {
  const { available, events, auditValid } = Route.useLoaderData();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<GovernanceEventRow | null>(null);

  const rows = useMemo(
    () =>
      events.filter(
        (e) =>
          !q ||
          `${e.eventId} ${e.actorId} ${e.eventType} ${e.botId} ${e.eventHash}`
            .toLowerCase()
            .includes(q.toLowerCase()),
      ),
    [q, events],
  );

  const actorCount = useMemo(() => new Set(events.map((e) => e.actorId)).size, [events]);
  const chainCount = useMemo(() => new Set(events.map((e) => e.botId)).size, [events]);
  const integrityTone = !available ? "warning" : auditValid ? "positive" : "negative";
  const integrityLabel = !available ? "Unavailable" : auditValid ? "Verified" : "INVALID";

  return (
    <AppShell>
      <PageHeader
        kicker="Immutable · Append-only · SHA-256 chain"
        title="Audit Log"
        subtitle="Durable governance events across every grid bot, with actor, payload, and per-bot hash linkage."
        actions={
          available && auditValid ? (
            <div className="flex items-center gap-2 rounded-md border border-positive/40 bg-positive/5 px-2 py-1 text-xs text-positive">
              <ShieldCheck className="h-3.5 w-3.5" /> Chain integrity: verified
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-2 py-1 text-xs text-destructive">
              <ShieldAlert className="h-3.5 w-3.5" />
              {available ? "Chain integrity: FAILED" : "Governance storage unavailable"}
            </div>
          )
        }
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Events" value={String(events.length)} demo={false} sub="Durable D1 records" />
          <MetricCard label="Actors" value={String(actorCount)} demo={false} sub="Distinct actor identities" />
          <MetricCard label="Bot chains" value={String(chainCount)} demo={false} sub="Independent hash chains" />
          <MetricCard
            label="Integrity"
            value={integrityLabel}
            tone={integrityTone}
            demo={false}
            sub={available ? "Recomputed on load" : "No storage bound"}
          />
        </div>

        {!available ? (
          <Panel title="Events" subtitle="Actor · Action · Entity · Hash">
            <p className="py-10 text-center text-sm text-muted-foreground">
              Governance storage is not bound to this environment, so no audit events can be shown.
              Nothing here is simulated.
            </p>
          </Panel>
        ) : (
          <>
            <Panel
              title="Events"
              subtitle="Actor · Event · Bot · Hash"
              actions={
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Filter events…"
                    className="h-8 w-64 pl-7 text-xs"
                  />
                </div>
              }
            >
              {events.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  No durable governance events exist yet.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm tabular">
                    <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      <tr className="border-b border-border/60">
                        <th className="text-left py-2 pr-4 font-medium">Event</th>
                        <th className="text-left py-2 pr-4 font-medium">Timestamp</th>
                        <th className="text-left py-2 pr-4 font-medium">Actor</th>
                        <th className="text-left py-2 pr-4 font-medium">Type</th>
                        <th className="text-left py-2 pr-4 font-medium">Bot</th>
                        <th className="text-left py-2 font-medium">Hash</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr
                          key={r.eventId}
                          onClick={() => setSel(r)}
                          className="border-b border-border/40 hover:bg-accent/30 cursor-pointer"
                        >
                          <td className="py-2 pr-4 font-mono text-xs">{shortId(r.eventId)}</td>
                          <td className="py-2 pr-4 text-xs text-muted-foreground num">
                            {new Date(r.occurredAt).toLocaleString()}
                          </td>
                          <td className="py-2 pr-4">{r.actorId}</td>
                          <td className="py-2 pr-4 font-mono text-xs">{r.eventType}</td>
                          <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                            {shortId(r.botId)}
                          </td>
                          <td className="py-2 font-mono text-xs">{shortHash(r.eventHash)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>

            {events.length > 0 && (
              <Panel title="Evidence chain" subtitle="Latest blocks (newest first)">
                <div className="overflow-x-auto">
                  <div className="flex items-center gap-2 py-2 min-w-max">
                    {events.slice(0, 6).map((e, i) => (
                      <div key={e.eventId} className="flex items-center gap-2">
                        <div className="rounded-md border border-border/70 bg-background/60 px-3 py-2 min-w-[170px]">
                          <div className="font-mono text-[10px] text-muted-foreground">
                            {shortId(e.eventId)}
                          </div>
                          <div className="text-xs mt-0.5 truncate">{e.eventType}</div>
                          <div className="font-mono text-[10px] text-muted-foreground mt-1">
                            {shortHash(e.eventHash)}
                          </div>
                        </div>
                        {i < Math.min(events.length, 6) - 1 && (
                          <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>
            )}
          </>
        )}
      </div>

      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {sel && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono">{sel.eventType}</SheetTitle>
              </SheetHeader>
              <div className="mt-4 px-4 pb-6 space-y-3 text-sm">
                <div className="rounded-md border border-border/60 p-3 space-y-1.5">
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Event</span>
                    <span className="font-mono text-xs break-all text-right">{sel.eventId}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Timestamp</span>
                    <span className="num">{new Date(sel.occurredAt).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Actor</span>
                    <span>{sel.actorId}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Bot</span>
                    <span className="font-mono text-xs break-all text-right">{sel.botId}</span>
                  </div>
                </div>
                <div className="rounded-md border border-border/60 p-3">
                  <div className="text-xs font-medium mb-1">Payload</div>
                  <pre className="rounded bg-background/60 p-2 text-[11px] font-mono overflow-x-auto">
{JSON.stringify(sel.payload, null, 2)}
                  </pre>
                </div>
                <div className="rounded-md border border-border/60 p-3 space-y-1.5">
                  <div className="text-xs font-medium mb-1">Hash linkage</div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Previous</span>
                    <span className="font-mono text-[11px] break-all text-right">
                      {sel.previousHash}
                    </span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">This event</span>
                    <span className="font-mono text-[11px] break-all text-right">
                      {sel.eventHash}
                    </span>
                  </div>
                </div>
                <div
                  className={
                    auditValid
                      ? "rounded-md border border-positive/30 bg-positive/5 p-3 text-xs text-positive flex items-center gap-2"
                      : "rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive flex items-center gap-2"
                  }
                >
                  {auditValid ? (
                    <ShieldCheck className="h-3.5 w-3.5" />
                  ) : (
                    <ShieldAlert className="h-3.5 w-3.5" />
                  )}
                  {auditValid
                    ? "This bot's SHA-256 chain recomputed cleanly on load."
                    : "Chain verification failed — records may have been tampered."}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}
