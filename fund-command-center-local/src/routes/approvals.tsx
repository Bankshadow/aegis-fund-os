import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Check, CheckCheck, Clock3, ShieldCheck, UserRoundCheck, X } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/approvals")({
  head: () => ({ meta: [{ title: "Approvals · Aegis Fund OS" }] }),
  component: ApprovalsPage,
});

type Approval = {
  id: string;
  type: string;
  subject: string;
  maker: string;
  created: string;
  materiality: string;
  status: "Pending" | "Approved" | "Rejected";
  impact: string;
  self: boolean;
};

const initialApprovals: Approval[] = [
  {
    id: "APR-1902",
    type: "NAV close",
    subject: "Lock provisional NAV · 2025-11-14",
    maker: "N. Suriya",
    created: "2h ago",
    materiality: "High",
    status: "Pending",
    impact: "$12.48m NAV becomes official",
    self: false,
  },
  {
    id: "APR-1901",
    type: "Reconciliation",
    subject: "Resolve break REC-0114-03",
    maker: "P. Chai",
    created: "5h ago",
    materiality: "Medium",
    status: "Pending",
    impact: "$18,420 cash variance explained",
    self: false,
  },
  {
    id: "APR-1900",
    type: "Adapter change",
    subject: "Rotate Coinbase sandbox key",
    maker: "Anong K.",
    created: "1d ago",
    materiality: "Low",
    status: "Pending",
    impact: "Read-only connector credential",
    self: true,
  },
  {
    id: "APR-1899",
    type: "Paper bot",
    subject: "Pause BTC Dual Grid",
    maker: "Risk Officer",
    created: "1d ago",
    materiality: "Medium",
    status: "Approved",
    impact: "Paper process only",
    self: false,
  },
];

const approvalPolicies = [
  {
    title: "Separation of duties",
    text: "Maker and checker must be different identities.",
    icon: UserRoundCheck,
  },
  {
    title: "Materiality routing",
    text: "High-impact changes require COO plus Risk.",
    icon: ShieldCheck,
  },
  {
    title: "Evidence retention",
    text: "Decision, reason and before/after state are audit-linked.",
    icon: CheckCheck,
  },
];

function ApprovalsPage() {
  const [approvals, setApprovals] = useState(initialApprovals);
  const pending = useMemo(() => approvals.filter((a) => a.status === "Pending"), [approvals]);

  const decide = (id: string, status: "Approved" | "Rejected") => {
    setApprovals((items) => items.map((a) => (a.id === id ? { ...a, status } : a)));
    toast.success(
      `${id} ${status.toLowerCase()} in local demo. Downstream execution remains disabled.`,
    );
  };

  return (
    <AppShell>
      <PageHeader
        kicker="P3 · Four-Eyes governance"
        title="Approvals"
        subtitle="Maker-checker queue for material operational changes, with self-approval prevention and evidence capture."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => toast("Approval policy exported (demo)")}
          >
            <CheckCheck className="h-3.5 w-3.5" /> Export policy
          </Button>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Approval is not execution"
          text="Decisions update this local governance queue only. They cannot transmit live orders, funds or withdrawals."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="Pending"
            value={String(pending.length)}
            tone="warning"
            sub="1 high materiality"
          />
          <MetricCard label="Within SLA" value="2 / 3" />
          <MetricCard label="Self-approval blocks" value="1" tone="positive" />
          <MetricCard label="Material value" value={fmtMoney(12_498_420, "USD", 0)} />
        </div>
        <Tabs defaultValue="queue" className="space-y-4">
          <TabsList>
            <TabsTrigger value="queue">Decision queue</TabsTrigger>
            <TabsTrigger value="history">Decision history</TabsTrigger>
            <TabsTrigger value="policy">Control policy</TabsTrigger>
          </TabsList>
          <TabsContent value="queue">
            <div className="space-y-3">
              {pending.map((approval) => (
                <article
                  key={approval.id}
                  className="rounded-md border border-border/70 bg-card/40 p-4"
                >
                  <div className="flex flex-wrap items-start gap-3">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-warning/10 text-warning">
                      <Clock3 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-medium">{approval.subject}</h3>
                        <Badge variant="outline">{approval.materiality}</Badge>
                        {approval.self && (
                          <Badge
                            variant="outline"
                            className="border-destructive/35 text-destructive"
                          >
                            Self-approval blocked
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {approval.id} · {approval.type} · Maker: {approval.maker} ·{" "}
                        {approval.created}
                      </div>
                      <div className="mt-2 text-sm">Impact: {approval.impact}</div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => decide(approval.id, "Rejected")}
                      >
                        <X className="h-3.5 w-3.5" /> Reject
                      </Button>
                      <Button
                        size="sm"
                        disabled={approval.self}
                        onClick={() => decide(approval.id, "Approved")}
                      >
                        <Check className="h-3.5 w-3.5" /> Approve
                      </Button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </TabsContent>
          <TabsContent value="history">
            <Panel title="Recent decisions">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left">ID</th>
                      <th className="py-2 pr-4 text-left">Subject</th>
                      <th className="py-2 pr-4 text-left">Maker</th>
                      <th className="py-2 text-left">Decision</th>
                    </tr>
                  </thead>
                  <tbody>
                    {approvals
                      .filter((a) => a.status !== "Pending")
                      .map((a) => (
                        <tr key={a.id} className="border-b border-border/40">
                          <td className="py-3 pr-4 font-mono text-xs">{a.id}</td>
                          <td className="py-3 pr-4">{a.subject}</td>
                          <td className="py-3 pr-4">{a.maker}</td>
                          <td className="py-3">
                            <Badge
                              variant="outline"
                              className={
                                a.status === "Approved"
                                  ? "border-positive/35 text-positive"
                                  : "border-destructive/35 text-destructive"
                              }
                            >
                              {a.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="policy">
            <div className="grid gap-4 lg:grid-cols-3">
              {approvalPolicies.map((policy) => (
                <Panel key={policy.title}>
                  <div className="flex gap-3">
                    <policy.icon className="h-5 w-5 shrink-0 text-primary" />
                    <div>
                      <div className="font-medium">{policy.title}</div>
                      <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {policy.text}
                      </div>
                    </div>
                  </div>
                </Panel>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
