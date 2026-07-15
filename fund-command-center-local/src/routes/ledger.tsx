import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard, fmtMoney, fmtNum } from "@/components/metric-card";
import { LEDGER } from "@/lib/demo-data";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Search, Download, ShieldCheck, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/ledger")({
  head: () => ({ meta: [{ title: "General Ledger · Aegis Fund OS" }] }),
  component: LedgerPage,
});

function LedgerPage() {
  const [q, setQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [accountF, setAccountF] = useState("all");
  const [sel, setSel] = useState<(typeof LEDGER)[number] | null>(null);

  const accountOptions = useMemo(() => Array.from(new Set(LEDGER.map((r) => r.account))), []);

  const rows = useMemo(() => LEDGER.filter((r) => {
    if (q && !`${r.id} ${r.account} ${r.ref} ${r.source}`.toLowerCase().includes(q.toLowerCase())) return false;
    if (accountF !== "all" && r.account !== accountF) return false;
    const dateOnly = r.ts.slice(0, 10);
    if (dateFrom && dateOnly < dateFrom) return false;
    if (dateTo && dateOnly > dateTo) return false;
    return true;
  }), [q, accountF, dateFrom, dateTo]);

  const totals = rows.reduce((s, r) => ({ dr: s.dr + r.dr, cr: s.cr + r.cr }), { dr: 0, cr: 0 });
  // Force a trial-balance warning example when a subset is applied that isn't zero-sum.
  const outOfBalance = Math.abs(totals.dr - totals.cr) > 0.01;

  return (
    <AppShell>
      <PageHeader
        kicker="Double-entry ledger · immutable"
        title="General Ledger"
        subtitle="Every trade, fee, funding event, and revaluation is posted here with cryptographic provenance."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => toast.success("Export queued (demo)")}>
              <Download className="h-3.5 w-3.5" /> Export CSV
            </Button>
            <Button size="sm">Post batch</Button>
          </>
        }
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Debits (period)" value={fmtMoney(totals.dr, "USD", 0)} />
          <MetricCard label="Credits (period)" value={fmtMoney(totals.cr, "USD", 0)} />
          <MetricCard label="Entries" value={`${fmtNum(rows.length)} / ${fmtNum(LEDGER.length)}`} sub="Filtered / total" />
          <MetricCard
            label="Trial balance (filtered)"
            value={outOfBalance ? "Out of balance" : "In balance"}
            tone={outOfBalance ? "negative" : "positive"}
            sub={outOfBalance ? `Δ ${fmtMoney(totals.dr - totals.cr)} (demo)` : "Δ 0.00 (demo)"}
          />
        </div>

        {outOfBalance && (
          <div className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            Filtered subset is out of balance (demo). In production, a full-period trial balance runs after all
            entries are posted; correcting entries would route to suspense account 9999.
          </div>
        )}

        <Panel
          title="Journal"
          subtitle="Immutable double-entry ledger"
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search event / account / ref…" className="h-8 w-56 pl-7 text-xs" />
              </div>
              <Input aria-label="From date" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="h-8 w-36 text-xs" />
              <Input aria-label="To date" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="h-8 w-36 text-xs" />
              <Select value={accountF} onValueChange={setAccountF}>
                <SelectTrigger className="h-8 w-52 text-xs" aria-label="Account filter"><SelectValue placeholder="Account" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All accounts</SelectItem>
                  {accountOptions.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
              {(q || dateFrom || dateTo || accountF !== "all") && (
                <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => { setQ(""); setDateFrom(""); setDateTo(""); setAccountF("all"); }}>Reset</Button>
              )}
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="text-left py-2 pr-4 font-medium">Timestamp</th>
                  <th className="text-left py-2 pr-4 font-medium">Event</th>
                  <th className="text-left py-2 pr-4 font-medium">Account</th>
                  <th className="text-right py-2 pr-4 font-medium">Debit</th>
                  <th className="text-right py-2 pr-4 font-medium">Credit</th>
                  <th className="text-left py-2 pr-4 font-medium">Ccy</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 pr-4 font-medium">Ref</th>
                  <th className="text-left py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => setSel(r)} className="border-b border-border/40 hover:bg-accent/30 cursor-pointer">
                    <td className="py-2 pr-4 text-xs text-muted-foreground num">{r.ts}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{r.id}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{r.account}</td>
                    <td className="py-2 pr-4 text-right num">{r.dr ? fmtMoney(r.dr, "USD", 2) : "—"}</td>
                    <td className="py-2 pr-4 text-right num">{r.cr ? fmtMoney(r.cr, "USD", 2) : "—"}</td>
                    <td className="py-2 pr-4 text-xs">{r.ccy}</td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground">{r.source}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{r.ref}</td>
                    <td className="py-2">
                      <Badge variant={r.status === "Posted" ? "secondary" : "outline"} className="text-[10px]">
                        {r.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={9} className="py-8 text-center text-sm text-muted-foreground">No entries match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {sel && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono">{sel.id}</SheetTitle>
                <SheetDescription>{sel.ts}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 px-4 pb-6 space-y-3 text-sm">
                <div className="rounded-md border border-border/60 p-3 space-y-2">
                  <div className="flex justify-between"><span className="text-muted-foreground">Account</span><span className="font-mono">{sel.account}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Debit</span><span className="num">{fmtMoney(sel.dr)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Credit</span><span className="num">{fmtMoney(sel.cr)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Currency</span><span>{sel.ccy}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Source</span><span>{sel.source}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">External Ref</span><span className="font-mono text-xs">{sel.ref}</span></div>
                </div>
                <div className="rounded-md border border-positive/30 bg-positive/5 p-3 text-xs">
                  <div className="flex items-center gap-2 text-positive font-medium"><ShieldCheck className="h-3.5 w-3.5" /> Immutable</div>
                  <div className="text-muted-foreground mt-1">
                    This entry is append-only. Corrections must be posted as reversing entries. Hash <span className="font-mono">c9f2…14ea</span>.
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">View in audit log</Button>
                  <Button variant="outline" size="sm" disabled>Reverse (requires approver)</Button>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}

