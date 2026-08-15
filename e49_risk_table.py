"""E49 - what risk per trade is actually usable, with drawdown as a distribution.

Criteria declared in `docs/E49_CRITERIA.md` BEFORE this file existed. Run:

    python e49_risk_table.py

Every drawdown figure quoted so far - 72.1%, 62.5%, 50.9% - comes from the one
trade sequence history happened to deal. This measures the spread around it by
resampling blocks of ten consecutive trades, so loss clustering survives the
resampling. Nothing is tuned and nothing is selected: the output is a table that
maps a drawdown tolerance to a risk level by a rule fixed in advance.
"""

import json
import os

import numpy as np

from e47_sizing_overlay import build, cagr, INITIAL, IS_FROM, SPLIT, OOS_TO
from e48_v4_adversarial import run

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "risk-table-e49.json")

LEVELS = (0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10)
BLOCK, RESAMPLES = 10, 500
TOLERANCES = (0.20, 0.30, 0.40, 0.50)
RUIN_DD = 0.80
E49_HARNESS = {"dd": 0.721, "cagr": 0.372}


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def block_orders(n, rng):
    """Moving-block bootstrap indices: blocks of BLOCK consecutive trades."""
    out = []
    while len(out) < n:
        s = rng.integers(0, max(1, n - BLOCK + 1))
        out.extend(range(s, min(s + BLOCK, n)))
    return np.array(out[:n])


def main():
    head("E49 - risk per trade as a distribution | criteria docs/E49_CRITERIA.md")
    trades = build()
    n_full = len([t for t in trades if IS_FROM <= t.entry_date < OOS_TO])
    print(f"  {n_full} trades, {IS_FROM} -> {OOS_TO}")
    print(f"  moving-block bootstrap: block={BLOCK} trades, {RESAMPLES} resamples/level")

    # ---- X1 harness ------------------------------------------------------
    f6, dd6, _ = run(trades, 0.06, "flat", IS_FROM, OOS_TO)
    c6 = cagr(f6, trades, IS_FROM, OOS_TO)
    x1 = (abs(dd6 - E49_HARNESS["dd"]) <= 0.005
          and abs(c6 - E49_HARNESS["cagr"]) <= 0.005)
    print(f"\n  X1 harness: 6% flat -> DD {dd6:.1%} / CAGR {c6:+.1%}  "
          f"-> {'PASS' if x1 else 'FAIL'}")
    if not x1:
        print("  STOP per criteria section 4.")
        return 1

    rows = {}
    for risk in LEVELS:
        fi, ddi, _ = run(trades, risk, "flat", IS_FROM, SPLIT)
        fo, ddo, _ = run(trades, risk, "flat", SPLIT, OOS_TO)
        ff, ddf, _ = run(trades, risk, "flat", IS_FROM, OOS_TO)

        # sequential reference: same path model the bootstrap uses (no overlap)
        seq_f, seq_dd, _ = run(trades, risk, "flat", IS_FROM, OOS_TO,
                               order=np.arange(n_full))

        dds, finals = [], []
        for s in range(RESAMPLES):
            rng = np.random.default_rng(5000 + s)
            f, dd, _ = run(trades, risk, "flat", IS_FROM, OOS_TO,
                           order=block_orders(n_full, rng))
            dds.append(dd)
            finals.append(f)
        dds = np.array(dds)

        rows[f"{risk:.3f}"] = {
            "risk": risk,
            "IS": {"cagr": cagr(fi, trades, IS_FROM, SPLIT), "maxDD": ddi},
            "OOS": {"cagr": cagr(fo, trades, SPLIT, OOS_TO), "maxDD": ddo},
            "full": {"cagr": cagr(ff, trades, IS_FROM, OOS_TO), "maxDD": ddf,
                     "final": ff},
            "sequential_ref": {"maxDD": seq_dd, "final": seq_f},
            "bootstrap": {
                "dd_median": float(np.median(dds)),
                "dd_p90": float(np.percentile(dds, 90)),
                "dd_p95": float(np.percentile(dds, 95)),
                "dd_max": float(dds.max()),
                "real_percentile": float((dds < seq_dd).mean() * 100),
                "ruin_share": float((dds > RUIN_DD).mean()),
                "median_final": float(np.median(finals)),
            },
            "dd_inflation_is_to_oos": (ddo / ddi) if ddi > 0 else float("nan"),
        }

    head("X2 - realised path, all nine levels, all three windows")
    print(f"  {'risk':>6}{'IS CAGR':>10}{'IS DD':>8}{'OOS CAGR':>11}{'OOS DD':>9}"
          f"{'full CAGR':>11}{'full DD':>10}{'X5 DD x':>9}")
    for r in rows.values():
        print(f"  {r['risk'] * 100:>5.1f}%{r['IS']['cagr']:>+10.1%}{r['IS']['maxDD']:>8.1%}"
              f"{r['OOS']['cagr']:>+11.1%}{r['OOS']['maxDD']:>9.1%}"
              f"{r['full']['cagr']:>+11.1%}{r['full']['maxDD']:>10.1%}"
              f"{r['dd_inflation_is_to_oos']:>9.2f}")

    head(f"X3/X4/X6 - drawdown distribution, {RESAMPLES} block-bootstrap paths")
    print(f"  {'risk':>6}{'real(seq)':>11}{'median':>9}{'p90':>8}{'p95':>8}{'worst':>8}"
          f"{'real pctile':>13}{'DD>80%':>9}")
    for r in rows.values():
        b = r["bootstrap"]
        print(f"  {r['risk'] * 100:>5.1f}%{r['sequential_ref']['maxDD']:>11.1%}"
              f"{b['dd_median']:>9.1%}{b['dd_p90']:>8.1%}{b['dd_p95']:>8.1%}"
              f"{b['dd_max']:>8.1%}{b['real_percentile']:>12.0f}%"
              f"{b['ruin_share']:>9.1%}")

    head("The declared rule: highest risk level whose bootstrap p90 DD <= tolerance")
    mapping = {}
    for tol in TOLERANCES:
        ok = [r for r in rows.values() if r["bootstrap"]["dd_p90"] <= tol]
        if ok:
            best = max(ok, key=lambda r: r["risk"])
            mapping[f"{tol:.2f}"] = best["risk"]
            grow = best["full"]["final"] / INITIAL
            print(f"  tolerance {tol:.0%}  ->  risk {best['risk'] * 100:.1f}%/trade   "
                  f"full-history CAGR {best['full']['cagr']:+.1%}, "
                  f"$10k -> {best['full']['final']:,.0f} ({grow:.1f}x over 8.2y)")
        else:
            mapping[f"{tol:.2f}"] = None
            print(f"  tolerance {tol:.0%}  ->  NO LEVEL QUALIFIES "
                  f"(lowest p90 DD = {min(r['bootstrap']['dd_p90'] for r in rows.values()):.1%} "
                  f"at {LEVELS[0] * 100:.1f}%)")

    head("Warnings the criteria require to be stated with the table")
    lo = rows[f"{LEVELS[0]:.3f}"]["bootstrap"]
    print(f"  - the bootstrap resamples the PAST only; a regime never seen is not in it")
    print(f"  - bootstrap paths run one trade at a time (no overlap), so compare them to"
          f" 'real(seq)', not to the overlapped realised DD")
    below = [r["risk"] for r in rows.values()
             if r["sequential_ref"]["maxDD"] < r["bootstrap"]["dd_median"]]
    if below:
        print(f"  - history was KIND at {len(below)}/{len(rows)} levels: the realised path's"
              f" DD sits below the bootstrap median")
    print(f"  - even at {LEVELS[0] * 100:.1f}%/trade the worst bootstrap path drew down "
          f"{lo['dd_max']:.1%}")

    payload = {"experiment": "E49", "criteria": "docs/E49_CRITERIA.md",
               "block": BLOCK, "resamples": RESAMPLES, "trades": n_full,
               "X1_harness": x1, "levels": rows,
               "tolerance_to_risk": mapping,
               "note": "measurement only - no tuning, no selection, no promotion"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
