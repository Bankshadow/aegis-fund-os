import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { SafetyBanner } from "@/components/safety-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { testBinanceTestnetConnection } from "@/lib/binance-testnet.functions";
import { testBybitTestnetConnection } from "@/lib/bybit-testnet.functions";
import { testHyperliquidConnection } from "@/lib/hyperliquid.functions";
import {
  CheckCircle2,
  KeyRound,
  PlugZap,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/integrations")({
  head: () => ({ meta: [{ title: "Integrations · Aegis Fund OS" }] }),
  component: IntegrationsPage,
});

type Adapter = {
  id: string;
  name: string;
  kind: string;
  environment: string;
  status: "Healthy" | "Degraded" | "Disconnected" | "Not tested" | "Needs credentials";
  mode: "Read-only" | "Paper" | "Manual";
  scopes: string[];
  freshness: string;
  enabled: boolean;
};

const initialAdapters: Adapter[] = [
  {
    id: "ADP-001",
    name: "Binance",
    kind: "Exchange",
    environment: "Testnet",
    status: "Not tested",
    mode: "Read-only",
    scopes: ["Balances", "Trades", "Funding", "Positions"],
    freshness: "Not tested",
    enabled: true,
  },
  {
    id: "ADP-002",
    name: "Hyperliquid",
    kind: "DEX",
    environment: "Testnet",
    status: "Not tested",
    mode: "Read-only",
    scopes: ["Positions", "Open orders", "Market metadata"],
    freshness: "Not tested",
    enabled: true,
  },
  {
    id: "ADP-003",
    name: "Bybit",
    kind: "Exchange",
    environment: "Testnet",
    status: "Not tested",
    mode: "Read-only",
    scopes: ["Balances", "Positions", "Executions"],
    freshness: "Not tested",
    enabled: true,
  },
  {
    id: "ADP-004",
    name: "Interactive Brokers",
    kind: "Broker",
    environment: "Paper",
    status: "Healthy",
    mode: "Paper",
    scopes: ["Positions", "Executions", "Market data"],
    freshness: "8s",
    enabled: true,
  },
  {
    id: "ADP-005",
    name: "Coinbase",
    kind: "Exchange",
    environment: "Sandbox",
    status: "Degraded",
    mode: "Read-only",
    scopes: ["Balances", "Trades"],
    freshness: "12m",
    enabled: true,
  },
  {
    id: "ADP-006",
    name: "Kraken",
    kind: "Exchange",
    environment: "Sandbox",
    status: "Disconnected",
    mode: "Read-only",
    scopes: ["Balances", "Trades"],
    freshness: "Never",
    enabled: false,
  },
  {
    id: "ADP-007",
    name: "Fund Administrator",
    kind: "File transfer",
    environment: "Manual CSV",
    status: "Healthy",
    mode: "Manual",
    scopes: ["NAV packs", "Investor records"],
    freshness: "1d",
    enabled: true,
  },
];

function statusClass(status: Adapter["status"]) {
  if (status === "Healthy") return "border-positive/35 text-positive";
  if (status === "Degraded" || status === "Needs credentials")
    return "border-warning/35 text-warning";
  return "border-border text-muted-foreground";
}

function IntegrationsPage() {
  const [adapters, setAdapters] = useState(initialAdapters);
  const [testing, setTesting] = useState<string | null>(null);
  const [binanceResult, setBinanceResult] = useState<Awaited<
    ReturnType<typeof testBinanceTestnetConnection>
  > | null>(null);
  const [hyperliquidResult, setHyperliquidResult] = useState<Awaited<
    ReturnType<typeof testHyperliquidConnection>
  > | null>(null);
  const [bybitResult, setBybitResult] = useState<Awaited<
    ReturnType<typeof testBybitTestnetConnection>
  > | null>(null);
  const testBinanceConnection = useServerFn(testBinanceTestnetConnection);
  const testHyperliquid = useServerFn(testHyperliquidConnection);
  const testBybitConnection = useServerFn(testBybitTestnetConnection);

  const toggle = (id: string, enabled: boolean) => {
    setAdapters((items) => items.map((a) => (a.id === id ? { ...a, enabled } : a)));
    toast.success(`${enabled ? "Enabled" : "Disabled"} local ingestion adapter (demo)`);
  };

  const test = async (adapter: Adapter) => {
    setTesting(adapter.id);
    if (adapter.id === "ADP-001") {
      try {
        const result = await testBinanceConnection();
        setBinanceResult(result);
        setAdapters((items) =>
          items.map((item) =>
            item.id === adapter.id
              ? {
                  ...item,
                  status:
                    result.status === "connected"
                      ? "Healthy"
                      : result.status === "needs_credentials"
                        ? "Needs credentials"
                        : "Degraded",
                  freshness:
                    result.latencyMs === null ? "Unavailable" : `${result.latencyMs}ms probe`,
                }
              : item,
          ),
        );
        if (result.status === "connected") {
          toast.success("Binance Spot Testnet authenticated in read-only mode");
        } else if (result.status === "needs_credentials") {
          toast.warning("Testnet is reachable; server-side credentials are still required");
        } else {
          toast.error(result.message);
        }
      } catch {
        toast.error("Local Binance Testnet connection check was blocked or failed");
      } finally {
        setTesting(null);
      }
      return;
    }

    if (adapter.id === "ADP-002") {
      try {
        const result = await testHyperliquid();
        setHyperliquidResult(result);
        setAdapters((items) =>
          items.map((item) =>
            item.id === adapter.id
              ? {
                  ...item,
                  status:
                    result.status === "connected"
                      ? "Healthy"
                      : result.status === "needs_address"
                        ? "Needs credentials"
                        : "Degraded",
                  freshness:
                    result.latencyMs === null ? "Unavailable" : `${result.latencyMs}ms probe`,
                }
              : item,
          ),
        );
        if (result.status === "connected") {
          toast.success("Hyperliquid Testnet connected in public read-only mode");
        } else if (result.status === "needs_address") {
          toast.warning(
            "Hyperliquid Testnet is reachable; add a public Testnet wallet address for account data",
          );
        } else {
          toast.error(result.message);
        }
      } catch {
        toast.error("Local Hyperliquid connection check was blocked or failed");
      } finally {
        setTesting(null);
      }
      return;
    }

    if (adapter.id === "ADP-003") {
      try {
        const result = await testBybitConnection();
        setBybitResult(result);
        setAdapters((items) =>
          items.map((item) =>
            item.id === adapter.id
              ? {
                  ...item,
                  status:
                    result.status === "connected"
                      ? "Healthy"
                      : result.status === "needs_credentials"
                        ? "Needs credentials"
                        : "Degraded",
                  freshness:
                    result.latencyMs === null ? "Unavailable" : `${result.latencyMs}ms probe`,
                }
              : item,
          ),
        );
        if (result.status === "connected") {
          toast.success("Bybit Testnet authenticated in read-only mode");
        } else if (result.status === "needs_credentials") {
          toast.warning("Bybit Testnet is reachable; server-side credentials are still required");
        } else {
          toast.error(result.message);
        }
      } catch {
        toast.error("Local Bybit Testnet connection check was blocked or failed");
      } finally {
        setTesting(null);
      }
      return;
    }

    window.setTimeout(() => {
      setTesting(null);
      toast.success(`${adapter.name} connectivity check completed (demo)`);
    }, 450);
  };

  return (
    <AppShell>
      <PageHeader
        kicker="P3 · Platform connectivity"
        title="Integrations"
        subtitle="Govern exchange, broker, custody and administrator connections from one read-only control plane."
        actions={
          <Button size="sm" onClick={() => toast("Adapter catalogue opened (demo)")}>
            <PlugZap className="h-3.5 w-3.5" /> Add adapter
          </Button>
        }
      />
      <div className="space-y-6 p-6">
        <SafetyBanner
          title="Least-privilege connectivity"
          text="Production credentials, withdrawals and live order scopes are not supported. Secrets are never rendered in the browser."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Adapters" value="7" sub="6 enabled" />
          <MetricCard
            label="Healthy"
            value={String(adapters.filter((adapter) => adapter.status === "Healthy").length)}
            tone="positive"
          />
          <MetricCard
            label="Needs attention"
            value={String(
              adapters.filter((adapter) =>
                ["Degraded", "Disconnected", "Needs credentials"].includes(adapter.status),
              ).length,
            )}
            tone="warning"
          />
          <MetricCard label="Live-trade scopes" value="0" sub="Enforced boundary" />
        </div>
        <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
          <Panel title="Adapter registry" subtitle="Environment, scope and freshness">
            <div className="grid gap-3 lg:grid-cols-2">
              {adapters.map((adapter) => (
                <article
                  key={adapter.id}
                  className="rounded-md border border-border/70 bg-background/35 p-3.5"
                >
                  <div className="flex items-start gap-3">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                      <PlugZap className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-medium">{adapter.name}</h3>
                        <Badge variant="outline" className={statusClass(adapter.status)}>
                          {adapter.status}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {adapter.id} · {adapter.kind} · {adapter.environment}
                      </div>
                    </div>
                    <Switch
                      checked={adapter.enabled}
                      onCheckedChange={(value) => toggle(adapter.id, value)}
                      aria-label={`Toggle ${adapter.name}`}
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {adapter.scopes.map((scope) => (
                      <Badge key={scope} variant="secondary" className="text-[10px]">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                  {adapter.id === "ADP-001" && binanceResult && (
                    <div
                      className={`mt-3 rounded-md border p-2.5 text-xs ${
                        binanceResult.status === "connected"
                          ? "border-positive/30 bg-positive/5"
                          : "border-warning/30 bg-warning/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Real Testnet probe</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {binanceResult.latencyMs === null ? "—" : `${binanceResult.latencyMs}ms`}
                        </span>
                      </div>
                      <p className="mt-1 leading-relaxed text-muted-foreground">
                        {binanceResult.message}
                      </p>
                      {binanceResult.authenticated && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <Badge variant="secondary" className="text-[10px]">
                            {binanceResult.accountType}
                          </Badge>
                          <Badge variant="secondary" className="text-[10px]">
                            {binanceResult.nonZeroAssetCount ?? 0} non-zero assets
                          </Badge>
                          {(binanceResult.permissions ?? []).map((permission) => (
                            <Badge key={permission} variant="secondary" className="text-[10px]">
                              {permission}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {adapter.id === "ADP-002" && hyperliquidResult && (
                    <div
                      className={`mt-3 rounded-md border p-2.5 text-xs ${
                        hyperliquidResult.status === "connected"
                          ? "border-positive/30 bg-positive/5"
                          : "border-warning/30 bg-warning/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Testnet Info API probe</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {hyperliquidResult.latencyMs === null
                            ? "โ€”"
                            : `${hyperliquidResult.latencyMs}ms`}
                        </span>
                      </div>
                      <p className="mt-1 leading-relaxed text-muted-foreground">
                        {hyperliquidResult.message}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge variant="secondary" className="text-[10px]">
                          {hyperliquidResult.marketCount ?? 0} markets
                        </Badge>
                        {hyperliquidResult.walletConfigured && (
                          <>
                            <Badge variant="secondary" className="text-[10px]">
                              {hyperliquidResult.openPositionCount ?? 0} positions
                            </Badge>
                            <Badge variant="secondary" className="text-[10px]">
                              {hyperliquidResult.openOrderCount ?? 0} open orders
                            </Badge>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                  {adapter.id === "ADP-003" && bybitResult && (
                    <div
                      className={`mt-3 rounded-md border p-2.5 text-xs ${
                        bybitResult.status === "connected"
                          ? "border-positive/30 bg-positive/5"
                          : "border-warning/30 bg-warning/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Real Testnet probe</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {bybitResult.latencyMs === null ? "โ€”" : `${bybitResult.latencyMs}ms`}
                        </span>
                      </div>
                      <p className="mt-1 leading-relaxed text-muted-foreground">
                        {bybitResult.message}
                      </p>
                      {bybitResult.authenticated && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <Badge variant="secondary" className="text-[10px]">
                            {bybitResult.accountType}
                          </Badge>
                          <Badge variant="secondary" className="text-[10px]">
                            {bybitResult.nonZeroAssetCount ?? 0} non-zero assets
                          </Badge>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="mt-3 flex items-center justify-between border-t border-border/50 pt-3 text-xs">
                    <span className="text-muted-foreground">
                      {adapter.mode} · fresh {adapter.freshness}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!adapter.enabled || testing === adapter.id}
                      onClick={() => void test(adapter)}
                    >
                      <RefreshCw
                        className={`h-3.5 w-3.5 ${testing === adapter.id ? "animate-spin" : ""}`}
                      />{" "}
                      Test
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          </Panel>
          <div className="space-y-6">
            <Panel title="Credential posture" subtitle="Server-side vault controls">
              <ul className="space-y-3 text-sm">
                <li className="flex gap-2">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                  <div>
                    <div className="font-medium">Secrets masked</div>
                    <div className="text-xs text-muted-foreground">
                      No raw credentials exposed to the client.
                    </div>
                  </div>
                </li>
                <li className="flex gap-2">
                  <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <div className="font-medium">Bybit Testnet</div>
                    <div className="text-xs text-muted-foreground">
                      {bybitResult?.authenticated
                        ? "Authenticated from server-side environment variables."
                        : "Awaiting server-side credentials in .env.local."}
                    </div>
                  </div>
                </li>
                <li className="flex gap-2">
                  <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <div className="font-medium">Binance Testnet</div>
                    <div className="text-xs text-muted-foreground">
                      {binanceResult?.authenticated
                        ? "Authenticated from server-side environment variables."
                        : "Awaiting server-side credentials in .env.local."}
                    </div>
                  </div>
                </li>
                <li className="flex gap-2">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                  <div>
                    <div className="font-medium">Hyperliquid Testnet account</div>
                    <div className="text-xs text-muted-foreground">
                      {hyperliquidResult?.walletConfigured
                        ? "Testnet wallet address loaded for read-only account monitoring."
                        : "Optional public Testnet wallet address can be added in .env.local; no wallet signing."}
                    </div>
                  </div>
                </li>
                <li className="flex gap-2">
                  <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
                  <div>
                    <div className="font-medium">Least privilege</div>
                    <div className="text-xs text-muted-foreground">Read and paper scopes only.</div>
                  </div>
                </li>
                <li className="flex gap-2">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                  <div>
                    <div className="font-medium">Rotation due</div>
                    <div className="text-xs text-muted-foreground">
                      Coinbase sandbox key · 9 days.
                    </div>
                  </div>
                </li>
              </ul>
            </Panel>
            <Panel title="Capability boundary">
              <div className="space-y-2 text-xs">
                {[
                  ["Balances & positions", true],
                  ["Trades & funding history", true],
                  ["Paper order simulation", true],
                  ["Live order submission", false],
                  ["Withdrawals / transfers", false],
                ].map(([label, allowed]) => (
                  <div
                    key={String(label)}
                    className="flex items-center justify-between rounded-md border border-border/60 p-2.5"
                  >
                    <span>{label}</span>
                    {allowed ? (
                      <CheckCircle2 className="h-4 w-4 text-positive" />
                    ) : (
                      <span className="font-medium text-destructive">Blocked</span>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
