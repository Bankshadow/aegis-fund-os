import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CalendarClock,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/access")({
  head: () => ({ meta: [{ title: "Access & Roles · Aegis Fund OS" }] }),
  component: AccessPage,
});

const users = [
  {
    initials: "AN",
    name: "Anong K.",
    email: "anong@aegis.demo",
    role: "COO / Operations",
    mfa: true,
    status: "Active",
    seen: "Now",
    expiresAt: null,
  },
  {
    initials: "NS",
    name: "N. Suriya",
    email: "suriya@aegis.demo",
    role: "Fund Accountant",
    mfa: true,
    status: "Active",
    seen: "12m ago",
    expiresAt: null,
  },
  {
    initials: "RC",
    name: "R. Chen",
    email: "rchen@aegis.demo",
    role: "Risk Officer",
    mfa: true,
    status: "Active",
    seen: "1h ago",
    expiresAt: null,
  },
  {
    initials: "PT",
    name: "P. Tan",
    email: "ptan@auditor.demo",
    role: "External Auditor",
    mfa: true,
    status: "Time-bound",
    seen: "2d ago",
    expiresAt: "2025-11-21 17:00 UTC",
  },
  {
    initials: "DV",
    name: "Demo Viewer",
    email: "viewer@aegis.demo",
    role: "Read-only Viewer",
    mfa: false,
    status: "Suspended",
    seen: "18d ago",
    expiresAt: null,
  },
];

const roles = [
  {
    role: "COO / Operations",
    members: 1,
    research: "Review",
    paper: "Approve",
    nav: "Approve",
    users: "Manage",
    audit: "Read",
  },
  {
    role: "Fund Accountant",
    members: 2,
    research: "Read",
    paper: "Read",
    nav: "Prepare",
    users: "None",
    audit: "Read",
  },
  {
    role: "Risk Officer",
    members: 1,
    research: "Approve",
    paper: "Stop",
    nav: "Review",
    users: "None",
    audit: "Read",
  },
  {
    role: "Quant Research",
    members: 3,
    research: "Edit",
    paper: "Draft",
    nav: "None",
    users: "None",
    audit: "Own",
  },
  {
    role: "External Auditor",
    members: 1,
    research: "Read",
    paper: "Read",
    nav: "Read",
    users: "None",
    audit: "Export",
  },
];

function AccessPage() {
  const [enforceMfa, setEnforceMfa] = useState(true);
  const [sessionHours, setSessionHours] = useState(8);
  const [renewedUsers, setRenewedUsers] = useState<string[]>([]);

  const renewTimeBoundAccess = (email: string) => {
    setRenewedUsers((current) => [...new Set([...current, email])]);
    toast.success("30-day renewal drafted for maker/checker review (demo)");
  };

  return (
    <AppShell>
      <PageHeader
        kicker="P3 · Identity governance"
        title="Access & Roles"
        subtitle="Role-based access, MFA posture, session policy and segregation of duties for the operating team."
        actions={
          <Button size="sm" onClick={() => toast.success("Invitation drafted (demo)")}>
            <UserPlus className="h-3.5 w-3.5" /> Invite user
          </Button>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="No role can enable live trading"
          text="Permissions govern this operations prototype only. Live order and withdrawal capabilities do not exist in the application."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Active users" value="4" sub="1 time-bound auditor" />
          <MetricCard label="MFA coverage" value="100%" tone="positive" sub="Active accounts" />
          <MetricCard label="Privileged roles" value="2" />
          <MetricCard label="Policy findings" value="0" tone="positive" />
        </div>
        <Tabs defaultValue="users" className="space-y-4">
          <TabsList>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="roles">Role matrix</TabsTrigger>
            <TabsTrigger value="security">Security policy</TabsTrigger>
          </TabsList>
          <TabsContent value="users">
            <Panel title="Directory" subtitle="Demo identities · status and authentication posture">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left">User</th>
                      <th className="py-2 pr-4 text-left">Role</th>
                      <th className="py-2 pr-4 text-left">MFA</th>
                      <th className="py-2 pr-4 text-left">Status</th>
                      <th className="py-2 pr-4 text-left">Expiry / renewal</th>
                      <th className="py-2 text-left">Last active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.email} className="border-b border-border/40">
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2.5">
                            <div className="grid h-8 w-8 place-items-center rounded-full bg-accent text-[10px] font-semibold">
                              {user.initials}
                            </div>
                            <div>
                              <div className="font-medium">{user.name}</div>
                              <div className="text-[11px] text-muted-foreground">{user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 pr-4">{user.role}</td>
                        <td className="py-3 pr-4">
                          {user.mfa ? (
                            <Badge variant="outline" className="border-positive/35 text-positive">
                              Enforced
                            </Badge>
                          ) : (
                            <Badge variant="outline">N/A</Badge>
                          )}
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline">{user.status}</Badge>
                        </td>
                        <td className="py-3 pr-4">
                          {user.expiresAt ? (
                            <div className="flex min-w-[190px] items-center gap-2">
                              <CalendarClock className="h-3.5 w-3.5 shrink-0 text-warning" />
                              <div className="text-xs">
                                <div className="font-medium">Ends {user.expiresAt}</div>
                                <div className="text-muted-foreground">
                                  {renewedUsers.includes(user.email)
                                    ? "Renewal drafted"
                                    : "Sponsor renewal required"}
                                </div>
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={renewedUsers.includes(user.email)}
                                onClick={() => renewTimeBoundAccess(user.email)}
                              >
                                Renew 30d
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">No expiry</span>
                          )}
                        </td>
                        <td className="py-3 text-xs text-muted-foreground">{user.seen}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="roles">
            <Panel title="Role permission matrix" subtitle="Least privilege · deny by default">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr className="border-b border-border/60">
                      <th className="py-2 pr-4 text-left">Role</th>
                      <th className="py-2 pr-4 text-right">Members</th>
                      <th className="py-2 pr-4 text-left">Research</th>
                      <th className="py-2 pr-4 text-left">Paper bots</th>
                      <th className="py-2 pr-4 text-left">NAV</th>
                      <th className="py-2 pr-4 text-left">Users</th>
                      <th className="py-2 text-left">Audit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map((role) => (
                      <tr key={role.role} className="border-b border-border/40">
                        <td className="py-3 pr-4 font-medium">{role.role}</td>
                        <td className="py-3 pr-4 text-right font-mono">{role.members}</td>
                        {[role.research, role.paper, role.nav, role.users, role.audit].map(
                          (value, index) => (
                            <td
                              key={`${role.role}-${index}`}
                              className={`py-3 pr-4 text-xs ${value === "None" ? "text-muted-foreground" : ""}`}
                            >
                              {value}
                            </td>
                          ),
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </TabsContent>
          <TabsContent value="security">
            <div className="grid gap-6 lg:grid-cols-2">
              <Panel title="Authentication policy">
                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded-md border border-border/60 p-3">
                    <div className="flex gap-2">
                      <ShieldCheck className="mt-0.5 h-4 w-4 text-positive" />
                      <div>
                        <div className="text-sm font-medium">Require MFA</div>
                        <div className="text-xs text-muted-foreground">
                          All active human accounts
                        </div>
                      </div>
                    </div>
                    <Switch
                      checked={enforceMfa}
                      onCheckedChange={(value) => {
                        setEnforceMfa(value);
                        toast("Security policy changed in local demo");
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-md border border-border/60 p-3">
                    <div className="flex gap-2">
                      <KeyRound className="mt-0.5 h-4 w-4 text-primary" />
                      <div>
                        <div className="text-sm font-medium">Session lifetime</div>
                        <div className="text-xs text-muted-foreground">
                          Re-authenticate privileged actions
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSessionHours(sessionHours === 8 ? 4 : 8);
                        toast("Session policy updated in local demo");
                      }}
                    >
                      {sessionHours} hours
                    </Button>
                  </div>
                </div>
              </Panel>
              <Panel title="Segregation of duties">
                <div className="space-y-3 text-sm text-muted-foreground">
                  <div className="flex gap-2">
                    <UsersRound className="mt-0.5 h-4 w-4 text-primary" />
                    <p>
                      Maker and checker identities must differ for NAV locks, break resolution and
                      material configuration changes.
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <LockKeyhole className="mt-0.5 h-4 w-4 text-warning" />
                    <p>
                      Quant Research can draft paper bots but cannot approve activation or edit fund
                      accounting records.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => toast.success("SoD scan complete: no conflicts (demo)")}
                  >
                    Run conflict scan
                  </Button>
                </div>
              </Panel>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
