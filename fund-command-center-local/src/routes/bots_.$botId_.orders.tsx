import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { cancelTestnetGridOrder, getGridBotGovernance, getGridBotOrders } from "@/lib/grid-bot-governance.functions";

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

// A FILLED or CANCELED order is settled; anything else (NEW, PARTIALLY_FILLED, or a
// RECONCILIATION_REQUIRED row whose exchange twin vanished) is a stuck order the
// operator can close from here instead of a manual script.
const isCancellable = (status: string) => status !== "FILLED" && status !== "CANCELED";

function Orders() {
  const { bot, orders } = Route.useLoaderData();
  const { botId } = Route.useParams();
  const router = useRouter();
  const [working, setWorking] = useState<string | null>(null);
  // Only a Testnet bot has an exchange-backed ledger to cancel against; Demo/Paper
  // rows are local projections with nothing to cancel on an exchange.
  const canCancel = bot?.environment === "BINANCE_TESTNET";

  const cancel = async (clientOrderId: string) => {
    setWorking(clientOrderId);
    try {
      await cancelTestnetGridOrder({ data: { botId, clientOrderId, actorId: "local-operator@aegis" } });
      toast.success(`Order cancelled and ledger reconciled; a durable audit event was appended.`);
      await router.invalidate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Order cancellation failed closed");
    } finally {
      setWorking(null);
    }
  };

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
              <table className="w-full min-w-[820px] text-sm">
                <thead><tr className="text-left text-xs uppercase text-muted-foreground">
                  {["Grid", "Side", "Price", "Quantity", "Status", "Exchange order", "Client order", ""].map((heading) => <th className="p-2" key={heading}>{heading}</th>)}
                </tr></thead>
                <tbody>{orders.map((order) => (
                  <tr className="border-t" key={order.id}>
                    <td className="p-2">{order.gridIndex}</td><td className="p-2">{order.side}</td>
                    <td className="p-2 font-mono">{order.price}</td><td className="p-2 font-mono">{order.quantity}</td>
                    <td className="p-2">{order.status}</td><td className="p-2 font-mono">{order.exchangeOrderId}</td>
                    <td className="p-2 font-mono text-xs">{order.clientOrderId}</td>
                    <td className="p-2 text-right">
                      {canCancel && isCancellable(order.status) && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={working === order.clientOrderId}
                          onClick={() => cancel(order.clientOrderId)}
                        >
                          {working === order.clientOrderId ? "Cancelling..." : "Cancel"}
                        </Button>
                      )}
                    </td>
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
