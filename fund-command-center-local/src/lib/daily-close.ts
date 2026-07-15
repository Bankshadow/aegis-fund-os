export type DailyCloseCheck = "data" | "prices" | "recon" | "fx" | "fees";

export type DailyCloseInput = {
  state: "Provisional" | "Locked";
  maker: string;
  reviewer: string;
  checks: Record<DailyCloseCheck, boolean>;
};

export type DailyCloseDecision = {
  state: "Blocked" | "Ready to lock" | "Locked";
  canLock: boolean;
  blockers: string[];
};

const CHECK_LABELS: Record<DailyCloseCheck, string> = {
  data: "Data freshness is incomplete",
  prices: "Pricing completeness is incomplete",
  recon: "Reconciliation still has unresolved exceptions",
  fx: "FX rates are not finalized",
  fees: "Fee accruals are not posted",
};

export function evaluateDailyClose(input: DailyCloseInput): DailyCloseDecision {
  if (input.state === "Locked") return { state: "Locked", canLock: false, blockers: [] };

  const blockers = (Object.keys(CHECK_LABELS) as DailyCloseCheck[])
    .filter((check) => !input.checks[check])
    .map((check) => CHECK_LABELS[check]);

  if (!input.reviewer) blockers.push("An independent reviewer is required");
  else if (input.reviewer === input.maker)
    blockers.push("Maker and reviewer must be different people");

  return blockers.length > 0
    ? { state: "Blocked", canLock: false, blockers }
    : { state: "Ready to lock", canLock: true, blockers: [] };
}
