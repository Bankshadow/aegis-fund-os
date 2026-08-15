import { Link } from "@tanstack/react-router";
import { AlertTriangle, FlaskConical } from "lucide-react";
import { Panel } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import {
  RESEARCH_BOARD_SUBTITLE,
  RESEARCH_BOARD_TITLE,
  RESEARCH_CANDIDATES,
  RESEARCH_COLD_SHOWER,
  type ResearchCandidate,
  verdictLabel,
  verdictTone,
} from "@/lib/research-board";
import { cn } from "@/lib/utils";

const fmtSigned = (n: number, digits = 1) => `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
const fmtDd = (n: number, digits = 1) => `−${Math.abs(n).toFixed(digits)}%`;

function VerdictBadge({ verdict }: { verdict: ResearchCandidate["verdict"] }) {
  const tone = verdictTone(verdict);
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] uppercase tracking-wider whitespace-nowrap",
        tone === "pos" && "border-positive/40 text-positive bg-positive/10",
        tone === "warn" && "border-warning/40 text-warning bg-warning/10",
        tone === "neg" && "border-destructive/40 text-destructive bg-destructive/10",
      )}
    >
      {verdictLabel(verdict)}
    </Badge>
  );
}

/** Minara-style honesty strip: backtests are not forecasts; DD is not optional. */
export function ColdShowerBanner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-start gap-3 rounded-md border border-destructive/35 bg-destructive/5 px-3 py-2.5",
        className,
      )}
    >
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-destructive/10 text-destructive">
        <AlertTriangle className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">Cold shower · read twice</div>
        <div className="text-xs text-muted-foreground leading-relaxed">{RESEARCH_COLD_SHOWER}</div>
      </div>
      <Badge variant="outline" className="border-destructive/40 text-destructive">
        NFA · NO LIVE ORDER
      </Badge>
    </div>
  );
}

/**
 * Paired return | max-DD tile — risk lives next to return, never in a footnote.
 */
export function ReturnDrawdownPair({
  returnPct,
  returnLabel,
  maxDdPct,
  vsBenchmarkPct,
  benchmarkLabel,
}: {
  returnPct: number;
  returnLabel: string;
  maxDdPct: number;
  vsBenchmarkPct?: number | null;
  benchmarkLabel?: string;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 min-w-[160px]">
      <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-2">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {returnLabel}
        </div>
        <div
          className={cn(
            "num text-base font-semibold",
            returnPct >= 0 ? "text-positive" : "text-destructive",
          )}
        >
          {fmtSigned(returnPct)}
        </div>
      </div>
      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Max DD</div>
        <div className="num text-base font-semibold text-destructive">{fmtDd(maxDdPct)}</div>
      </div>
      {vsBenchmarkPct != null && (
        <div className="col-span-2 text-[11px] text-muted-foreground">
          vs {benchmarkLabel ?? "benchmark"}:{" "}
          <span
            className={cn(
              "num font-medium",
              vsBenchmarkPct >= 0 ? "text-positive" : "text-destructive",
            )}
          >
            {fmtSigned(vsBenchmarkPct)}
          </span>
        </div>
      )}
    </div>
  );
}

function CandidateLink({ candidate }: { candidate: ResearchCandidate }) {
  const label = (
    <>
      {candidate.id} · {candidate.name}
    </>
  );
  if (candidate.labVariant) {
    return (
      <Link
        to="/walk-forward"
        search={{ variant: candidate.labVariant, cost: "thai" }}
        className="font-medium hover:text-primary hover:underline underline-offset-4"
      >
        {label}
      </Link>
    );
  }
  return (
    <Link
      to="/walk-forward"
      search={{ variant: "baseline", cost: "thai" }}
      className="font-medium hover:text-primary hover:underline underline-offset-4"
    >
      {label}
    </Link>
  );
}

export function MeasuredHonestlyBoard() {
  return (
    <Panel
      title={RESEARCH_BOARD_TITLE}
      subtitle={RESEARCH_BOARD_SUBTITLE}
      actions={
        <Link
          to="/walk-forward"
          search={{ variant: "baseline", cost: "thai" }}
          className="inline-flex items-center gap-1.5 text-xs text-primary underline-offset-4 hover:underline"
        >
          <FlaskConical className="h-3.5 w-3.5" /> Walk-Forward Lab
        </Link>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] text-sm">
          <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border/60">
              <th className="text-left py-2 pr-3 font-medium">Candidate</th>
              <th className="text-left py-2 pr-3 font-medium">Return | Max DD</th>
              <th className="text-right py-2 pr-3 font-medium">Robust</th>
              <th className="text-left py-2 pr-3 font-medium">Gate</th>
              <th className="text-left py-2 font-medium">Diagnosis (why this failed / stalled)</th>
            </tr>
          </thead>
          <tbody>
            {RESEARCH_CANDIDATES.map((c) => (
              <tr key={c.id} className="border-b border-border/40 align-top hover:bg-accent/20">
                <td className="py-3 pr-3">
                  <CandidateLink candidate={c} />
                  <div className="mt-0.5 text-[11px] text-muted-foreground">
                    {c.universe} · {c.window}
                  </div>
                  <div className="text-[10px] text-muted-foreground/80">{c.logRef}</div>
                </td>
                <td className="py-3 pr-3">
                  <ReturnDrawdownPair
                    returnPct={c.returnPct}
                    returnLabel={c.returnLabel}
                    maxDdPct={c.maxDdPct}
                    vsBenchmarkPct={c.vsBenchmarkPct}
                    benchmarkLabel={c.benchmarkLabel}
                  />
                </td>
                <td className="py-3 pr-3 text-right num">
                  {c.robust == null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <span className={c.robust >= 0 ? "text-positive" : "text-destructive"}>
                      {c.robust >= 0 ? "+" : ""}
                      {c.robust.toFixed(2)}
                    </span>
                  )}
                  {c.sharpe != null && (
                    <div className="text-[10px] text-muted-foreground">
                      Sharpe {c.sharpe.toFixed(2)}
                    </div>
                  )}
                </td>
                <td className="py-3 pr-3">
                  <VerdictBadge verdict={c.verdict} />
                </td>
                <td className="py-3 text-xs text-muted-foreground leading-relaxed max-w-md">
                  {c.diagnosis}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Source: declared criteria before each run · ≥3 seeds / held-out where required · negatives
        logged in <span className="font-mono">docs/VALIDATION_LOG.md</span>. Model self-report is
        never the final vote.
      </p>
    </Panel>
  );
}
