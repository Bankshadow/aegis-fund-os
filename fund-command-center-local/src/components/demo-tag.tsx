import { cn } from "@/lib/utils";

export function DemoTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-border/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground",
        className,
      )}
      title="Seeded demo data — not investment advice"
    >
      <span className="h-1 w-1 rounded-full bg-warning/80" />
      Demo
    </span>
  );
}

export function PaperBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border border-warning/40 bg-warning/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-warning",
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-warning animate-pulse" />
      Paper / Non-Live
    </span>
  );
}

export function StatusDot({ tone }: { tone: "positive" | "warning" | "destructive" | "muted" | "info" }) {
  const map: Record<string, string> = {
    positive: "bg-positive",
    warning: "bg-warning",
    destructive: "bg-destructive",
    info: "bg-info",
    muted: "bg-muted-foreground/60",
  };
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full", map[tone])} />;
}

