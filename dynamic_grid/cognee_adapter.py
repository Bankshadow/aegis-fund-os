"""Bridge from the grid system's DecisionLog to Cognee AI memory.

Cognee (https://github.com/topoteretes/cognee) is a self-hosted knowledge-graph
memory platform for AI agents. This adapter pushes two kinds of memory into it:

  1. **Decision knowledge** - the per-bar agent decisions from a DecisionLog,
     as natural-language statements (Cognee builds graph edges from them).
  2. **Findings / negative results** - the higher-value lessons (walk-forward
     Static>Dynamic, overfitting, seed sensitivity). Persisting these is the
     whole point: an orchestrator agent that recalls "Dynamic overfits to a
     single training regime" makes better calls than one that only sees
     profitable trade logs.

Design notes:
  - **Cognee is an optional dependency.** It is NOT installed in this repo's
    dev env. Import is guarded; every function raises a clear, actionable
    error if cognee is missing, instead of an ImportError at module load.
  - **API-version tolerant.** Cognee has both a modern high-level API
    (`remember`/`recall`) and a classic pipeline API (`add`+`cognify`+
    `search`). Which one ships depends on the installed version, and this
    machine can't verify either - so the adapter feature-detects at call
    time and uses whichever the installed cognee exposes. If neither is
    found, it says so rather than guessing.
  - Cognee is fully async; sync wrappers are provided for convenience.
"""

import asyncio


def _import_cognee():
    try:
        import cognee  # noqa: F401
        return cognee
    except ImportError as e:
        raise RuntimeError(
            "cognee is not installed. Install it in your agent env with "
            "`uv pip install cognee` (or pip/poetry), set LLM_API_KEY, then "
            "re-run. See https://github.com/topoteretes/cognee"
        ) from e


async def _remember(cognee, text: str, **kw):
    """Store one memory, using whichever API this cognee version exposes."""
    if hasattr(cognee, "remember"):
        # modern high-level API: add + cognify + improve in one call
        return await cognee.remember(text, **kw)
    if hasattr(cognee, "add") and hasattr(cognee, "cognify"):
        # classic pipeline API
        await cognee.add(text, **({"dataset_name": kw["dataset"]}
                                  if "dataset" in kw else {}))
        return await cognee.cognify()
    raise RuntimeError(
        "Installed cognee exposes neither remember() nor add()+cognify(); "
        "check the version / API docs at github.com/topoteretes/cognee"
    )


async def _recall(cognee, query: str, **kw):
    if hasattr(cognee, "recall"):
        return await cognee.recall(query, **kw)
    if hasattr(cognee, "search"):
        return await cognee.search(query)
    raise RuntimeError(
        "Installed cognee exposes neither recall() nor search()."
    )


# -- async API ------------------------------------------------------------
async def push_log_async(log, dataset: str = "grid_decisions",
                         batch: bool = True):
    """Ingest a DecisionLog's knowledge statements into Cognee.

    batch=True joins statements into one document (faster, fewer graph
    builds); batch=False stores each decision as its own memory (finer
    provenance, slower). Also stores the run-level summary().
    """
    cognee = _import_cognee()
    statements = [e.to_knowledge() for e in log.events]
    if batch:
        await _remember(cognee, "\n".join(statements), dataset=dataset)
    else:
        for s in statements:
            await _remember(cognee, s, dataset=dataset)
    await _remember(cognee, "Run summary: " + log.summary(), dataset=dataset)
    return len(statements)


async def push_findings_async(findings: list[str],
                             dataset: str = "grid_findings"):
    """Ingest high-value lessons / negative results (see module docstring)."""
    cognee = _import_cognee()
    for f in findings:
        await _remember(cognee, f, dataset=dataset)
    return len(findings)


async def recall_async(query: str, **kw):
    cognee = _import_cognee()
    return await _recall(cognee, query, **kw)


# -- sync convenience wrappers -------------------------------------------
def push_log(log, dataset: str = "grid_decisions", batch: bool = True) -> int:
    return asyncio.run(push_log_async(log, dataset, batch))


def push_findings(findings: list[str], dataset: str = "grid_findings") -> int:
    return asyncio.run(push_findings_async(findings, dataset))


def recall(query: str, **kw):
    return asyncio.run(recall_async(query, **kw))


# The findings worth persisting from THIS project's own validation work -
# negative results an orchestrator agent should know before trusting the
# grid. Pass to push_findings() to seed the knowledge graph.
PROJECT_FINDINGS = [
    "Walk-forward validation on real BTC/USDT daily data (1000 bars) showed "
    "the Static grid beat the Dynamic grid on both mean and median "
    "out-of-sample return - the opposite of every synthetic-data result. Do "
    "not trust synthetic backtests as proof the Dynamic grid is superior in "
    "live markets.",

    "The Dynamic grid's walk-forward optimizer overfits to a single training "
    "window's regime: a config tuned on a strong bull run sat out the next "
    "window's mild pullback (zone stop + cooldown) and missed the rebound "
    "that the Static grid held through.",

    "Sub-window robust scoring (scoring a config across 4 sub-windows of the "
    "train slice instead of one blob) reduced tail risk substantially (worst "
    "max drawdown across configs dropped from ~21% to ~3.6%) but did NOT "
    "reverse Static's win on return.",

    "Methodology lesson: a single random seed can look like a clean win by "
    "luck. Always aggregate across multiple seeds before concluding - the "
    "first walk-forward check (seed 0 only) falsely suggested the Dynamic "
    "grid had overtaken Static.",

    "Momentum confirmation (deferring fills during active sell-offs) lowers "
    "return but improves tail risk (CVaR ~31% better) - only 'wins' if you "
    "judge on a risk-weighted score chosen before the experiment, not on "
    "raw return.",
]
