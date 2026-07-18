import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { decideGridBotApproval, getGridBotGovernance } from "@/lib/grid-bot-governance.functions";
import { Check, ShieldCheck, X } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/approvals")({
  head: () => ({ meta: [{ title: "Approvals · Aegis Fund OS" }] }),
  loader: async () => {
    try {
      return { ...(await getGridBotGovernance()), storageAvailable: true as const, error: "" };
    } catch (error) {
      return {
        bots: [],
        events: [],
        auditValid: false,
        storageAvailable: false as const,
        error: error instanceof Error ? error.message : "Governance storage unavailable",
      };
    }
  },
  component: ApprovalsPage,
});

function ApprovalsPage() {
  const initial = Route.useLoaderData();
  const [bots, setBots] = useState(initial.bots);
  const [checkerId, setCheckerId] = useState("local-checker@aegis");
  const [reason, setReason] = useState("Independent risk review completed");
  const [working, setWorking] = useState<string | null>(null);
  const pending = bots.filter((bot) => bot.state === "PENDING_APPROVAL");

  const decide = async (botId: string, decision: "APPROVED" | "REJECTED") => {
    setWorking(botId);
    try {
      const updated = await decideGridBotApproval({ data: { botId, checkerId, decision, reason } });
      setBots((items) => items.map((bot) => (bot.id === botId ? updated : bot)));
      toast.success(`${botId} ${decision.toLowerCase()}; audit event appended.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Decision failed closed");
    } finally {
      setWorking(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        kicker="Durable Four-Eyes governance"
        title="Grid bot approvals"
        subtitle="Cloudflare D1 system of record with immutable, hash-linked decisions."
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Approval unlocks Testnet start, not Mainnet"
          text="Approval sends nothing by itself. A separate Start Testnet action may transmit LIMIT orders only to the fixed Binance Spot Testnet endpoint."
        />
        {!initial.storageAvailable && (
          <Panel title="Storage unavailable">
            <p className="text-sm text-destructive">{initial.error}. All mutations are blocked.</p>
          </Panel>
        )}
        <div className="grid gap-3 md:grid-cols-3">
          <Panel title="Pending">
            <div className="text-3xl font-semibold">{pending.length}</div>
          </Panel>
          <Panel title="Audit chain">
            <Badge
              variant="outline"
              className={
                initial.auditValid
                  ? "border-positive/35 text-positive"
                  : "border-destructive/35 text-destructive"
              }
            >
              {initial.auditValid ? "Verified" : "Blocked / unavailable"}
            </Badge>
          </Panel>
          <Panel title="Durable events">
            <div className="text-3xl font-semibold">{initial.events.length}</div>
          </Panel>
        </div>
        <Panel
          title="Independent checker"
          subtitle="Maker identity is recorded on the draft; the same identity cannot decide."
        >
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              aria-label="Checker identity"
              value={checkerId}
              onChange={(e) => setCheckerId(e.target.value)}
            />
            <Input
              aria-label="Decision reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </Panel>
        <div className="space-y-3">
          {pending.length === 0 && (
            <Panel title="Decision queue">
              <p className="text-sm text-muted-foreground">No grid bot is awaiting approval.</p>
            </Panel>
          )}
          {pending.map((bot) => (
            <article key={bot.id} className="rounded-md border border-border/70 bg-card/40 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-warning" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-medium">{bot.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {bot.id} · {bot.environment} · {bot.pair} · Maker: {bot.makerId} · v
                    {bot.version}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={working === bot.id || !initial.storageAvailable}
                  onClick={() => decide(bot.id, "REJECTED")}
                >
                  <X className="h-3.5 w-3.5" /> Reject
                </Button>
                <Button
                  size="sm"
                  disabled={
                    working === bot.id || !initial.storageAvailable || checkerId === bot.makerId
                  }
                  onClick={() => decide(bot.id, "APPROVED")}
                >
                  <Check className="h-3.5 w-3.5" /> Approve
                </Button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
