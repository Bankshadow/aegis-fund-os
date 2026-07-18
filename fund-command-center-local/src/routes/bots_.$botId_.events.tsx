import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getGridBotGovernance } from "@/lib/grid-bot-governance.functions";

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
function Events() {
  const { botId } = Route.useParams();
  const { events, auditValid } = Route.useLoaderData();
  return (
    <AppShell>
      <PageHeader
        kicker={botId}
        title="Bot Audit Events"
        subtitle={`Hash chain ${auditValid ? "verified" : "invalid"}`}
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
              <div
                className="grid gap-1 border-b p-3 text-sm md:grid-cols-[70px_1fr_1fr_190px]"
                key={event.eventId}
              >
                <span className="font-mono">#{index + 1}</span>
                <span>{event.eventType}</span>
                <span>{event.actorId}</span>
                <span className="text-muted-foreground">
                  {new Date(event.occurredAt).toLocaleString()}
                </span>
              </div>
            ))
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
