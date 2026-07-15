import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney } from "@/components/metric-card";
import { StatusDot, DemoTag } from "@/components/demo-tag";
import { ACCOUNTS, type PlatformRow } from "@/lib/demo-data";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, RefreshCw, Plug, KeyRound } from "lucide-react";

export const Route = createFileRoute("/accounts")({
  head: () => ({ meta: [{ title: "Accounts & Custody · Aegis Fund OS" }] }),
  component: AccountsPage,
});

function statusTone(s: PlatformRow["status"]) {
  return s === "Healthy" ? "positive" : s === "Degraded" || s === "Stale" ? "warning" : "muted";
}

function AccountsPage() {
  const [q, setQ] = useState("");
  const [envF, setEnvF] = useState<string>("all");
  const [statF, setStatF] = useState<string>("all");
  const [selected, setSelected] = useState<PlatformRow | null>(null);

  const rows = ACCOUNTS.filter((a) => {
    if (envF !== "all" && a.env !== envF) return false;
    if (statF !== "all" && a.status !== statF) return false;
    if (q && !(`${a.platform} ${a.alias}`.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });

  const totalCash = ACCOUNTS.reduce((s, a) => s + a.cash, 0);
  const totalMv = ACCOUNTS.reduce((s, a) => s + a.mv, 0);
  const connected = ACCOUNTS.filter((a) => a.status !== "Disconnected").length;

  return (
    <AppShell>
      <PageHeader
        kicker="Custody & Adapters"
        title="Accounts & Custody"
        subtitle="Paper, testnet, sandbox and manual custodian adapters. Credentials are stored server-side and never exposed to the client."
        actions={
          <>
            <Button variant="outline" size="sm"><RefreshCw className="h-3.5 w-3.5" /> Sync all</Button>
            <Button size="sm"><Plug className="h-3.5 w-3.5" /> Connect adapter</Button>
          </>
        }
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Connected adapters" value={`${connected} / ${ACCOUNTS.length}`} sub="Paper/Testnet/Sandbox/Manual" />
          <MetricCard label="Aggregate cash" value={fmtMoney(totalCash, "USD", 0)} />
          <MetricCard label="Aggregate market value" value={fmtMoney(totalMv, "USD", 0)} />
          <MetricCard label="Freshest sync" value="2s ago" sub="Binance Testnet" />
        </div>

        <Panel title="Account list" subtitle="Institutional table view"
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search account…" className="h-8 w-56 pl-7 text-xs" />
              </div>
              <Select value={envF} onValueChange={setEnvF}>
                <SelectTrigger className="h-8 w-32 text-xs"><SelectValue placeholder="Env" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All envs</SelectItem>
                  {["Paper", "Testnet", "Sandbox", "Manual"].map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={statF} onValueChange={setStatF}>
                <SelectTrigger className="h-8 w-36 text-xs"><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {["Healthy","Degraded","Stale","Disconnected"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Platform</th>
                  <th className="text-left py-2 pr-4 font-medium">Alias</th>
                  <th className="text-left py-2 pr-4 font-medium">Env</th>
                  <th className="text-left py-2 pr-4 font-medium">Base</th>
                  <th className="text-right py-2 pr-4 font-medium">Cash</th>
                  <th className="text-right py-2 pr-4 font-medium">Market value</th>
                  <th className="text-left py-2 pr-4 font-medium">Health</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 font-medium">Last sync</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => {
                  const isDown = a.status === "Disconnected";
                  return (
                  <tr
                    key={a.id}
                    onClick={() => setSelected(a)}
                    className={`border-b border-border/40 hover:bg-accent/30 cursor-pointer ${isDown ? "opacity-60 [&_td]:italic" : ""}`}
                  >
                    <td className="py-2.5 pr-4 font-medium">{a.platform}</td>
                    <td className="py-2.5 pr-4 font-mono text-xs text-muted-foreground">{a.alias}</td>
                    <td className="py-2.5 pr-4"><Badge variant="outline" className="text-[10px] uppercase">{a.env}</Badge></td>
                    <td className="py-2.5 pr-4">{a.base}</td>
                    <td className="py-2.5 pr-4 text-right num">{fmtMoney(a.cash, "USD", 0)}</td>
                    <td className="py-2.5 pr-4 text-right num">{fmtMoney(a.mv, "USD", 0)}</td>
                    <td className="py-2.5 pr-4">
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <StatusDot tone={statusTone(a.status)} /> {a.status}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-muted-foreground">{a.source}</td>
                    <td className="py-2.5 text-xs text-muted-foreground num">{a.lastSync}</td>
                  </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr><td colSpan={9} className="py-8 text-center text-sm text-muted-foreground">No accounts match filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  {selected.platform}
                  <Badge variant="outline" className="text-[10px] uppercase">{selected.env}</Badge>
                  <DemoTag />
                </SheetTitle>
                <SheetDescription className="font-mono text-xs">{selected.alias}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-4 px-4 pb-6">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md border border-border/60 p-2.5">
                    <div className="text-[11px] uppercase text-muted-foreground tracking-wider">Cash</div>
                    <div className="num font-semibold">{fmtMoney(selected.cash)}</div>
                  </div>
                  <div className="rounded-md border border-border/60 p-2.5">
                    <div className="text-[11px] uppercase text-muted-foreground tracking-wider">Market value</div>
                    <div className="num font-semibold">{fmtMoney(selected.mv)}</div>
                  </div>
                </div>

                <div className="rounded-md border border-border/60 p-3 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium"><KeyRound className="h-3.5 w-3.5" /> Credentials</div>
                  <div className="text-xs text-muted-foreground">API keys are stored in a server vault and never exposed to the client or this UI.</div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="rounded bg-background/60 px-2 py-1">API_KEY: <span className="text-muted-foreground">••••••••••••7f2a</span></div>
                    <div className="rounded bg-background/60 px-2 py-1">SECRET: <span className="text-muted-foreground">••••••••••••••••</span></div>
                  </div>
                </div>

                <div className="rounded-md border border-border/60 p-3">
                  <div className="text-sm font-medium mb-2">Ingestion events</div>
                  <ul className="space-y-1.5 text-xs">
                    {["Positions snapshot", "Balances snapshot", "Trades since t-1", "Corporate actions"].map((e, i) => (
                      <li key={i} className="flex items-center justify-between">
                        <span>{e}</span>
                        <span className="text-muted-foreground num">{["2s","2s","12s","6m"][i]} ago</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-md border border-border/60 p-3 text-xs text-muted-foreground">
                  <div className="font-medium text-foreground mb-1">Provenance</div>
                  Data source: <span className="font-mono">{selected.source}</span> · integrity hash <span className="font-mono">9f2a…c14e</span>
                </div>

                <div className="flex gap-2">
                  <Button variant="outline" size="sm"><RefreshCw className="h-3.5 w-3.5" /> Re-sync</Button>
                  <Button variant="outline" size="sm">View ledger entries</Button>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}

