"""E47 - do sizing overlays beat simply trading smaller, at the same drawdown?

Criteria declared in `docs/E47_CRITERIA.md` BEFORE this file existed. Run:

    python e47_sizing_overlay.py

Entry, stop and target logic are untouched - the spec allows a sizing overlay
only. Every arm is calibrated on IS to the same drawdown budget, so no arm can
win merely by holding less. The comparison is then read once, on OOS.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load, ASSETS, INITIAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "sizing-overlay-e47.json")

IS_FROM, SPLIT, OOS_TO = "2017-11-09", "2022-08-01", "2026-08-13"
DD_TARGET = 0.45
VOL_LOOKBACK, VOL_CLIP = 20, (0.25, 2.0)
EQ_MA = 20


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def build():
    """All closed trades, plus each trade's realised vol at entry."""
    trades = []
    for symbol in ASSETS:
        dates, o, h, l, c, _ = load(symbol)
        with np.errstate(invalid="ignore", divide="ignore"):
            rets = np.concatenate([[np.nan], np.diff(np.log(c))])
        vol = np.full(len(c), np.nan)
        for i in range(VOL_LOOKBACK, len(c)):
            w = rets[i - VOL_LOOKBACK + 1:i + 1]
            if not np.isnan(w).any():
                vol[i] = float(np.std(w, ddof=1) * np.sqrt(365))
        for t in st.run_symbol(symbol, dates, o, h, l, c).closed:
            t.entry_vol = float(vol[t.entry_bar])
            trades.append(t)
    trades.sort(key=lambda t: (t.exit_date, t.entry_date))
    return trades


def sigma_ref(trades):
    vols = [t.entry_vol for t in trades
            if IS_FROM <= t.entry_date < SPLIT and not np.isnan(t.entry_vol)]
    return float(np.median(vols))


def simulate(trades, base_risk, arm, ref, lo, hi):
    """Equity path with the arm's sizing rule. Risk is set AT ENTRY."""
    sel = [t for t in trades if lo <= t.entry_date < hi]
    if not sel:
        return INITIAL, 0.0, 0
    events = [(t.entry_date, 0, t) for t in sel] + [(t.exit_date, 1, t) for t in sel]
    events.sort(key=lambda x: (x[0], x[1]))

    cash, risked, curve = INITIAL, {}, [INITIAL]
    streak = 0                      # consecutive losing closes, portfolio level
    closed_equity = []              # equity after each close, for the MA filter

    for _, kind, t in events:
        if kind == 0:
            scale = 1.0
            if arm in ("V1", "V5") and not np.isnan(t.entry_vol) and t.entry_vol > 0:
                scale *= float(np.clip((t.entry_vol / ref) ** -0.5, *VOL_CLIP))
            if arm == "V2" and streak >= 3:
                scale *= 0.5
            if arm in ("V3", "V5") and streak >= 5:
                scale *= 0.5
            if arm == "V4" and len(closed_equity) >= EQ_MA:
                if cash < float(np.mean(closed_equity[-EQ_MA:])):
                    scale *= 0.5
            risked[id(t)] = cash * base_risk * scale
        else:
            cash += risked.pop(id(t), cash * base_risk) * t.pnl_r_net
            streak = streak + 1 if t.pnl_r_net <= 0 else 0
            closed_equity.append(cash)
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0, len(sel)

    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return cash, float(((peak - arr) / peak).max()), len(sel)


def calibrate(trades, arm, ref):
    """Binary-search base_risk so IS maxDD lands on the declared budget."""
    lo_r, hi_r = 0.001, 0.40
    for _ in range(60):
        mid = (lo_r + hi_r) / 2
        _, dd, _ = simulate(trades, mid, arm, ref, IS_FROM, SPLIT)
        if dd < DD_TARGET:
            lo_r = mid
        else:
            hi_r = mid
    return (lo_r + hi_r) / 2


def cagr(final, trades, lo, hi):
    """Compound rate over the span capital was actually deployed.

    Measured from the first entry to the last exit inside the window, not from
    the first data bar - the warm-up months hold no position and counting them
    would understate the rate. U5 caught this as a mismatch against the number
    already reported for the 6% case, and this is the definition that produced it.
    """
    sel = [t for t in trades if lo <= t.entry_date < hi]
    if not sel or final <= 0:
        return -1.0
    a = dt.date.fromisoformat(min(t.entry_date for t in sel))
    b = dt.date.fromisoformat(max(t.exit_date for t in sel))
    years = (b - a).days / 365.25
    return (final / INITIAL) ** (1 / years) - 1 if years > 0 else -1.0


def main():
    head("E47 - sizing overlays vs simply trading smaller | docs/E47_CRITERIA.md")
    trades = build()
    ref = sigma_ref(trades)
    print(f"  {len(trades)} trades | sigma_ref (IS median realised vol) = {ref:.3f}")
    print(f"  every arm calibrated on IS to maxDD ~ {DD_TARGET:.0%}, then read once on OOS")

    # U5 harness check
    _, dd6, _ = simulate(trades, 0.06, "V0", ref, IS_FROM, OOS_TO)
    f6, _, _ = simulate(trades, 0.06, "V0", ref, IS_FROM, OOS_TO)
    c6 = cagr(f6, trades, IS_FROM, OOS_TO)
    u5 = abs(dd6 - 0.721) <= 0.005 and abs(c6 - 0.372) <= 0.005
    print(f"\n  U5 harness: V0 at 6% -> DD {dd6:.1%} (want 72.1%), "
          f"CAGR {c6:+.1%} (want +37.2%)  -> {tick(u5)}")
    if not u5:
        print("  STOP per criteria section 4.")
        return 1

    arms = ("V0", "V1", "V2", "V3", "V4", "V5")
    labels = {"V0": "flat (control)", "V1": "vol-target", "V2": "breaker-3",
              "V3": "breaker-5", "V4": "equity-MA", "V5": "vol-target+breaker-5"}
    rows = {}
    for arm in arms:
        base = calibrate(trades, arm, ref)
        is_f, is_dd, is_n = simulate(trades, base, arm, ref, IS_FROM, SPLIT)
        oos_f, oos_dd, oos_n = simulate(trades, base, arm, ref, SPLIT, OOS_TO)
        rows[arm] = {"label": labels[arm], "base_risk": base,
                     "IS": {"final": is_f, "maxDD": is_dd, "trades": is_n,
                            "cagr": cagr(is_f, trades, IS_FROM, SPLIT)},
                     "OOS": {"final": oos_f, "maxDD": oos_dd, "trades": oos_n,
                             "cagr": cagr(oos_f, trades, SPLIT, OOS_TO)}}

    head("All six arms, both periods (reported in full, always)")
    print(f"  {'arm':<24}{'risk/trade':>11}{'IS CAGR':>10}{'IS DD':>8}"
          f"{'OOS CAGR':>11}{'OOS DD':>9}{'OOS $10k ->':>14}")
    for arm in arms:
        r = rows[arm]
        mark = "  <- control" if arm == "V0" else ""
        print(f"  {arm + ' ' + r['label']:<24}{r['base_risk'] * 100:>10.2f}%"
              f"{r['IS']['cagr']:>+10.1%}{r['IS']['maxDD']:>8.1%}"
              f"{r['OOS']['cagr']:>+11.1%}{r['OOS']['maxDD']:>9.1%}"
              f"{r['OOS']['final']:>14,.0f}{mark}")

    others = [a for a in arms if a != "V0"]
    picked = max(others, key=lambda a: rows[a]["IS"]["cagr"])
    v0, pick = rows["V0"]["OOS"], rows[picked]["OOS"]
    median_oos = float(np.median([rows[a]["OOS"]["cagr"] for a in others]))

    head("Declared tests")
    print(f"  picked on IS CAGR: {picked} ({rows[picked]['label']})")
    u1 = pick["cagr"] > v0["cagr"]
    u2 = pick["maxDD"] <= v0["maxDD"]
    u3 = pick["cagr"] > median_oos
    print(f"  U1 OOS CAGR  {pick['cagr']:+.1%} vs V0 {v0['cagr']:+.1%}   -> {tick(u1)}")
    print(f"  U2 OOS maxDD {pick['maxDD']:.1%} vs V0 {v0['maxDD']:.1%}   -> {tick(u2)}")
    print(f"  U3 beats overlay median OOS CAGR ({median_oos:+.1%})   -> {tick(u3)}")
    print(f"\n  U4 DD calibration transfer (IS target {DD_TARGET:.0%}):")
    for arm in arms:
        r = rows[arm]
        print(f"     {arm}  IS {r['IS']['maxDD']:.1%}  ->  OOS {r['OOS']['maxDD']:.1%}")

    worth = u1 and u2
    head(f"VERDICT: {'overlay is worth it' if worth else 'NO - just trade smaller'}"
         f"   (promotion forbidden regardless)")
    if not worth:
        print("  Per the decision table: recommend lowering risk per trade, nothing more.")

    payload = {"experiment": "E47", "criteria": "docs/E47_CRITERIA.md",
               "dd_target": DD_TARGET, "sigma_ref": ref, "arms": rows,
               "picked_on_IS": picked, "median_oos_cagr": median_oos,
               "checks": {"U1": u1, "U2": u2, "U3": u3, "U5": u5},
               "verdict": "OVERLAY_WORTH_IT" if worth else "JUST_TRADE_SMALLER",
               "run_count": len(arms) * 2}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
