# Stuck protocol (Advisor Inversion)

The **harness** decides when the driver is stuck — not the driver's self-esteem.

## Fire a Fable consult when

1. Same failure signature twice (same error / same rejected approach)
2. Material trade-off (risk vs return, promote vs cash, gate vs research speed)
3. Promotion / ValidationGate / overfitting judgment with downside

## Do not fire when

- Formatting, renames, routine tests, summarizing known metrics
- First attempt at a clear coding task

## Caps

- ≤ **3** consults per task (`MAX_CONSULTS` in `agent/executor_advisor.py`)
- Brief stays tiny — long briefs poison the expert

## After consult

Driver acts. Advisor never takes the keyboard.
