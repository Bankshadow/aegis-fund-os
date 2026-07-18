import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getGridBotGovernance, getGridBotOrders } from "@/lib/grid-bot-governance.functions";

export const Route = createFileRoute("/bots_/$botId_/orders")({
  head: () => ({ meta: [{ title: "Active Orders · Aegis Fund OS" }] }),
  loader: async ({ params }) => {
    const [governance, orders] = await Promise.all([
      getGridBotGovernance(),
      getGridBotOrders({ data: { botId: params.botId } }),
    ]);
    return { bot: governance.bots.find((item) => item.id === params.botId) ?? null, orders };
  },
  component: Orders,
});
function Orders() {
  const { bot, orders } = Route.useLoaderData();
  const { botId } = Route.useParams();
  return (
    <AppShell>
      <PageHeader
        kicker={botId}
        title="Active Orders"
        subtitle={bot ? `${bot.name} · ${bot.environment}` : "Bot not found"}
        actions={
          <Button variant="outline" asChild>
            <Link to="/bots/$botId" params={{ botId }}>
              Bot detail
            </Link>
          </Button>
        }
      />
      <div className="p-6">
        <Panel title="Durable Testnet orders" subtitle="Only exchange-acknowledged orders persisted in D1 are shown.">
          {orders.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No Binance Spot Testnet orders exist for this bot.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead><tr className="text-left text-xs uppercase text-muted-foreground">
                  {["Grid", "Side", "Price", "Quantity", "Status", "Exchange order", "Client order"].map((heading) => <th className="p-2" key={heading}>{heading}</th>)}
                </tr></thead>
                <tbody>{orders.map((order) => (
                  <tr className="border-t" key={order.id}>
                    <td className="p-2">{order.gridIndex}</td><td className="p-2">{order.side}</td>
                    <td className="p-2 font-mono">{order.price}</td><td className="p-2 font-mono">{order.quantity}</td>
                    <td className="p-2">{order.status}</td><td className="p-2 font-mono">{order.exchangeOrderId}</td>
                    <td className="p-2 font-mono text-xs">{order.clientOrderId}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
