"""E35 - does the golden pocket (0.618-0.66) react differently on BTC?

Criteria declared in `docs/E35_CRITERIA.md` BEFORE this file existed. Run:

    python e35_retracement.py
    python -m unittest tests.test_retracement

Read-only measurement. No orders, no leverage, no short, no promotion path.
"""

import json
import os

import numpy as np

from dynamic_grid import retracement as rt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "golden-pocket-e35.json")

LOOKBACKS = (5, 10, 20)
HORIZONS = (5, 10, 20)
PRIMARY = {"lookback": 10, "horizon": 10, "zone": "Z3_golden", "control": "Z5_random"}
BOOTSTRAP = 10_000
MIN_N = 30


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        raw = json.load(fh)
    high = np.array([float(b[2]) for b in raw])
    low = np.array([float(b[3]) for b in raw])
    close = np.array([float(b[4]) for b in raw])
    return high, low, close


def head(title):
    print("\n" + "=" * 94)
    print(title)
    print("=" * 94)


def tick(ok):
    return "PASS" if ok else "FAIL"


def analyse(high, low, close, label):
    base = rt.baseline(close, HORIZONS, start=0)
    out = {}
    for lookback in LOOKBACKS:
        rng = np.random.default_rng(0)          # fixed seed, declared in criteria
        obs = rt.observations(high, low, close, lookback, HORIZONS, rng)
        boot = np.random.default_rng(7)
        zones = {}
        for name, rows in obs.items():
            entry = {"n": len(rows)}
            for h in HORIZONS:
                values = np.array([row[f"fwd_{h}"] for row in rows])
                if len(values) == 0:
                    entry[h] = None
                    continue
                draws = np.array([boot.choice(base[h], size=len(values),
                                              replace=False).mean()
                                  for _ in range(BOOTSTRAP)])
                entry[h] = {
                    "mean": float(values.mean()),
                    "median": float(np.median(values)),
                    "win_rate": float(np.mean(values > 0)),
                    "base_mean": float(base[h].mean()),
                    "base_win_rate": float(np.mean(base[h] > 0)),
                    "percentile": float(np.mean(draws < values.mean())),
                }
            zones[name] = entry
        out[lookback] = zones
    return {"label": label, "by_lookback": out}


def zone_vs_zone(zones, zone_a, zone_b, horizon, samples=BOOTSTRAP):
    """Percentile of zone_a's mean against resamples of zone_b's observations."""
    a = zones[zone_a][horizon]
    b = zones[zone_b][horizon]
    if a is None or b is None:
        return None
    return {"a_mean": a["mean"], "b_mean": b["mean"], "a_beats_b": a["mean"] > b["mean"]}


def print_table(zones, label):
    print(f"\n  {label}")
    print(f"  {'zone':<12}{'n':>5}" + "".join(f"{'h' + str(h) + 'mean':>11}" for h in HORIZONS)
          + "".join(f"{'h' + str(h) + 'pct':>10}" for h in HORIZONS))
    for name in list(rt.LEVELS) + [rt.RANDOM_ZONE]:
        entry = zones[name]
        means = "".join(
            (f"{entry[h]['mean'] * 100:>10.2f}%" if entry.get(h) else f"{'-':>11}")
            for h in HORIZONS)
        pcts = "".join(
            (f"{entry[h]['percentile'] * 100:>9.1f}%" if entry.get(h) else f"{'-':>10}")
            for h in HORIZONS)
        print(f"  {name:<12}{entry['n']:>5}{means}{pcts}")


def main():
    high, low, close = load("btc_daily_full.json")
    head(f"E35 - golden pocket on BTC | {len(close)} daily bars | docs/E35_CRITERIA.md")
    print("  zone width is identical for every level (0.042 of swing range)")
    print("  a pivot at bar i is usable only from bar i+lookback")
    print("  one observation per swing per zone; baseline is direction-symmetric")

    btc = analyse(high, low, close, "BTC")
    for lookback in LOOKBACKS:
        print_table(btc["by_lookback"][lookback], f"swing lookback L={lookback}")

    # ---- criteria ---------------------------------------------------------
    head("Criteria")
    zones = btc["by_lookback"][PRIMARY["lookback"]]
    primary = zones[PRIMARY["zone"]][PRIMARY["horizon"]]
    control = zones[PRIMARY["control"]][PRIMARY["horizon"]]

    g1 = primary is not None and primary["mean"] > control["mean"] and primary["percentile"] >= 0.95
    print(f"  G1 primary: Z3 vs random control, L=10 h=10")
    print(f"     Z3 mean {primary['mean'] * 100:.2f}%  percentile {primary['percentile'] * 100:.1f}%"
          f"   random mean {control['mean'] * 100:.2f}%   -> {tick(g1)}")

    others = ["Z1_0382", "Z2_0500", "Z4_0786"]
    g2 = all(primary["mean"] > zones[o][PRIMARY["horizon"]]["mean"] for o in others)
    print(f"  G2 Z3 beats Z1/Z2/Z4 at L=10 h=10: "
          + ", ".join(f"{o} {zones[o][PRIMARY['horizon']]['mean'] * 100:.2f}%" for o in others)
          + f"   -> {tick(g2)}")

    signs = [btc["by_lookback"][L]["Z3_golden"][PRIMARY["horizon"]]["mean"] > 0
             for L in LOOKBACKS]
    g3 = len(set(signs)) == 1
    print(f"  G3 same direction across L=5,10,20: "
          + ", ".join(f"L{L} {btc['by_lookback'][L]['Z3_golden'][PRIMARY['horizon']]['mean'] * 100:+.2f}%"
                      for L in LOOKBACKS)
          + f"   -> {tick(g3)}")

    counts = {name: zones[name]["n"] for name in list(rt.LEVELS) + [rt.RANDOM_ZONE]}
    g4 = all(c >= MIN_N for c in counts.values())
    print(f"  G4 n >= {MIN_N} per zone at L=10: {counts}   -> {tick(g4)}")

    held = {}
    g5 = None
    if g1 and g2 and g3 and g4:
        head("G5 - held-out (touched only because BTC passed G1-G4)")
        for symbol, filename in (("ETH", "ETHUSDT_1d.json"), ("SOL", "SOLUSDT_1d.json")):
            h2, l2, c2 = load(filename)
            held[symbol] = analyse(h2, l2, c2, symbol)
            entry = held[symbol]["by_lookback"][PRIMARY["lookback"]]["Z3_golden"][PRIMARY["horizon"]]
            print(f"  {symbol}: Z3 mean {entry['mean'] * 100:+.2f}% n={held[symbol]['by_lookback'][PRIMARY['lookback']]['Z3_golden']['n']}")
        g5 = all(held[s]["by_lookback"][PRIMARY["lookback"]]["Z3_golden"][PRIMARY["horizon"]]["mean"] > 0
                 for s in held)
        print(f"  G5 -> {tick(g5)}")
    else:
        print("\n  G5 not evaluated: BTC did not clear G1-G4, held-out stays untouched.")

    verdict = "PASS" if all([g1, g2, g3, g4, g5]) else "FAIL"
    print(f"\n  VERDICT: {verdict}  (promotion is forbidden regardless)")

    payload = {
        "experiment": "E35", "criteria": "docs/E35_CRITERIA.md",
        "config": {"lookbacks": LOOKBACKS, "horizons": HORIZONS,
                   "zone_width": rt.ZONE_WIDTH, "primary": PRIMARY,
                   "bootstrap": BOOTSTRAP, "min_n": MIN_N},
        "btc": btc, "held_out": held,
        "criteria_results": {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5},
        "verdict": verdict,
        "run_count": len(LOOKBACKS) * (len(rt.LEVELS) + 1) * len(HORIZONS),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
