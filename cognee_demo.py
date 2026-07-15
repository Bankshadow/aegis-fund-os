"""Push grid decision-memory + findings into Cognee, then recall.

This is the end-to-end wiring of the grid system into the user's MAS /
Virtual Office / Cognee stack:

    grid run --> DecisionLog --> Cognee knowledge graph --> agent recall

Cognee is an OPTIONAL dependency and is not installed in this repo's dev
env. Run this after installing it in your agent environment:

    uv pip install cognee
    export LLM_API_KEY=...        # Cognee needs an LLM to build the graph
    python cognee_demo.py

Without cognee installed, the script still builds the log and prints exactly
what WOULD be pushed (so you can inspect the payload before wiring it up).
"""

from dynamic_grid import DynamicGridConfig, generate_scenario
from dynamic_grid.cognee_adapter import (PROJECT_FINDINGS, push_findings,
                                        push_log, recall)
from logging_demo import run_logged_multiagent
from multilayer_demo import BASE


def build_log():
    base_cfg = DynamicGridConfig(**BASE)
    ohlc = generate_scenario("regime_switch", n_bars=2000, seed=7)
    return run_logged_multiagent(ohlc, base_cfg)


def main():
    log = build_log()
    print(f"Built decision log: {log.summary()}\n")

    try:
        n1 = push_findings(PROJECT_FINDINGS)
        n2 = push_log(log, batch=True)
        print(f"Pushed {n1} findings + {n2} decision statements to Cognee.\n")

        # An orchestrator agent would recall context before deciding:
        for q in ["Is the Dynamic grid proven better than Static in live markets?",
                  "What went wrong in walk-forward testing?",
                  "How should I judge the momentum confirmation feature?"]:
            print(f"Q: {q}")
            for r in recall(q):
                print(f"   -> {r}")
            print()

    except RuntimeError as e:
        # cognee not installed (or API mismatch) - show the payload instead
        print("Cognee not available:", e)
        print("\n--- Payload that WOULD be pushed (findings dataset) ---")
        for f in PROJECT_FINDINGS:
            print(" *", f)
        print(f"\n--- Plus {len(log.events)} decision statements. Sample: ---")
        for e in log.events[:3]:
            print(" *", e.to_knowledge())


if __name__ == "__main__":
    main()
