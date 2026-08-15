"""E44 - reproduce S003 (fade failed breakout, SOL+LINK daily) from the spec.

Criteria declared in `docs/E44_CRITERIA.md` BEFORE the engine was written. Run:

    python e44_s003.py
    python -m unittest tests.test_strat_trap

Reproduction only: no variant search, no parameter is tuned, no order path.
The spec itself says research artifact, not live trading advice.
"""

import json
import os
import urllib.request

import numpy as np

from dynamic_grid import strat_trap as st

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data", "s003")
OUT = os.path.join(ROOT, "docs", "s003-repro-e44.json")

ASSETS = ("SOL-USD", "LINK-USD")
HELD_OUT = ("BTC-USD", "ETH-USD")
BOUNDS = ("2024-08-01", "2025-02-01", "2025-08-01", "2026-08-01")
BASELINE = {"portR": 49.06, "minFold": 3.71, "sumOOS": 32.26}


def head(title):
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


def tick(ok):
    return "PASS" if ok else "FAIL"


def fetch(symbol):
    """Yahoo daily OHLCV, cached on disk so a rerun is reproducible."""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"{symbol}.json")
    if not os.path.exists(path):
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
               f"?range=3y&interval=1d")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read())
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)

    result = payload["chart"]["result"][0]
    stamps = result["timestamp"]
    q = result["indicators"]["quote"][0]
    import datetime as dt
    rows = [(dt.datetime.fromtimestamp(t, dt.UTC).date().isoformat(),
             q["open"][i], q["high"][i], q["low"][i], q["close"][i])
            for i, t in enumerate(stamps)
            if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
    dates = [r[0] for r in rows]
    arr = np.array([[r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
    bad = int(np.count_nonzero(~((arr[:, 2] <= arr[:, 0]) & (arr[:, 0] <= arr[:, 1])
                                 & (arr[:, 2] <= arr[:, 3]) & (arr[:, 3] <= arr[:, 1]))))
    return dates, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], bad


def evaluate(symbols, intrabar="tp_first"):
    per_symbol, all_trades = {}, []
    for symbol in symbols:
        dates, o, h, l, c, bad = fetch(symbol)
        res = st.run_symbol(symbol, dates, o, h, l, c, intrabar=intrabar)
        per_symbol[symbol] = {
            "bars": len(dates), "first": dates[0], "last": dates[-1],
            "ohlc_violations": bad,
            "trades": len(res.closed),
            "portR": res.port_r,
            "wins": sum(1 for t in res.closed if t.pnl_r_net > 0),
        }
        all_trades.extend(res.closed)

    folds = [[] for _ in range(len(BOUNDS) - 1)]
    for t in all_trades:
        k = st.fold_of(t.entry_date, BOUNDS)
        if k >= 0:
            folds[k].append(t.pnl_r_net)
    fold_r = [float(sum(f)) for f in folds]
    return {
        "per_symbol": per_symbol,
        "portR": float(sum(t.pnl_r_net for t in all_trades)),
        "fold_r": fold_r, "fold_n": [len(f) for f in folds],
        "minFold": float(min(fold_r)) if fold_r else 0.0,
        "sumOOS": float(sum(fold_r)),
        "trades": len(all_trades),
        "exit_mix": {r: sum(1 for t in all_trades if t.reason == r)
                     for r in sorted({t.reason for t in all_trades})},
    }


def main():
    head("E44 - S003 reproduction | criteria docs/E44_CRITERIA.md")
    print("  fade STRAT failed breakouts, SOL-USD + LINK-USD daily, Yahoo")
    print(f"  baseline to hit: portR {BASELINE['portR']:+.2f}, "
          f"minFold {BASELINE['minFold']:+.2f}, sumOOS {BASELINE['sumOOS']:+.2f}")

    main_run = evaluate(ASSETS, "tp_first")

    head("Data")
    for symbol, s in main_run["per_symbol"].items():
        print(f"  {symbol:<10}{s['bars']:>5} bars  {s['first']} -> {s['last']}  "
              f"OHLC violations {s['ohlc_violations']}")

    head("Result (primary: optimistic TP-first)")
    print(f"  {'symbol':<10}{'trades':>8}{'wins':>7}{'portR':>10}")
    for symbol, s in main_run["per_symbol"].items():
        print(f"  {symbol:<10}{s['trades']:>8}{s['wins']:>7}{s['portR']:>10.2f}")
    print(f"  {'TOTAL':<10}{main_run['trades']:>8}{'':>7}{main_run['portR']:>10.2f}")
    print(f"\n  exits: {main_run['exit_mix']}")

    print(f"\n  {'fold':<26}{'n':>5}{'R':>10}")
    for k in range(len(BOUNDS) - 1):
        print(f"  {BOUNDS[k]} -> {BOUNDS[k+1]}{main_run['fold_n'][k]:>5}"
              f"{main_run['fold_r'][k]:>10.2f}")
    print(f"  {'minFold':<26}{'':>5}{main_run['minFold']:>10.2f}")
    print(f"  {'sumOOS':<26}{'':>5}{main_run['sumOOS']:>10.2f}")

    head("W1-W3: did it reproduce?")
    w1 = abs(main_run["portR"] - BASELINE["portR"]) <= 0.20 * BASELINE["portR"]
    w2 = main_run["minFold"] > 0 and abs(main_run["minFold"] - BASELINE["minFold"]) <= 2.0
    w3 = abs(main_run["sumOOS"] - BASELINE["sumOOS"]) <= 0.20 * BASELINE["sumOOS"]
    print(f"  W1 portR   {main_run['portR']:>8.2f} vs {BASELINE['portR']:+.2f} "
          f"(band {BASELINE['portR']*0.8:.1f}-{BASELINE['portR']*1.2:.1f})   {tick(w1)}")
    print(f"  W2 minFold {main_run['minFold']:>8.2f} vs {BASELINE['minFold']:+.2f} "
          f"(band {BASELINE['minFold']-2:.2f}-{BASELINE['minFold']+2:.2f})   {tick(w2)}")
    print(f"  W3 sumOOS  {main_run['sumOOS']:>8.2f} vs {BASELINE['sumOOS']:+.2f} "
          f"(band {BASELINE['sumOOS']*0.8:.1f}-{BASELINE['sumOOS']*1.2:.1f})   {tick(w3)}")
    reproduced = w1 and w2 and w3
    print(f"\n  reproduced: {tick(reproduced)}")

    head("X1-X3 (project criteria)")
    stress = evaluate(ASSETS, "sl_first")
    x1 = main_run["minFold"] > 0
    x2 = stress["portR"] > 0
    biggest = max(s["portR"] for s in main_run["per_symbol"].values())
    x3 = (main_run["portR"] <= 0) or (biggest <= 0.80 * main_run["portR"])
    print(f"  X1 every OOS fold positive                {tick(x1)}")
    print(f"  X2 sl_first still positive: portR {stress['portR']:+.2f}   {tick(x2)}")
    print(f"  X3 no single asset > 80% of portR "
          f"({biggest:+.2f} of {main_run['portR']:+.2f})   {tick(x3)}")
    print(f"\n  intrabar model spread: tp_first {main_run['portR']:+.2f} "
          f"vs sl_first {stress['portR']:+.2f} "
          f"(gap {main_run['portR'] - stress['portR']:.2f} R)")
    print(f"  X4 held-out {HELD_OUT}: "
          f"{'evaluating' if reproduced and x1 and x2 and x3 else 'NOT touched (section 5)'}")

    held = {}
    if reproduced and x1 and x2 and x3:
        head("X4 - held-out BTC/ETH")
        held = evaluate(HELD_OUT, "tp_first")
        print(f"  portR {held['portR']:+.2f}  minFold {held['minFold']:+.2f}")

    payload = {"experiment": "E44", "criteria": "docs/E44_CRITERIA.md",
               "spec": "s003_agent_spec.md", "baseline": BASELINE,
               "bounds": BOUNDS, "primary": main_run, "stress_sl_first": stress,
               "held_out": held,
               "checks": {"W1": w1, "W2": w2, "W3": w3,
                          "X1": x1, "X2": x2, "X3": x3},
               "reproduced": reproduced}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
