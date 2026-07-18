import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { BotStateBadge, EnvironmentBadge } from "@/components/bots/bot-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getGridBotGovernance } from "@/lib/grid-bot-governance.functions";

export const Route = createFileRoute("/bots_/$botId")({
  head: () => ({ meta: [{ title: "Bot Detail · Aegis Fund OS" }] }),
  loader: async ({ params }) => {
    const snapshot = await getGridBotGovernance();
    return {
      bot: snapshot.bots.find((item) => item.id === params.botId) ?? null,
      events: snapshot.events.filter((event) => event.botId === params.botId),
      auditValid: snapshot.auditValid,
    };
  },
  component: BotDetail,
});

function BotDetail() {
  const { bot, events, auditValid } = Route.useLoaderData();
  if (!bot)
    return (
      <AppShell>
        <div className="p-8">Durable bot not found</div>
      </AppShell>
    );
  return (
    <AppShell>
      <PageHeader
        kicker={`${bot.id} · v${bot.version}`}
        title={bot.name}
        subtitle={`${bot.pair} · durable governance record`}
        actions={
          <Button variant="outline" asChild>
            <Link to="/bots">Back to fleet</Link>
          </Button>
        }
      />
      <div className="space-y-6 p-6">
        <div className="flex flex-wrap gap-2">
          <EnvironmentBadge value={bot.environment} />
          <Badge variant="outline">{bot.state.replaceAll("_", " ")}</Badge>
          <BotStateBadge value={bot.runtimeState} />
          <Badge
            variant="outline"
            className={
              auditValid
                ? "border-positive/35 text-positive"
                : "border-destructive/35 text-destructive"
            }
          >
            Audit {auditValid ? "verified" : "blocked"}
          </Badge>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="Ownership">
            <p className="text-sm">Maker: {bot.makerId}</p>
            <p className="text-sm">Checker: {bot.checkerId ?? "Pending"}</p>
          </Panel>
          <Panel title="Configuration">
            <p className="text-sm">
              Range: {String(bot.configuration.lower ?? "—")} –{" "}
              {String(bot.configuration.upper ?? "—")}
            </p>
            <p className="text-sm">
              Grid: {String(bot.configuration.grids ?? "—")} ·{" "}
              {String(bot.configuration.mode ?? "—")}
            </p>
            <p className="text-sm">
              Investment: {String(bot.configuration.investment ?? "—")} USDT
            </p>
          </Panel>
          <Panel title="Record">
            <p className="text-sm">Created: {new Date(bot.createdAt).toLocaleString()}</p>
            <p className="text-sm">Updated: {new Date(bot.updatedAt).toLocaleString()}</p>
            <p className="text-sm">Events: {events.length}</p>
          </Panel>
        </div>
        <Panel
          title="Execution boundary"
          subtitle="No fixture performance is presented as real data."
        >
          <p className="text-sm text-muted-foreground">
            BINANCE_TESTNET bots can persist exchange-acknowledged LIMIT orders after the explicit
            one-click Testnet policy or an independent approval. Fills, cycles, PnL and automatic
            replenishment remain unavailable until reconciliation is implemented.
          </p>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" asChild>
              <Link to="/bots/$botId/orders" params={{ botId: bot.id }}>
                Orders
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/bots/$botId/profit" params={{ botId: bot.id }}>
                Grid profit
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/bots/$botId/events" params={{ botId: bot.id }}>
                Audit events
              </Link>
            </Button>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
