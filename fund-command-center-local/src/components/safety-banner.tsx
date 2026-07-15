import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function SafetyBanner({
  title = "Non-live control boundary",
  text = "Research, paper and read-only workflows only. This interface cannot transmit live orders.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-warning/35 bg-warning/5 px-3 py-2.5">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-warning/10 text-warning">
        <ShieldCheck className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{title}</div>
        <div className="text-xs text-muted-foreground">{text}</div>
      </div>
      <Badge variant="outline" className="border-warning/40 text-warning">
        PAPER / READ-ONLY
      </Badge>
    </div>
  );
}
