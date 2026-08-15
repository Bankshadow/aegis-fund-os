---
name: code-graph-context
description: >-
  Use CodeGraphContext (CGC) as an optional local code call-graph for impact
  analysis, callers/callees, and dead-code triage. Use when the user mentions
  CodeGraphContext, CGC, code graph MCP, call chain, who calls this, impact of
  changing a function, or indexing the repo into a graph DB. Do not confuse with
  L2 agent graph contracts, L3 runtime severity graph, or Cognee trading memory.
---

# Code graph context (repo-mapped)

Upstream: [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext)
(MIT) — CLI + MCP that indexes local code into an embedded graph DB
(Kuzu / FalkorDB Lite / optional Neo4j) so agents can query callers, callees,
hierarchies, call chains, complexity, and dead code.

This skill is **when/how to use CGC here**, not a vendored install. Default
navigation stays ripgrep + Read + `commit-archaeologist` / `llm-app-pattern-router`
archaeology. Turn CGC on only when call-graph questions dominate.

## Three graphs — do not mix

| Graph | What it is | Path / tool |
|---|---|---|
| **L2 agent harness** | Review diamonds, severity routes for *agents* | `agent/graph_contracts.py`, `agent/graph_ops.py` |
| **L3 runtime** | Deterministic reconcile severity / dry-loop | `fund-command-center-local/src/lib/grid-runtime-graph.ts` |
| **Cognee / DecisionLog** | Trading *event* memory for recall | `dynamic_grid/cognee_adapter.py`, `cognee_demo.py` |
| **CGC (this skill)** | Static *source* call/import graph | Optional `codegraphcontext` CLI/MCP |

CGC never imports exchange adapters and must never be used as authority to
place, cancel, or size live orders. Firewall unchanged.

## When to use

- Impact analysis: “who calls `reconcile` / `place_order` wrapper / ValidationGate?”
- Cross-language coupling in this monorepo (Python research ↔ Fund OS TS)
- Dead-code / complexity triage before a large delete (still human + gate)
- Full call chain across many files when grep is drowning in noise

## When not to use

- Single-file edit or known path — use Read / Grep
- “Why does this code exist?” historically — `commit-archaeologist` doctrine
  (`llm-app-pattern-router` Pattern B)
- Promote/kill / ValidationGate judgment — `quant-research-pipeline`
- L2 diamond review — `python -m agent.diamonds.runtime_safety_review`
- Trading recall of past runs — Cognee / DecisionLog, not CGC

## Opt-in install (operator)

Windows-friendly path (this machine): prefer **Kuzu** embedded backend.

```powershell
pip install "codegraphcontext[kuzu]"
# or: pip install codegraphcontext kuzu
codegraphcontext --help
```

Index this repo from the workspace root (exclude junk via `.cgcignore`):

```powershell
codegraphcontext index .
codegraphcontext list
```

Useful analyses:

```powershell
codegraphcontext analyze callers <symbol>
codegraphcontext analyze dead-code
codegraphcontext analyze complexity --threshold 10
```

MCP (optional, Cursor):

```powershell
codegraphcontext mcp setup
codegraphcontext mcp start
```

Do **not** commit Neo4j passwords, `~/.codegraphcontext/.env`, or local graph
DB files into git. Prefer embedded Kuzu; Neo4j only if you already run it.

## `.cgcignore` (recommended for this repo)

If indexing, ignore heavy / generated / local junk so the graph stays useful:

```
node_modules/
fund-command-center-local/node_modules/
fund-command-center-local/.tmp-*/
**/dist/
**/.wrangler/
**/miniflare-*/
__pycache__/
.venv/
venv/
results/
*.sqlite
*.sqlite-*
.git/
```

Ask before creating the file if it does not exist; keep it local-ops unless
the user wants it committed.

## Agent workflow

1. Confirm the question is call-graph / impact (else use Grep/Read).
2. If CGC is not installed, say so and fall back — do not silently `pip install`
   into the project venv without user OK (heavy deps: tree-sitter, kuzu, etc.).
3. Prefer CLI one-shots over leaving `watch` / MCP running unattended.
4. Treat dead-code and complexity hits as **candidates**, not delete orders.
5. Before rewrite of hot paths: CGC impact + archaeology + human check
   (`agent-build-loop`), then `ship-gate`.

## Sibling skills

| Need | Skill |
|---|---|
| Catalog adopt/reject | `llm-app-pattern-router` |
| Build loop + human check | `agent-build-loop` |
| Scope of a diff | scope-creep doctrine / upstream scope-creep-detector |
| Ship | `ship-gate` |
| Model seat | `model-router` |

## Invoke

```
Use code-graph-context: impact of changing <symbol>
```

```
Use code-graph-context: should we install/index CGC for this task?
```
