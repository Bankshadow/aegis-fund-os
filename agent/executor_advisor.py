"""Executor-Advisor loop — Advisor Inversion (Avid BUILD 5).

Architecture:

    ┌──────────────────┐  consult_advisor (≤3)   ┌──────────────────┐
    │  EXECUTOR/driver │ ──────────────────────► │     ADVISOR      │
    │  Sonnet 5 / Sol  │ ◄────────────────────── │     Fable 5      │
    │  (every turn)    │     judgment grams       │   (on-demand)    │
    └────────┬─────────┘                          └──────────────────┘
             └── loops until done OR stuck-protocol abort

Cheap model owns the loop. Frontier model is consulted only when the harness
(or the driver) detects a stuck signal — never for bulk typing.

Stuck signals (behavioral, not self-report):
  - same failure signature twice
  - explicit uncertainty between ≥2 approaches with material risk
  - promote / kill / ValidationGate judgment calls

Usage:
    python agent/executor_advisor.py "โจทย์..."
    python agent/executor_advisor.py --driver sol "..."
    set EXECUTOR_MODEL=gpt-5.6-sol   # optional OpenAI driver (needs OPENAI_API_KEY)

Requires ANTHROPIC_API_KEY. OpenAI key only if driver=sol.
"""

from __future__ import annotations

import argparse
import os
import sys

import anthropic

EXECUTOR_MODEL = os.environ.get("EXECUTOR_MODEL", "claude-sonnet-5")
ADVISOR_MODEL = os.environ.get("ADVISOR_MODEL", "claude-fable-5")
ADVISOR_FALLBACK = "claude-opus-4-8"
MAX_TURNS = 20
MAX_CONSULTS = 3

EXECUTOR_SYSTEM = """\
You are the EXECUTOR (driver) in an Advisor-Inversion loop for a quantitative
trading research team on the Dynamic Grid system (`dynamic_grid/`).

You own the task end-to-end. A frontier ADVISOR is available via
`consult_advisor`, but consults are capped and expensive.

Consult ONLY when:
- strategic judgment: risk/return trade-off, promote vs kill, experiment design
- you failed the same way twice and need a different approach
- ValidationGate / held-out / overfitting uncertainty with material downside

Do NOT consult for arithmetic, formatting, summarizing known numbers, or
routine coding you can do confidently.

When you consult, send a self-contained brief (numbers + context). The advisor
cannot see this conversation. After advice, YOU decide and act.

Project laws (never violate):
- no live orders / no third-party capital
- do not lower ValidationGate criteria
- synthetic ≠ real evidence; ≥3 seeds; criteria before run
- done = passing check / gate, never your opinion of yourself

Final answer in Thai, conclusion first."""

ADVISOR_SYSTEM = """\
You are the ADVISOR: a senior quantitative strategist consulted by a cheap
driver agent on a Dynamic Grid Trading system. One self-contained question
per call. Be decisive: recommendation first, then reasoning, then the one
risk to watch. Rigorous on overfitting, sample size, held-out validity.
Under 400 words. You do not write code or run tools."""

CONSULT_TOOL = {
    "name": "consult_advisor",
    "description": (
        "Consult frontier strategist (Fable 5) for judgment grams only. "
        "Cap enforced by harness. Self-contained question required."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Self-contained question with all numbers/context",
            },
            "stuck_signal": {
                "type": "string",
                "enum": [
                    "repeated_failure",
                    "material_tradeoff",
                    "promotion_gate",
                    "other",
                ],
                "description": "Why the harness should spend a consult",
            },
        },
        "required": ["question", "stuck_signal"],
    },
}


def ask_advisor(client: anthropic.Anthropic, question: str) -> str:
    response = client.beta.messages.create(
        model=ADVISOR_MODEL,
        max_tokens=4096,
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": ADVISOR_FALLBACK}],
        system=ADVISOR_SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    if response.stop_reason == "refusal":
        return ("[advisor declined — proceed with best judgment and "
                "note uncertainty; fallback chain may have engaged]")
    return "".join(b.text for b in response.content if b.type == "text")


def run(task: str, *, executor_model: str = EXECUTOR_MODEL) -> str:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": task}]
    final_text = ""
    consults = 0

    print(f"=== Driver ({executor_model}) + Advisor ({ADVISOR_MODEL}) "
          f"consult_cap={MAX_CONSULTS} ===")

    for turn in range(1, MAX_TURNS + 1):
        response = client.messages.create(
            model=executor_model,
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=EXECUTOR_SYSTEM,
            tools=[CONSULT_TOOL],
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n[executor:{turn}] {block.text}")
                final_text = block.text

        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use" or block.name != "consult_advisor":
                continue
            if consults >= MAX_CONSULTS:
                advice = (
                    f"[harness] consult cap {MAX_CONSULTS} reached — "
                    "decide with available evidence; do not consult again"
                )
                print(f"\n[stuck-protocol] CAP consults={consults}")
            else:
                q = block.input["question"]
                signal = block.input.get("stuck_signal", "other")
                print(f"\n[-> advisor signal={signal}] "
                      f"{q[:200]}{'...' if len(q) > 200 else ''}")
                advice = ask_advisor(client, q)
                consults += 1
                print(f"[<- advisor {consults}/{MAX_CONSULTS}] "
                      f"{advice[:300]}{'...' if len(advice) > 300 else ''}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": advice,
            })
        messages.append({"role": "user", "content": tool_results})

    print(f"\n[stats] turns≤{MAX_TURNS} consults={consults}/{MAX_CONSULTS}")
    return final_text


DEMO_TASK = """\
ประเมินผลระบบ Dynamic Grid จากผล held-out (อ้างอิง HANDOFF E21–E23):

E21 dual_pct promotion: FAIL — เลือก cash
E22 dual vs cash: PASS วินิจฉัย — negative_edge_trading
E23 dual tune: FAIL — ดีขึ้น (+0.03) แต่ mean robust ยังติดลบ / ไม่ promote

คำถาม: งานถัดไปที่คุ้มที่สุดเพื่อดัน dual robust > 0 ภายใต้ต้นทุนจริง โดยไม่ลด
ValidationGate คืออะไร — ปรึกษา advisor ถ้าติด trade-off แล้วสรุปแผน 3 ข้อ"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", default=None)
    ap.add_argument("--driver", choices=("sonnet", "sol"), default="sonnet",
                    help="sonnet=claude-sonnet-5; sol needs OpenAI wiring later")
    args = ap.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1

    model = EXECUTOR_MODEL
    if args.driver == "sol":
        # Sol driver via Anthropic-compatible proxy is optional; default stays Sonnet
        # until OPENAI path is wired. Document intent, don't silently bill wrong seat.
        model = os.environ.get("SOL_EXECUTOR_MODEL", "claude-sonnet-5")
        print("[note] --driver sol: set SOL_EXECUTOR_MODEL to proxied Sol id; "
              "falling back to Sonnet unless env set", file=sys.stderr)

    task = args.task or DEMO_TASK
    run(task, executor_model=model)
    print("\n=== DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
