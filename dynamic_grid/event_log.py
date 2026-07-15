"""Structured decision-event logging for the grid agents.

This is the foundation layer for three things at once (see the user's
Virtual Office / MAS / Cognee direction):

  1. **MAS memory** - each engine/layer is an "agent"; its decisions become
     structured events other agents (or an orchestrator) can read back.
  2. **Cognee ingestion** - events export as JSON Lines (`to_jsonl`) and as
     natural-language "knowledge statements" (`to_knowledge`) suitable for a
     knowledge-graph memory platform, not just raw numbers.
  3. **Virtual Office animation** - events carry agent_id + state + regime,
     so a front-end can render each agent's live status from the log alone.

Design rule: **opt-in and non-invasive.** An engine with `logger=None`
(the default) behaves byte-identically to before - every prior test and
result reproduces. Logging only happens when a DecisionLog is attached.
"""

import json
from dataclasses import dataclass, field, asdict

# Canonical decision types an agent can emit. Kept small and stable so the
# knowledge graph has a fixed vocabulary of edges.
BUILD = "build_zone"            # opened a new grid zone
SKIP_BUILD = "skip_build"       # declined to open (trend gate / regime / cooldown)
FILL = "fill"                   # a buy level filled
ENTRY_BLOCK = "entry_block"     # momentum confirmation deferred a fill
TAKE_PROFIT = "take_profit"     # a lot hit TP
STOP_OUT = "stop_out"           # zone stop cut the whole zone
CONSOLIDATE = "consolidate"     # merged pending levels on an anomaly
RECENTER = "recenter"           # rebuilt higher, following price up
# orchestrator-level (memory-loop) decisions:
RISK_CUT = "risk_cut"           # reduced a layer's risk budget after reading memory
RISK_RESTORE = "risk_restore"   # restored a layer's budget after clean performance


@dataclass
class DecisionEvent:
    bar: int                    # bar index within the run (the "timestamp")
    agent_id: str               # which engine/layer emitted this
    decision: str               # one of the constants above
    reason: str                 # short human/agent-readable why
    price: float
    regime: str                 # market regime at decision time
    momentum: float             # normalized momentum signal
    equity: float
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_knowledge(self) -> str:
        """One natural-language statement for a knowledge graph.

        Example: "At bar 142, agent 'core' skipped opening a zone because
        the market regime was trend_down (momentum -1.83). Price 61840."
        """
        verb = {
            BUILD: "opened a new grid zone",
            SKIP_BUILD: "declined to open a zone",
            FILL: "filled a buy order",
            ENTRY_BLOCK: "deferred a fill",
            TAKE_PROFIT: "closed a lot at take-profit",
            STOP_OUT: "cut the whole zone at its stop",
            CONSOLIDATE: "consolidated pending orders",
            RECENTER: "rebuilt its zone higher following price",
            RISK_CUT: "cut a layer's risk budget",
            RISK_RESTORE: "restored a layer's risk budget",
        }.get(self.decision, self.decision)
        return (f"At bar {self.bar}, agent '{self.agent_id}' {verb} "
                f"because {self.reason}. Regime was {self.regime} "
                f"(momentum {self.momentum:+.2f}), price {self.price:.2f}, "
                f"equity {self.equity:.2f}.")


class DecisionLog:
    """Collects DecisionEvents from one or more agents in a run."""

    def __init__(self):
        self.events: list[DecisionEvent] = []

    def record(self, **kwargs) -> None:
        self.events.append(DecisionEvent(**kwargs))

    # -- exports -----------------------------------------------------------
    def to_jsonl(self, path: str) -> None:
        """JSON Lines - the shape most memory/ingestion tools expect."""
        with open(path, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    def to_knowledge_file(self, path: str) -> None:
        """One knowledge statement per line - for graph/embedding ingestion."""
        with open(path, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(e.to_knowledge() + "\n")

    # -- quick aggregate views (also useful as MAS "shared summary") -------
    def counts_by_decision(self) -> dict:
        out = {}
        for e in self.events:
            out[e.decision] = out.get(e.decision, 0) + 1
        return out

    def counts_by_agent(self) -> dict:
        out = {}
        for e in self.events:
            out[e.agent_id] = out.get(e.agent_id, 0) + 1
        return out

    def summary(self) -> str:
        """A compact shared-context summary an orchestrator agent could read."""
        by_dec = self.counts_by_decision()
        by_agent = self.counts_by_agent()
        parts = [f"{len(self.events)} decisions logged"]
        if by_agent:
            parts.append("by agent: " + ", ".join(
                f"{k}={v}" for k, v in sorted(by_agent.items())))
        if by_dec:
            parts.append("by type: " + ", ".join(
                f"{k}={v}" for k, v in sorted(by_dec.items())))
        return " | ".join(parts)
