"""Demo: structured decision logging across a multi-agent grid run.

Produces the foundation artifacts for the Virtual Office / MAS / Cognee
direction:

  results/decision_events.jsonl   - one JSON event per agent decision
                                    (feed to Cognee / any memory store)
  results/decision_knowledge.txt  - natural-language knowledge statements
                                    (feed to a knowledge-graph / embeddings)

Each grid layer runs as a named agent (fast / core / wide), all writing to
one shared DecisionLog - the minimal shape of a multi-agent system sharing
memory. The printed summary is the kind of shared-context digest an
orchestrator agent would read back.
"""

import os

from dynamic_grid import DynamicGridConfig, generate_scenario, make_layers
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from multilayer_demo import BASE


def run_logged_multiagent(ohlc, base_cfg):
    """Run fast/core/wide layers + memory-loop orchestrator, one shared log.

    v3.5: switched from plain logged engines to MemoryOrchestrator so the
    log also carries governance events (risk_cut / risk_restore) - the
    Virtual Office renders the orchestrator as a fourth desk.
    """
    orch = MemoryOrchestrator(make_layers(base_cfg))
    equity = 10_000.0
    cash = 0.0
    for o, h, l, c in ohlc:
        cash += orch.on_bar(o, h, l, c, equity + cash)
    return orch.log


def main():
    base_cfg = DynamicGridConfig(**BASE)
    # regime_switch exercises every decision type (builds, stops, recenters,
    # consolidations) so the log is representative.
    ohlc = generate_scenario("regime_switch", n_bars=2000, seed=7)

    log = run_logged_multiagent(ohlc, base_cfg)

    print("=== Shared-context summary (what an orchestrator agent would read) ===")
    print(log.summary())

    print("\n=== Sample knowledge statements (for the knowledge graph) ===")
    # show a spread: first few + a few interesting non-fill decisions
    shown = 0
    for e in log.events:
        if e.decision in ("build_zone", "stop_out", "recenter", "skip_build",
                          "consolidate", "entry_block") and shown < 6:
            print(" -", e.to_knowledge())
            shown += 1

    os.makedirs("results", exist_ok=True)
    jsonl_path = os.path.join("results", "decision_events.jsonl")
    know_path = os.path.join("results", "decision_knowledge.txt")
    log.to_jsonl(jsonl_path)
    log.to_knowledge_file(know_path)
    print(f"\nsaved: {jsonl_path} ({len(log.events)} events)")
    print(f"saved: {know_path}")

    print("\n--- How this plugs into your Virtual Office / Cognee stack ---")
    print("1. decision_events.jsonl -> ingest into Cognee as structured events")
    print("   (each carries agent_id + regime + momentum for graph edges)")
    print("2. decision_knowledge.txt -> ingest as natural-language memories")
    print("   for the knowledge graph / semantic recall")
    print("3. Virtual Office front-end reads agent_id + decision + regime per")
    print("   bar to animate each agent's live state (trading / cooldown / idle)")
    print("4. NEXT: also log the walk-forward lesson (Static>Dynamic, seed")
    print("   sensitivity) as knowledge - negative results are the most")
    print("   valuable thing to persist, not just profitable trades")


if __name__ == "__main__":
    main()
