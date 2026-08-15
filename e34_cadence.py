"""E34 - does lowering the decision frequency rescue the trend edge on BTC?

Criteria declared in `docs/E34_CRITERIA.md` BEFORE this file existed. Run:

    python e34_cadence.py
    python -m unittest tests.test_cadence

Read-only backtest. Long-only spot, no leverage, no short, no order path.
"""

import json
import os

import numpy as np

from dynamic_grid import cadence as cd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "btc-cadence-e34.json")

WARMUP = 252
OOS = 252
IS = 504
INITIAL = 10_000.0


def load_closes(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as handle:
        raw = json.load(handle)
    return np.array([float(bar[4]) for bar in raw]), [int(bar[0]) for bar in raw]


def head(title):
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


def pct(x, nd=1):
    return f"{x * 100:>8.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


# ---------------------------------------------------------------------------
# P1 - the mechanism premise, measured BEFORE any return is read (§2.1)
# ---------------------------------------------------------------------------

def precondition(close):
    state = cd.sma_state(close, 200)
    live = state[~np.isnan(state)]
    flips = int(np.count_nonzero(np.diff(live) != 0.0))
    years = len(live) / cd.TRADING_DAYS
    per_year = flips / years

    monthly = cd.sampled(state, 21, close)
    daily = cd.sampled(state, 1, close)
    both = ~np.isnan(state)
    agreement = float(np.mean(monthly[both] == daily[both]))

    return {
        "flips_total": flips,
        "years": years,
        "flips_per_year": per_year,
        "P1a_pass": per_year <= 12.0,
        "monthly_daily_agreement": agreement,
        "P1b_pass": agreement >= 0.85,
    }


# ---------------------------------------------------------------------------
# walk-forward
# ---------------------------------------------------------------------------

def windows(n, warmup=WARMUP, size=OOS):
    out, start = [], warmup
    while start + size <= n:
        out.append((start, start + size))
        start += size
    return out


def run_window(close, lo, hi, mix_fraction):
    """Every candidate over one OOS window, signal warm-started from bar 0."""
    specs = cd.targets(close, mix_fraction)
    return {name: cd.metrics(cd.run_segment(close, spec, lo, hi, INITIAL))
            for name, spec in specs.items()}


def realised_exposure(close):
    """C2's average exposure - the fraction C4 is matched to (§5)."""
    state = cd.sma_state(close, 200)
    run = cd.simulate(close, state, 21, initial=INITIAL)
    return float(np.mean(run["weights"][WARMUP:]))


def evaluate(close, label):
    mix = realised_exposure(close)
    folds = windows(len(close))
    per_candidate = {}
    for lo, hi in folds:
        for name, m in run_window(close, lo, hi, mix).items():
            per_candidate.setdefault(name, []).append(m)

    summary = {}
    bh = per_candidate["C0_buy_hold"]
    for name, rows in per_candidate.items():
        robust = [r["robust"] for r in rows]
        beats = sum(1 for r, b in zip(rows, bh) if r["robust"] > b["robust"])
        summary[name] = {
            "mean_robust": float(np.mean(robust)),
            "median_robust": float(np.median(robust)),
            "mean_return": float(np.mean([r["total_return"] for r in rows])),
            "mean_max_dd": float(np.mean([r["max_dd"] for r in rows])),
            "mean_exposure": float(np.mean([r["exposure"] for r in rows])),
            "trades_per_year": float(np.mean([r["trades_per_year"] for r in rows])),
            "beats_bh_windows": beats,
            "windows": len(rows),
        }
    return {"label": label, "mix_fraction": mix, "folds": len(folds),
            "summary": summary, "per_window": per_candidate}


def selection_value(close, mix):
    """K7 - is picking the in-sample winner worth anything out of sample?"""
    picks, n = [], len(close)
    start = WARMUP
    while start + IS + OOS <= n:
        is_lo, is_hi = start, start + IS
        oos_lo, oos_hi = is_hi, is_hi + OOS
        in_sample = run_window(close, is_lo, is_hi, mix)
        out_sample = run_window(close, oos_lo, oos_hi, mix)
        best = max(in_sample, key=lambda k: in_sample[k]["robust"])
        scores = [m["robust"] for m in out_sample.values()]
        picks.append({
            "picked": best,
            "oos_robust": out_sample[best]["robust"],
            "oos_average": float(np.mean(scores)),
            "beat_average": out_sample[best]["robust"] > float(np.mean(scores)),
            "was_best": out_sample[best]["robust"] == max(scores),
        })
        start += OOS
    return {
        "folds": len(picks),
        "beat_average_rate": float(np.mean([p["beat_average"] for p in picks])) if picks else 0.0,
        "was_best_rate": float(np.mean([p["was_best"] for p in picks])) if picks else 0.0,
        "chance_rate": 1.0 / 6.0,
        "picks": picks,
    }


def continuous(close, mix):
    """Descriptive - the plain question: what does 10,000 become on one path?"""
    specs = cd.targets(close, mix)
    return {name: cd.metrics(cd.run_segment(close, spec, WARMUP, len(close), INITIAL))
            for name, spec in specs.items()}


def main():
    close, _ = load_closes("btc_daily_full.json")
    head(f"E34 - BTC cadence | {len(close)} daily bars | criteria docs/E34_CRITERIA.md")

    # --- P1 first, before any return is read -------------------------------
    head("P1 - mechanism premise (measured BEFORE returns)")
    p1 = precondition(close)
    print(f"  SMA-200 state flips     {p1['flips_total']} over {p1['years']:.1f}y "
          f"= {p1['flips_per_year']:.2f}/year   P1a (<=12/y) {tick(p1['P1a_pass'])}")
    print(f"  monthly vs daily agree  {pct(p1['monthly_daily_agreement'], 2)}"
          f"                        P1b (>=85%) {tick(p1['P1b_pass'])}")
    if not (p1["P1a_pass"] and p1["P1b_pass"]):
        print("\n  P1 FAILED - the premise is wrong. Reporting and stopping per section 7.")
        json.dump({"experiment": "E34", "p1": p1, "stopped_at": "P1"},
                  open(OUT, "w", encoding="utf-8"), indent=1)
        return 1

    # --- BTC walk-forward ---------------------------------------------------
    btc = evaluate(close, "BTC")
    head(f"BTC - {btc['folds']} non-overlapping OOS windows "
         f"(C4 matched to C2 exposure {btc['mix_fraction']:.3f})")
    print(f"  {'candidate':<28}{'meanRobust':>12}{'meanRet':>10}{'meanDD':>9}"
          f"{'expo':>7}{'trd/y':>8}{'beatBH':>8}")
    for name, s in btc["summary"].items():
        print(f"  {name:<28}{s['mean_robust']:>11.3f} {pct(s['mean_return'])}"
              f"{pct(s['mean_max_dd'])}{s['mean_exposure']:>7.2f}"
              f"{s['trades_per_year']:>8.1f}{s['beats_bh_windows']:>5}/{s['windows']}")

    # --- criteria -----------------------------------------------------------
    bh = btc["summary"]["C0_buy_hold"]
    c4 = btc["summary"]["C4_constant_mix_monthly"]
    head("K1-K4, K6 on BTC")
    verdicts = {}
    contenders = [n for n in btc["summary"] if n != "C0_buy_hold"]
    print(f"  {'candidate':<28}{'K1>0':>7}{'K2>=7':>8}{'K3<BH':>8}{'K4<=12':>9}{'K6>C4':>8}")
    for name in contenders:
        s = btc["summary"][name]
        k = {
            "K1": s["mean_robust"] > 0,
            "K2": s["beats_bh_windows"] >= 7,
            "K3": s["mean_max_dd"] < bh["mean_max_dd"],
            "K4": s["trades_per_year"] <= 12.0,
            "K6": s["mean_robust"] > c4["mean_robust"],
        }
        verdicts[name] = k
        print(f"  {name:<28}{tick(k['K1']):>7}{tick(k['K2']):>8}{tick(k['K3']):>8}"
              f"{tick(k['K4']):>9}{tick(k['K6']):>8}")

    winners = [n for n, k in verdicts.items() if all(k.values())]
    print(f"\n  candidates clearing K1-K4 + K6 on BTC: {winners or 'NONE'}")

    # --- K5 held-out, only if BTC produced a winner (§9) --------------------
    held_out = {}
    if winners:
        head("K5 - held-out (touched only because BTC produced a winner)")
        for symbol, filename in (("ETH", "ETHUSDT_1d.json"), ("SOL", "SOLUSDT_1d.json")):
            other, _ = load_closes(filename)
            held_out[symbol] = evaluate(other, symbol)
            for name in winners:
                s = held_out[symbol]["summary"][name]
                print(f"  {symbol} {name:<28} meanRobust {s['mean_robust']:>8.3f} "
                      f"{tick(s['mean_robust'] > 0)}")
    else:
        print("\n  K5 not evaluated: no BTC winner, so held-out stays untouched (section 9).")

    # --- K7 selection value -------------------------------------------------
    head("K7 - is picking the in-sample winner worth anything?")
    sel = selection_value(close, btc["mix_fraction"])
    print(f"  beat candidate average OOS: {sel['beat_average_rate'] * 100:.1f}% "
          f"over {sel['folds']} folds")
    print(f"  was actually best OOS:      {sel['was_best_rate'] * 100:.1f}% "
          f"(chance with 6 candidates = {sel['chance_rate'] * 100:.1f}%)")

    # --- §8 descriptive ------------------------------------------------------
    head("Descriptive (NOT a criterion) - one continuous path from 10,000")
    cont = continuous(close, btc["mix_fraction"])
    print(f"  {'candidate':<28}{'final':>14}{'CAGR':>10}{'maxDD':>9}{'expo':>7}")
    for name, m in cont.items():
        print(f"  {name:<28}{m['final_equity']:>14,.0f}{pct(m['cagr'])}"
              f"{pct(m['max_dd'])}{m['exposure']:>7.2f}")

    payload = {
        "experiment": "E34",
        "criteria": "docs/E34_CRITERIA.md",
        "config": {"warmup": WARMUP, "oos": OOS, "is": IS, "initial": INITIAL,
                   "cost_per_side": cd.COST_PER_SIDE},
        "p1": p1,
        "btc": btc,
        "verdicts": verdicts,
        "winners": winners,
        "held_out": held_out,
        "k7_selection_value": sel,
        "descriptive_continuous": cont,
        "run_count": len(cd.targets(close, 0.5)) * btc["folds"],
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
