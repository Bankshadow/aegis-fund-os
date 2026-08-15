"""E45 - S003 on the full available history, including years the designer never saw.

Criteria declared in `docs/E45_CRITERIA.md` BEFORE this file existed. Run:

    python e45_s003_full.py

The strategy is untouched: this reuses `dynamic_grid/strat_trap.py` exactly as
E44 ran it. Only the data window changes. Everything before 2023-08-12 is data
that was not available when S003's baseline was locked, which makes it a genuine
out-of-sample period rather than another fold inside the search window.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data", "s003")
OUT = os.path.join(ROOT, "docs", "s003-full-e45.json")

ASSETS = ("SOL-USD", "LINK-USD")
UNSEEN_BEFORE = "2023-08-12"       # start of the window the baseline was locked on
E44_WINDOW = ("2023-08-12", "2026-08-13")
FOLD_START, FOLD_END = "2018-02-01", "2026-08-01"
RISK = 0.01
INITIAL = 10_000.0


def head(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def tick(ok):
    return "PASS" if ok else "FAIL"


def load(symbol):
    """Full daily history, with any trailing malformed bar dropped (criteria 1)."""
    with open(os.path.join(DATA, f"{symbol}_full.json"), encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]
    dropped = []
    while rows:
        d, o, h, l, c = rows[-1]
        if l <= o <= h and l <= c <= h:
            break
        dropped.append(d)
        rows.pop()
    dates = [r[0] for r in rows]
    arr = np.array([[r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
    return dates, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], dropped


def fold_bounds():
    out, y, m = [], 2018, 2
    while f"{y}-{m:02d}-01" <= FOLD_END:
        out.append(f"{y}-{m:02d}-01")
        m += 6
        if m > 12:
            m -= 12
            y += 1
    return tuple(out)


def collect(intrabar="tp_first"):
    per, trades, notes = {}, [], {}
    for symbol in ASSETS:
        dates, o, h, l, c, dropped = load(symbol)
        res = st.run_symbol(symbol, dates, o, h, l, c, intrabar=intrabar)
        per[symbol] = {"bars": len(dates), "first": dates[0], "last": dates[-1],
                       "dropped_tail_bars": dropped,
                       "trades": len(res.closed), "portR": res.port_r}
        notes[symbol] = (dates, c)
        trades.extend(res.closed)
    return per, trades, notes


def equity(trades, since=None):
    """1% of equity risked at entry; P&L booked at exit. Handles overlap."""
    sel = [t for t in trades if since is None or t.entry_date >= since]
    if not sel:
        return INITIAL, 0.0, 0
    events = [(t.entry_date, 0, t) for t in sel] + [(t.exit_date, 1, t) for t in sel]
    events.sort(key=lambda x: (x[0], x[1]))
    eq, risked, curve = INITIAL, {}, [INITIAL]
    for _, kind, t in events:
        if kind == 0:
            risked[id(t)] = eq * RISK
        else:
            eq += risked.pop(id(t), eq * RISK) * t.pnl_r_net
            curve.append(eq)
    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return eq, float(((peak - arr) / peak).max()), len(sel)


def main():
    head("E45 - S003 on the full history | criteria docs/E45_CRITERIA.md")
    print("  strategy untouched; only the data window changes")
    print(f"  data before {UNSEEN_BEFORE} was not available when the baseline was locked")

    per, trades, notes = collect("tp_first")
    head("Data")
    for symbol, s in per.items():
        span = ((dt.date.fromisoformat(s["last"]) - dt.date.fromisoformat(s["first"])).days
                / 365.25)
        print(f"  {symbol:<10}{s['bars']:>5} bars  {s['first']} -> {s['last']}  "
              f"({span:.1f}y)  dropped tail: {s['dropped_tail_bars'] or 'none'}")

    unseen = [t for t in trades if t.entry_date < UNSEEN_BEFORE]
    seen = [t for t in trades if t.entry_date >= UNSEEN_BEFORE]
    unseen_r = float(sum(t.pnl_r_net for t in unseen))
    seen_r = float(sum(t.pnl_r_net for t in seen))

    head("Y1 (primary): the period the designer never saw")
    print(f"  trades entered BEFORE {UNSEEN_BEFORE}: {len(unseen)}   portR {unseen_r:+.2f}")
    print(f"  trades entered AFTER  {UNSEEN_BEFORE}: {len(seen)}   portR {seen_r:+.2f}")
    y1 = unseen_r > 0
    print(f"  Y1 portR > 0 on never-seen data -> {tick(y1)}")

    head("Y2 (sanity): does the E44 window still reproduce?")
    e44_like = [t for t in trades
                if E44_WINDOW[0] <= t.entry_date < E44_WINDOW[1]]
    e44_r = float(sum(t.pnl_r_net for t in e44_like))
    y2 = abs(e44_r - 49.22) <= 0.05 * 49.22
    print(f"  portR restricted to the E44 window: {e44_r:+.2f}  vs E44 +49.22  -> {tick(y2)}")

    head("Y3 / Y4: six-month folds across the whole span")
    bounds = fold_bounds()
    folds = []
    for k in range(len(bounds) - 1):
        rs = [t.pnl_r_net for t in trades if bounds[k] <= t.entry_date < bounds[k + 1]]
        if rs:
            folds.append((bounds[k], bounds[k + 1], len(rs), float(sum(rs))))
    print(f"  {'fold':<26}{'n':>5}{'R':>9}")
    for a, b, n, r in folds:
        flag = "  <- negative" if r < 0 else ""
        print(f"  {a} -> {b}{n:>5}{r:>9.2f}{flag}")
    positives = sum(1 for *_, r in folds if r > 0)
    worst = min((r for *_, r in folds), default=0.0)
    y3 = positives / len(folds) >= 0.60 if folds else False
    y4 = worst > -8.0
    print(f"\n  folds {len(folds)} | positive {positives} ({positives/len(folds)*100:.0f}%) "
          f"-> Y3 {tick(y3)}    worst {worst:+.2f} R -> Y4 {tick(y4)}")

    head("Y5 / Y6")
    y5 = all(s["portR"] > 0 for s in per.values())
    for symbol, s in per.items():
        print(f"  {symbol:<10}{s['trades']:>5} trades   portR {s['portR']:+.2f}")
    per_sl, trades_sl, _ = collect("sl_first")
    sl_r = float(sum(t.pnl_r_net for t in trades_sl))
    y6 = sl_r > 0
    print(f"  Y5 both assets positive -> {tick(y5)}")
    print(f"  Y6 sl_first portR {sl_r:+.2f} -> {tick(y6)}")

    head("Descriptive: $10,000 at 1% risk per trade (not a criterion)")
    total_r = float(sum(t.pnl_r_net for t in trades))
    for label, since in (("full history", None), ("never-seen only", None),
                         ("E44 window only", E44_WINDOW[0])):
        pool = unseen if label == "never-seen only" else trades
        eq, dd, n = equity(pool, since=since)
        print(f"  {label:<20}{n:>5} trades   ${eq:>10,.0f}   "
              f"{eq/INITIAL-1:>+7.1%}   maxDD {dd:>5.1%}")
    print(f"\n  total portR (full history): {total_r:+.2f}")
    for symbol in ASSETS:
        dates, c = notes[symbol]
        print(f"  buy & hold {symbol}: {c[-1]/c[0]-1:+.1%} over its full span")

    verdict = "PASS" if all([y1, y2, y3, y4, y5, y6]) else "MIXED" if y1 else "FAIL"
    head(f"VERDICT: {verdict}   (promotion is forbidden regardless)")

    payload = {"experiment": "E45", "criteria": "docs/E45_CRITERIA.md",
               "per_symbol": per, "total_portR": total_r,
               "unseen": {"trades": len(unseen), "portR": unseen_r,
                          "cutoff": UNSEEN_BEFORE},
               "seen": {"trades": len(seen), "portR": seen_r},
               "e44_window_portR": e44_r,
               "folds": [{"from": a, "to": b, "n": n, "R": r} for a, b, n, r in folds],
               "sl_first_portR": sl_r,
               "checks": {"Y1": y1, "Y2": y2, "Y3": y3, "Y4": y4, "Y5": y5, "Y6": y6},
               "verdict": verdict}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
