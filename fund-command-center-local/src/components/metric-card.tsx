import { cn } from "@/lib/utils";
import { DemoTag } from "./demo-tag";
import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "positive" | "negative" | "warning";
  hint?: string;
  className?: string;
  demo?: boolean;
}

export function MetricCard({ label, value, sub, tone = "default", hint, className, demo = true }: MetricCardProps) {
  const toneCls =
    tone === "positive" ? "text-positive"
    : tone === "negative" ? "text-destructive"
    : tone === "warning" ? "text-warning"
    : "text-foreground";
  return (
    <div className={cn("rounded-md border border-border/70 bg-card/60 p-4 flex flex-col gap-1.5 min-w-0", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground truncate">{label}</div>
        {demo && <DemoTag />}
      </div>
      <div className={cn("num text-xl xl:text-2xl font-semibold leading-tight tracking-tight break-words", toneCls)}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground num">{sub}</div>}
      {hint && <div className="text-[11px] text-muted-foreground/80">{hint}</div>}
    </div>
  );
}

export function fmtMoney(n: number, ccy = "USD", fractional = 2) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: ccy, minimumFractionDigits: fractional, maximumFractionDigits: fractional,
  }).format(n);
}
export function fmtPct(n: number, digits = 2) {
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(digits)}%`;
}
export function fmtNum(n: number, digits = 0) {
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

