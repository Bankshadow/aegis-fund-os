import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { getGridBotGovernance } from "@/lib/grid-bot-governance.functions";

const shortHash = (hash: string) =>
  hash === "GENESIS" ? "GENESIS" : `${hash.slice(0, 10)}…${hash.slice(-6)}`;

export const Route = createFileRoute("/bots_/$botId_/events")({
  head: () => ({ meta: [{ title: "Bot Audit Events · Aegis Fund OS" }] }),
  loader: async ({ params }) => {
    const snapshot = await getGridBotGovernance();
    return {
      events: snapshot.events.filter((event) => event.botId === params.botId),
      auditValid: snapshot.auditValid,
    };
  },
  component: Events,
});

type EventRow = Awaited<ReturnType<typeof getGridBotGovernance>>["events"][number];

function Events() {
  const { botId } = Route.useParams();
  const { events, auditValid } = Route.useLoaderData();
  const [sel, setSel] = useState<EventRow | null>(null);
  return (
    <AppShell>
      <PageHeader
        kicker={botId}
        title="Bot Audit Events"
        subtitle={`Hash chain ${auditValid ? "verified" : "invalid"} · select an event for payload and linkage`}
        actions={
          <Button variant="outline" asChild>
            <Link to="/bots/$botId" params={{ botId }}>
              Bot detail
            </Link>
          </Button>
        }
      />
      <div className="p-6">
        <Panel title="Immutable events">
          {events.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No durable events found.
            </p>
          ) : (
            events.map((event, index) => (
              <button
                type="button"
                onClick={() => setSel(event)}
                className="grid w-full gap-1 border-b p-3 text-left text-sm hover:bg-muted/40 md:grid-cols-[70px_1fr_1fr_170px_190px]"
                key={event.eventId}
              >
                <span className="font-mono">#{index + 1}</span>
                <span>{event.eventType}</span>
                <span>{event.actorId}</span>
                <span className="font-mono text-xs text-muted-foreground">{shortHash(event.eventHash)}</span>
                <span className="text-muted-foreground">
                  {new Date(event.occurredAt).toLocaleString()}
                </span>
              </button>
            ))
          )}
        </Panel>
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
                    <span className="font-mono text-[11px] break-all text-right">{sel.previousHash}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">This event</span>
                    <span className="font-mono text-[11px] break-all text-right">{sel.eventHash}</span>
                  </div>
                </div>
                <div
                  className={
                    auditValid
                      ? "rounded-md border border-positive/30 bg-positive/5 p-3 text-xs text-positive flex items-center gap-2"
                      : "rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive flex items-center gap-2"
                  }
                >
                  {auditValid ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
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
