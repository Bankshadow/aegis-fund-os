import { Badge } from "@/components/ui/badge";
import type { BotEnvironment, BotState } from "@/lib/grid-bot-domain";
export function EnvironmentBadge({ value }: { value: BotEnvironment }) {
  return (
    <Badge
      variant="outline"
      className={
        value === "BINANCE_TESTNET"
          ? "border-info/40 text-info"
          : value === "PAPER"
            ? "border-warning/40 text-warning"
            : ""
      }
    >
      {value.replace("BINANCE_", "")}
    </Badge>
  );
}
export function BotStateBadge({ value }: { value: BotState }) {
  const tone =
    value === "RUNNING"
      ? "border-positive/40 text-positive"
      : value === "RECOVERY_REQUIRED"
        ? "border-destructive/40 text-destructive"
        : value === "PAUSED" || value === "WAITING_FOR_TRIGGER"
          ? "border-warning/40 text-warning"
          : "";
  return (
    <Badge variant="outline" className={tone}>
      {value.replaceAll("_", " ")}
    </Badge>
  );
}
