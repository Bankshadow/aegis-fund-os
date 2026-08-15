"""E37 - BTC EMA9/21 + RSI Momentum (5x) with DSL exits, dedup and risk halts.

Criteria declared in `docs/E37_CRITERIA.md` BEFORE the engine was written. Run:

    python e37_dsl.py
    python -m unittest tests.test_dsl_runtime

Read-only backtest. No order path, no promotion, no live trading.
"""

import json
import os

import numpy as np

from dynamic_grid import dsl_runtime as dsl

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "dsl-momentum-e37.json")

INITIAL = 5_000.0
WARMUP = 60
BARS_PER_YEAR = 6 * 365.25
CLAIM = {"trades": 73, "win_rate": 0.78, "roi": 1.53, "profit_factor": 1.45, "max_dd": 0.67}

WINDOWS = (
    ("W1_2024-07_2026-08", "BTCUSDT_4h_2y.json", "BTCUSDT_funding_2y.json"),
    ("W2_2022-06_2024-07", "BTCUSDT_4h_prev2y.json", None),
)


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


def load(price_file, funding_file):
    with open(os.path.join(ROOT, "data", price_file), encoding="utf-8") as fh:
        bars = json.load(fh)
    opens = np.array([int(b[0]) for b in bars])
    close = np.array([float(b[4]) for b in bars])
    high = np.array([float(b[2]) for b in bars])
    low = np.array([float(b[3]) for b in bars])
    funding = np.zeros(len(bars))
    if funding_file:
        with open(os.path.join(ROOT, "data", funding_file), encoding="utf-8") as fh:
            rows = json.load(fh)
        step = 4 * 3600 * 1000
        index = {t: i for i, t in enumerate(opens)}
        for row in rows:
            i = index.get((int(row["fundingTime"]) // step) * step)
            if i is not None:
                funding[i] += float(row["fundingRate"])
    return close, high, low, funding


def buy_hold(close):
    curve = INITIAL * close[WARMUP:] / close[WARMUP]
    peak = np.maximum.accumulate(curve)
    dd = float(((peak - curve) / peak).max())
    ret = float(curve[-1] / INITIAL - 1.0)
    return {"total_return": ret, "max_dd": dd, "robust": ret - 2 * dd}


def summarise(result, label):
    s = result.stats()
    years = len(result.equity) / BARS_PER_YEAR
    return {
        "label": label,
        "trades": s["trades"], "win_rate": s["win_rate"],
        "profit_factor": s["profit_factor"],
        "avg_win": s["avg_win"], "avg_loss": s["avg_loss"],
        "exit_reasons": s["exit_reasons"],
        "total_return": result.total_return, "max_dd": result.max_drawdown,
        "robust": result.robust, "final_equity": float(result.equity[-1]),
        "liquidations": result.liquidations, "ruined": result.ruined,
        "halted_at": result.halted_at, "daily_stops": result.daily_stops,
        "funding_paid": result.funding_paid,
        "trades_per_month": s["trades"] / (years * 12) if years else 0.0,
    }


def show(rows, title):
    head(title)
    print(f"  {'variant':<30}{'trades':>8}{'win%':>8}{'PF':>7}{'ROI':>10}"
          f"{'maxDD':>9}{'robust':>9}{'liq':>5}{'halt':>7}{'t/mo':>7}")
    for r in rows:
        pf = f"{r['profit_factor']:.2f}" if r["profit_factor"] else "  n/a"
        halt = "yes" if r["halted_at"] >= 0 else "no"
        print(f"  {r['label']:<30}{r['trades']:>8}{pct(r['win_rate'])}{pf:>7}"
              f"{pct(r['total_return'])}{pct(r['max_dd'])}{r['robust']:>9.2f}"
              f"{r['liquidations']:>5}{halt:>7}{r['trades_per_month']:>7.1f}")


def main():
    head("E37 - EMA9/21 + RSI 45/55 @5x with DSL exits | criteria docs/E37_CRITERIA.md")
    print("  spec: 1 slot, signal dedup, SL 3xATR, profit ladder 10/35/100% ROE,")
    print("        drawdown_halt 25%, daily_loss_limit 8%, 4h cadence")

    report = {}
    for name, price_file, funding_file in WINDOWS:
        close, high, low, funding = load(price_file, funding_file)
        bh = buy_hold(close)
        base = dsl.run(close, high, low, funding, warmup=WARMUP, initial=INITIAL)

        variants = [summarise(base, "as declared (5x, RSI on)")]
        variants.append(summarise(
            dsl.run(close, high, low, funding, warmup=WARMUP, initial=INITIAL,
                    use_rsi=False), "control: RSI off (P4)"))
        variants.append(summarise(
            dsl.run(close, high, low, funding, warmup=WARMUP, initial=INITIAL,
                    leverage=1.0), "control: 1x (P5)"))
        variants.append(summarise(
            dsl.run(close, high, low, funding, warmup=WARMUP, initial=INITIAL,
                    halt_is_permanent=False), "robustness: halt resumes"))

        show(variants, f"{name}  |  buy&hold ROI {pct(bh['total_return'])} "
                       f"maxDD {pct(bh['max_dd'])} robust {bh['robust']:.2f}")
        print(f"\n  exit reasons (as declared): {variants[0]['exit_reasons']}")
        print(f"  daily-loss stops: {variants[0]['daily_stops']}   "
              f"halted at bar: {variants[0]['halted_at']}")

        # --- two diagnostics that decide how to read the headline number ----
        gated = int(np.count_nonzero(dsl.signals(close, use_rsi=True)))
        ungated = int(np.count_nonzero(dsl.signals(close, use_rsi=False)))
        print(f"  RSI 45/55 rejected {ungated - gated} of {ungated} signals "
              f"-> the band never binds")

        halt_bar = variants[0]["halted_at"]
        curve = np.concatenate(([INITIAL], dsl.run(close, high, low, funding,
                                                   warmup=WARMUP, initial=INITIAL).equity))
        traded = max(halt_bar - WARMUP, 0)
        print(f"  peak equity {curve.max() / INITIAL - 1:+.0%} -> frozen at "
              f"{variants[0]['total_return']:+.0%}; traded {traded} of "
              f"{len(close) - WARMUP} bars ({traded / (len(close) - WARMUP):.0%} of the window)")

        diagnostics = {"rsi_rejected": ungated - gated, "rsi_signals": ungated,
                       "peak_before_halt": float(curve.max() / INITIAL - 1.0),
                       "bars_traded": traded, "bars_total": len(close) - WARMUP}
        report[name] = {"buy_hold": bh, "variants": variants, "diagnostics": diagnostics}

    # ---- criteria ---------------------------------------------------------
    head("Criteria")
    w1 = report["W1_2024-07_2026-08"]
    ref = w1["variants"][0]
    p1_trades = abs(ref["trades"] - CLAIM["trades"]) <= 0.40 * CLAIM["trades"]
    p1_wr = abs(ref["win_rate"] - CLAIM["win_rate"]) <= 0.15
    p1 = p1_trades and p1_wr
    print(f"  P1 reproduce (W1): trades {ref['trades']} vs {CLAIM['trades']} "
          f"({tick(p1_trades)}), win {ref['win_rate']*100:.0f}% vs 78% ({tick(p1_wr)})"
          f"  -> {tick(p1)}")

    checks = {}
    for name, block in report.items():
        declared, rsi_off, one_x = block["variants"][0], block["variants"][1], block["variants"][2]
        c = {
            "P2": declared["robust"] > 0,
            "P3": declared["robust"] > block["buy_hold"]["robust"],
            "P4": declared["robust"] > rsi_off["robust"],
            "P5": declared["robust"] > one_x["robust"],
            "P6": declared["liquidations"] == 0 and not declared["ruined"],
        }
        checks[name] = c
        print(f"  {name}: " + "  ".join(f"{k} {tick(v)}" for k, v in c.items()))

    passed = all(all(c.values()) for c in checks.values())
    print(f"\n  P2-P6 on both windows: {tick(passed)}")
    if not passed:
        print("  P7 not evaluated: held-out stays untouched (section 7).")

    # source table's own bar
    head("Layer 1 - the source table's own criteria, on the declared variant")
    for name, block in report.items():
        d = block["variants"][0]
        t = {"T1 >=25 trades": d["trades"] >= 25, "T2 win >55%": d["win_rate"] > 0.55,
             "T3 profit": d["total_return"] > 0, "T4 DD<100%": d["max_dd"] < 1.0}
        print(f"  {name}: " + "  ".join(f"{k} {tick(v)}" for k, v in t.items())
              + f"   all {tick(all(t.values()))}")

    payload = {"experiment": "E37", "criteria": "docs/E37_CRITERIA.md",
               "claim": CLAIM,
               "config": {"initial": INITIAL, "warmup": WARMUP,
                          "cost_per_side": dsl.PERP_COST,
                          "ladder": dsl.PROFIT_LADDER, "atr_mult": 3.0},
               "windows": report, "P1": p1, "checks": checks,
               "verdict": "PASS" if passed else "FAIL"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
