"""E36 - do Koroush volume regimes separate momentum vs fade on BTC?

Criteria declared in `docs/E36_CRITERIA.md` BEFORE this file existed. Run:

    python e36_volume.py
    python -m unittest tests.test_volume_regime

Read-only measurement. No orders, no leverage, no short, no promotion path.
"""

import json
import os

import numpy as np

from dynamic_grid import volume_regime as vr

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "volume-regime-e36.json")

PRIMARY = {"window": 10, "horizon": 10}
BOOTSTRAP = 10_000
MIN_N = 30


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        raw = json.load(fh)
    high = np.array([float(b[2]) for b in raw])
    low = np.array([float(b[3]) for b in raw])
    close = np.array([float(b[4]) for b in raw])
    quote = np.array([float(b[7]) for b in raw])
    return high, low, close, quote


def head(title):
    print("\n" + "=" * 94)
    print(title)
    print("=" * 94)


def tick(ok):
    return "PASS" if ok else "FAIL"


def summarise_obs(obs, horizons=vr.HORIZONS):
    out = {}
    for regime, rows in obs.items():
        entry = {"n": len(rows)}
        for h in horizons:
            cont = [r.continuation[h] for r in rows]
            fade = [r.fade[h] for r in rows]
            entry[h] = {
                "continuation_mean": float(np.mean(cont)) if cont else None,
                "fade_mean": float(np.mean(fade)) if fade else None,
                "continuation_win": float(np.mean(np.array(cont) > 0)) if cont else None,
                "fade_win": float(np.mean(np.array(fade) > 0)) if fade else None,
            }
        out[regime] = entry
    return out


def analyse(high, low, close, quote, label):
    by_window = {}
    primary_boot = None
    for window in vr.WINDOWS:
        obs = vr.observations(quote, close, high, low, window)
        summary = summarise_obs(obs)
        rng = np.random.default_rng(0)
        boot = vr.bootstrap_diff_percentile(
            obs["INCREASING"], obs["FLAT"], PRIMARY["horizon"], "continuation",
            BOOTSTRAP, rng)
        # Also spike vs non-spike fade at same horizon for reporting
        spike_rows = obs["SPIKE"]
        non_spike = obs["INCREASING"] + obs["DECREASING"] + obs["FLAT"]
        rng2 = np.random.default_rng(1)
        spike_boot = vr.bootstrap_diff_percentile(
            spike_rows, non_spike, PRIMARY["horizon"], "fade",
            BOOTSTRAP, rng2)

        price_mask = vr.price_only_spike_mask(close, high, low, window)
        vol_mask = vr.volume_only_spike_mask(quote, close, window)
        # Restrict controls to bars that have forward room
        max_h = max(vr.HORIZONS)
        price_mask = price_mask.copy()
        vol_mask = vol_mask.copy()
        price_mask[len(close) - max_h:] = False
        vol_mask[len(close) - max_h:] = False

        control_b = vr.scores_on_mask(close, price_mask, vr.HORIZONS, "fade")
        control_c = vr.scores_on_mask(close, vol_mask, vr.HORIZONS, "fade")

        by_window[window] = {
            "regimes": summary,
            "primary_boot": boot,
            "spike_vs_rest_fade_boot": spike_boot,
            "control_b_price_only_fade": control_b,
            "control_c_volume_only_fade": control_c,
        }
        if window == PRIMARY["window"]:
            primary_boot = boot
    return {"label": label, "by_window": by_window, "primary_boot": primary_boot}


def print_table(by_window):
    h = PRIMARY["horizon"]
    print(f"\n  Continuation / fade means at h={h} (primary horizon)")
    print(f"  {'W':>3}  {'regime':<12}{'n':>6}{'cont':>10}{'fade':>10}")
    for window in vr.WINDOWS:
        regimes = by_window[window]["regimes"]
        for name in vr.REGIMES:
            e = regimes[name]
            c = e[h]["continuation_mean"]
            f = e[h]["fade_mean"]
            cs = f"{c * 100:.2f}%" if c is not None else "-"
            fs = f"{f * 100:.2f}%" if f is not None else "-"
            print(f"  {window:>3}  {name:<12}{e['n']:>6}{cs:>10}{fs:>10}")


def gate_results(btc):
    w = PRIMARY["window"]
    h = PRIMARY["horizon"]
    pack = btc["by_window"][w]
    boot = pack["primary_boot"]
    regimes = pack["regimes"]
    spike_fade = regimes["SPIKE"][h]["fade_mean"]
    control_b_mean = pack["control_b_price_only_fade"][h]["mean"]

    g1 = boot is not None and boot["percentile"] >= 0.95
    g2 = (spike_fade is not None and spike_fade > 0
          and control_b_mean is not None and spike_fade > control_b_mean)
    # G3: same direction of (inc cont - flat cont) across all W
    diffs = []
    for window in vr.WINDOWS:
        b = btc["by_window"][window]["primary_boot"]
        if b is None:
            diffs.append(None)
        else:
            diffs.append(b["diff"])
    g3 = all(d is not None and d > 0 for d in diffs)
    g4 = (regimes["INCREASING"]["n"] >= MIN_N
          and regimes["FLAT"]["n"] >= MIN_N)
    g5 = None  # held-out not touched unless BTC wins

    return {
        "G1": {"pass": g1, "detail": boot},
        "G2": {"pass": g2, "spike_fade": spike_fade, "control_b": control_b_mean},
        "G3": {"pass": g3, "diffs": diffs},
        "G4": {"pass": g4,
               "n_increasing": regimes["INCREASING"]["n"],
               "n_flat": regimes["FLAT"]["n"]},
        "G5": {"pass": g5, "note": "held-out untouched until BTC primary survives"},
    }


def main():
    high, low, close, quote = load("btc_daily_full.json")
    head("E36 Volume Regime — BTC daily (criteria locked before code)")
    print(f"  bars={len(close)}  median daily VolUSD={np.median(quote):,.0f}")
    print(f"  primary: W={PRIMARY['window']} h={PRIMARY['horizon']}  "
          f"bootstrap={BOOTSTRAP}")

    btc = analyse(high, low, close, quote, "BTC")
    print_table(btc["by_window"])

    boot = btc["primary_boot"]
    head("Primary test — INCREASING cont vs FLAT cont (W=10, h=10)")
    if boot is None:
        print("  insufficient n")
    else:
        print(f"  INCREASING mean={boot['a_mean']*100:.3f}%  n={boot['n_a']}")
        print(f"  FLAT        mean={boot['b_mean']*100:.3f}%  n={boot['n_b']}")
        print(f"  diff={boot['diff']*100:.3f} pp  bootstrap percentile="
              f"{boot['percentile']*100:.1f}%")

    gates = gate_results(btc)
    head("Gates")
    for gid, info in gates.items():
        status = "SKIP" if info["pass"] is None else tick(info["pass"])
        print(f"  {gid}: {status}  { {k: v for k, v in info.items() if k != 'pass'} }")

    verdict = all(gates[g]["pass"] is True for g in ("G1", "G2", "G3", "G4"))
    # G5 deferred
    head("Verdict")
    if gates["G1"]["pass"] and gates["G4"]["pass"]:
        print("  Primary survived on BTC — would unlock held-out next.")
    else:
        print("  Primary did NOT survive on BTC — held-out untouched (per criteria).")
    print(f"  G1–G4 all pass: {verdict}")

    payload = {
        "criteria": "docs/E36_CRITERIA.md",
        "primary": PRIMARY,
        "btc": {
            "n_bars": len(close),
            "median_quote_volume": float(np.median(quote)),
            "by_window": {
                str(w): {
                    "regimes": btc["by_window"][w]["regimes"],
                    "primary_boot": btc["by_window"][w]["primary_boot"],
                    "spike_vs_rest_fade_boot": btc["by_window"][w]["spike_vs_rest_fade_boot"],
                    "control_b_price_only_fade": btc["by_window"][w]["control_b_price_only_fade"],
                    "control_c_volume_only_fade": btc["by_window"][w]["control_c_volume_only_fade"],
                }
                for w in vr.WINDOWS
            },
        },
        "gates": gates,
        "verdict_g1_g4": verdict,
        "held_out_touched": False,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\n  wrote {OUT}")


if __name__ == "__main__":
    main()
