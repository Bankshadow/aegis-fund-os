import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FUND } from "@/lib/demo-data";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings · Aegis Fund OS" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const [name, setName] = useState(FUND.name);
  const [ccy, setCcy] = useState(FUND.baseCurrency);
  const [tz, setTz] = useState(FUND.timezone);
  const [dirty, setDirty] = useState(false);

  const track =
    <T,>(setter: (v: T) => void) =>
    (v: T) => {
      setter(v);
      setDirty(true);
    };

  const save = () => {
    setDirty(false);
    toast.success("Settings saved (demo)");
  };

  return (
    <AppShell>
      <PageHeader
        kicker="Configuration"
        title="Settings"
        subtitle="Fund profile, valuation and global risk limits. Platform connections and access policy live in their dedicated workspaces."
        actions={
          <>
            {dirty && (
              <div className="flex items-center gap-1.5 text-[11px] text-warning">
                <AlertCircle className="h-3.5 w-3.5" /> Unsaved changes
              </div>
            )}
            <Button variant="outline" size="sm" disabled={!dirty} onClick={() => setDirty(false)}>
              Discard
            </Button>
            <Button size="sm" disabled={!dirty} onClick={save}>
              Save
            </Button>
          </>
        }
      />
      <div className="p-6">
        <Tabs defaultValue="profile" className="space-y-4">
          <TabsList>
            <TabsTrigger value="profile">Fund profile</TabsTrigger>
            <TabsTrigger value="risk">Risk limits</TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="space-y-4">
            <Panel title="Identity">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Fund name">
                  <Input value={name} onChange={(e) => track<string>(setName)(e.target.value)} />
                </Field>
                <Field label="Code">
                  <Input defaultValue={FUND.code} onChange={() => setDirty(true)} />
                </Field>
                <Field label="Base currency">
                  <Select value={ccy} onValueChange={track<string>(setCcy)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["USD", "EUR", "GBP", "JPY", "THB", "SGD"].map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Valuation timezone">
                  <Select value={tz} onValueChange={track<string>(setTz)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[
                        "Asia/Bangkok",
                        "Asia/Singapore",
                        "Europe/London",
                        "America/New_York",
                        "UTC",
                      ].map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Inception date">
                  <Input defaultValue={FUND.inceptionDate} onChange={() => setDirty(true)} />
                </Field>
                <Field label="Reporting calendar">
                  <Select defaultValue="Monthly" onValueChange={() => setDirty(true)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["Daily", "Weekly", "Monthly", "Quarterly"].map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
            </Panel>

            <Panel title="Service providers">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Administrator">
                  <Input defaultValue={FUND.administrator} onChange={() => setDirty(true)} />
                </Field>
                <Field label="Auditor">
                  <Input defaultValue={FUND.auditor} onChange={() => setDirty(true)} />
                </Field>
              </div>
            </Panel>
          </TabsContent>

          <TabsContent value="risk" className="space-y-4">
            <Panel
              title="Global risk limits"
              subtitle="Applied fund-wide; strategy overrides allowed"
            >
              <div className="grid gap-3 md:grid-cols-2">
                {[
                  ["Gross exposure (soft)", "100"],
                  ["Gross exposure (hard)", "125"],
                  ["Net exposure (soft)", "60"],
                  ["Net exposure (hard)", "80"],
                  ["Single-name concentration (soft)", "8"],
                  ["Single-name concentration (hard)", "12"],
                  ["Max drawdown (soft)", "-10"],
                  ["Max drawdown (hard)", "-15"],
                ].map(([l, v]) => (
                  <Field key={l} label={l as string} suffix="%">
                    <Input
                      defaultValue={v as string}
                      onChange={() => setDirty(true)}
                      className="num"
                    />
                  </Field>
                ))}
              </div>
            </Panel>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}

function Field({
  label,
  children,
  suffix,
}: {
  label: string;
  children: React.ReactNode;
  suffix?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="relative">
        {children}
        {suffix && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}
