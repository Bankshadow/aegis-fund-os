export type GovernanceState = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
export type RuntimeState = "IDLE" | "RUNNING" | "PAUSED" | "STOPPED";
export type GovernanceEventType =
  | "bot.created"
  | "approval.requested"
  | "approval.approved"
  | "approval.auto_approved_testnet"
  | "approval.rejected"
  | "runtime.started"
  | "runtime.paused"
  | "runtime.resumed"
  | "runtime.stopped"
  | "testnet.orders_placed"
  | "testnet.orders_cancelled";

export interface GovernedBot {
  id: string;
  state: GovernanceState;
  makerId: string;
  checkerId?: string;
  version: number;
}

export const transitionRuntime = (
  approvalState: GovernanceState,
  current: RuntimeState,
  next: RuntimeState,
) => {
  if (approvalState !== "APPROVED")
    throw new Error("Only an approved bot can change runtime state");
  const allowed: Record<RuntimeState, RuntimeState[]> = {
    IDLE: ["RUNNING"],
    RUNNING: ["PAUSED", "STOPPED"],
    PAUSED: ["RUNNING", "STOPPED"],
    STOPPED: [],
  };
  if (!allowed[current].includes(next))
    throw new Error(`Invalid runtime transition: ${current} -> ${next}`);
  return next;
};

export interface GovernanceEvent {
  eventId: string;
  botId: string;
  eventType: GovernanceEventType;
  actorId: string;
  payload: Record<string, string | number | boolean | null>;
  previousHash: string;
  occurredAt: string;
  eventHash: string;
}

const canonical = (value: unknown): string => {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`)
    .join(",")}}`;
};

export const sha256 = async (value: string) => {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

export const appendGovernanceEvent = async (
  events: readonly GovernanceEvent[],
  input: Omit<GovernanceEvent, "previousHash" | "eventHash">,
): Promise<GovernanceEvent> => {
  const previousHash = events.at(-1)?.eventHash ?? "GENESIS";
  const unsigned = { ...input, previousHash };
  return { ...unsigned, eventHash: await sha256(canonical(unsigned)) };
};

export const verifyGovernanceChain = async (events: readonly GovernanceEvent[]) => {
  let previousHash = "GENESIS";
  for (const event of events) {
    if (event.previousHash !== previousHash) return false;
    const { eventHash, ...unsigned } = event;
    if ((await sha256(canonical(unsigned))) !== eventHash) return false;
    previousHash = eventHash;
  }
  return true;
};

export const verifyGovernanceChains = async (events: readonly GovernanceEvent[]) => {
  const chains = new Map<string, GovernanceEvent[]>();
  for (const event of events) {
    const chain = chains.get(event.botId) ?? [];
    chain.push(event);
    chains.set(event.botId, chain);
  }
  return (await Promise.all([...chains.values()].map(verifyGovernanceChain))).every(Boolean);
};

export const submitForApproval = (bot: GovernedBot, actorId: string): GovernedBot => {
  if (bot.state !== "DRAFT") throw new Error("Only a draft can be submitted");
  if (actorId !== bot.makerId) throw new Error("Only the maker can submit this draft");
  return { ...bot, state: "PENDING_APPROVAL", version: bot.version + 1 };
};

export const decideApproval = (
  bot: GovernedBot,
  checkerId: string,
  decision: "APPROVED" | "REJECTED",
): GovernedBot => {
  if (bot.state !== "PENDING_APPROVAL") throw new Error("Bot is not awaiting approval");
  if (checkerId === bot.makerId) throw new Error("Maker cannot be checker");
  return { ...bot, state: decision, checkerId, version: bot.version + 1 };
};
