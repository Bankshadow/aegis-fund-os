# Loop Engineering for Dynamic Grid Research

## Purpose

Use an AI-assisted loop to improve the quality and speed of strategy research,
not to let an agent continuously retune a production bot. The system optimizes
for survival and robustness under real costs. It never sends live orders and
never promotes its own result beyond an independent paper-review boundary.

## Source concepts and project adaptation

The referenced Loop Engineering material describes three cooperating parts:
Memory, an Agent Harness, and a Learning Loop. It emphasizes tactical parameter
adjustment, drawdown control, out-of-sample evaluation, and weekly maintenance.

For this repository the safe translation is:

| Source concept | Implementation here |
|---|---|
| Memory | Append-only experiment contract, result, failure reason, and validation log |
| Agent Harness | `loop/PROMPT.md`, bounded ticks, advisor cap, deterministic gate |
| Learning Loop | Propose → preregister → run → validate → distill → kill/revise/paper-review |
| Survival | Robust score = return − 2×max drawdown, including engaged periods and real costs |
| Tactical adjustment | Offline candidate generation only; no in-production retuning |
| Weekly maintenance | Drift detection may open a research task, but cannot change parameters |

## Two-loop design

### Inner loop: experiment execution

1. Propose one falsifiable hypothesis.
2. Write an `ExperimentContract` before seeing results.
3. Compare a small candidate set against cash and the incumbent under one
   execution profile.
4. Use named real-market datasets, a declared held-out split, at least three
   distinct seeds, purging/embargo where appropriate, and a bounded trial cap.
5. Let `ValidationGate` and `deterministic_verdict` issue `kill`, `revise`, or
   `paper_review`.
6. Append negative and positive evidence to `docs/VALIDATION_LOG.md`.

### Outer loop: improve the research process

After repeated failures, change the hypothesis, data quality, cost model, or
validation design. Do not weaken the gate or keep sweeping the same parameter
geometry. Any change to the score, split, benchmark, or threshold is a new
contract and must be justified before execution.

## State machine

```text
DRAFT -> PREREGISTERED -> RUNNING -> VALIDATED -> KILL
                                      |         -> REVISE -> DRAFT
                                      `--------> PAPER_REVIEW
```

There is deliberately no `LIVE` state. Paper eligibility requires an
independent reviewer, and controlled-live readiness remains governed by the
private-fund roadmap and repository constitution.

Independent paper decisions are persisted separately in `PaperReviewLedger`.
Only an experiment whose deterministic verdict is `paper_review` can be
reviewed; its declared maker cannot be the reviewer. A final decision is either
`approved_for_paper` or `rejected`, is bound to the experiment record hash and
is stored in its own verified append-only hash chain. There is no live decision.
The Loop snapshot verifies and projects this review chain, including maker,
reviewer, rationale and final paper decision. Aegis validates the same binding
and renders it read-only in Strategy Lab.

## Memory record

Every loop run should preserve:

- experiment ID, hypothesis, parent experiment, and code/data fingerprints;
- candidate and benchmark names;
- dataset/timeframe, split, purge/embargo, seeds, and trial budget;
- fee, spread, slippage, funding, liquidity, and liquidation assumptions;
- full fold results and robust scores, including non-engaged runs;
- deterministic verdict and failure reasons;
- human/reviewer decision for any paper promotion.

The memory is evidence, not a parameter cache. A failed configuration must not
be silently retried under a new label, and a configuration may not transfer to
another scale or timeframe without a new held-out contract.

## Initial delivery sequence

1. Contract and deterministic verdict — implemented in
   `dynamic_grid/loop_engineering.py`.
2. JSONL append-only storage with code and dataset hashes — implemented as
   `ExperimentMemory`; records form a verified SHA-256 chain and duplicate
   experiment IDs are rejected.
3. One-contract runner — implemented as `OneContractResearchRunner`; it
   validates the dataset mapping, fingerprints code/data before evaluation,
   enforces the declared trial budget, verifies inputs again after evaluation,
   and appends one result plus deterministic verdict to experiment memory.
4. Drift monitoring — implemented as `DriftMonitor` plus
   `DriftResearchQueue`; declared thresholds can emit immutable research-task
   drafts, while insufficient samples and cross-dataset comparisons fail
   closed. The API exposes no strategy parameters or execution operation.
5. Read-only lineage exporter — implemented in `dynamic_grid/loop_snapshot.py`;
   it verifies experiment memory, projects newest-first experiments, verdicts,
   failure reasons and drift tasks, includes source hashes, advertises no-write
   capabilities, and writes versioned JSON atomically. Next, bind this snapshot
   to an Aegis server-only reader and UI. The server-only reader is now
   implemented in `loop-lineage.functions.ts`: it accepts only server
   environment JSON/path input, validates the versioned no-write schema and
   returns an explicit unconfigured fallback. Strategy Lab now consumes that
   reader and shows verified lineage, verdict/failure counts, hashes and drift
   tasks with explicit loading, fallback and validation-failure states. Static
   registry data remains labelled as demo metadata and there is no write or
   parameter-control action in the lineage UI. A read-only CLI is available as
   `python -m dynamic_grid.loop_cli`; it requires explicit experiment-memory,
   drift-queue, review-ledger and output paths, verifies every source before
   atomically replacing the output, and exposes no approval, parameter mutation
   or order operation.

## First suitable experiment

Do not resume broad geometry search after E23–E25. The next contract should test
one genuinely new mechanism (for example a preregistered funding/relative
filter or a volatility pause) against cash and the E23 incumbent. It must use
real L1 spread estimates, time-varying funding, multiple held-out windows and at
least three seeds. Promotion requires positive mean robust score and every
declared validation report to pass unchanged gates.
