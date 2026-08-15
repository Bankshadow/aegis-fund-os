"""E39 - crowded-long liquidation fade (Osmo S1) on BTC.

Criteria: `docs/E39_CRITERIA.md` (declared before the engine was written).
Engine:   `dynamic_grid/crowding_fade.py`
Panel:    `data/crowding/btcusdt_1h_panel.json`

    python scripts/fetch_crowding_panel.py
    python -m unittest tests.test_crowding_fade
    python e39_crowding.py

Measurement only: no order path, no leverage in the measurement layer, and no
directional call. Public L/S and OI history is capped at ~30 days, which the
criteria declare up front - this is not a multi-year walk-forward.

RECONSTRUCTED 2026-08-12. The original runner was overwritten by mistake and was
not tracked in git. This version drives the surviving engine and panel, and its
output was checked against the numbers already recorded in
`docs/VALIDATION_LOG.md` section E39 before being accepted.
"""

import json
import os

import numpy as np

from dynamic_grid import crowding_fade as cf

ROOT = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(ROOT, "data", "crowding", "btcusdt_1h_panel.json")
OUT = os.path.join(ROOT, "docs", "crowding-fade-e39.json")

MIN_N = 20          # G4
ARMS = ("S_full", "S_fund", "S_ls", "S_oi", "S_imp")


def head(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def pct(x, nd=2):
    return "    n/a" if x is None or (isinstance(x, float) and np.isnan(x)) \
        else f"{x * 100:>6.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


def main():
    head("E39 - crowded-long liquidation fade (Osmo S1) | docs/E39_CRITERIA.md")
    with open(PANEL, encoding="utf-8") as fh:
        panel = cf.align_panel(json.load(fh))
    print(f"  panel: {len(panel.close)} bars of 1h | L/S>={cf.LS_THRESH}, "
          f"funding>={cf.FUNDING_THRESH}, OI up over {cf.OI_LOOKBACK}h, "
          f"impulse>={cf.IMPULSE_ATR_MULT}xATR14")
    print("  public L/S + OI history is capped at ~30 days (criteria section 0)")

    m = cf.masks(panel)
    rng = np.random.default_rng(0)
    m["S_rand"] = cf.random_mask_like(m["S_full"], len(panel.close), cf.PRIMARY_H, rng)

    head("Fade score by arm (positive = fading paid)")
    print(f"  {'arm':<10}{'bars':>6}  "
          + "".join(f"{'h' + str(h) + ' mean(n)':>14}" for h in cf.HORIZONS))
    summaries = {}
    for name in ARMS + ("S_rand",):
        summaries[name] = cf.arm_summary(panel.close, m[name])
        row = summaries[name]
        cells = "".join(pct(row[h]["mean"]) + f"({row[h]['n']:>3})  "
                        for h in cf.HORIZONS)
        print(f"  {name:<10}{row['n_signal_bars']:>6}  {cells}")

    head(f"Primary test (declared, one only): S_full vs S_fund at h={cf.PRIMARY_H}")
    full = cf.fade_scores(panel.close, m["S_full"], cf.PRIMARY_H)
    fund = cf.fade_scores(panel.close, m["S_fund"], cf.PRIMARY_H)
    boot = cf.bootstrap_diff_percentile(full, fund, cf.BOOTSTRAP,
                                        np.random.default_rng(0))
    print(f"  n(S_full) = {len(full)}   n(S_fund) = {len(fund)}")
    if boot is None:
        print("  percentile = n/a - a group has fewer than 2 observations")
    else:
        print(f"  percentile = {boot.get('percentile', float('nan')) * 100:.1f}%")

    head("Gates")
    full_mean = float(np.mean(full)) if len(full) else None
    imp_mean = summaries["S_imp"][cf.PRIMARY_H]["mean"]
    rand_mean = summaries["S_rand"][cf.PRIMARY_H]["mean"]
    gates = {
        "G1 primary >= 95%": bool(boot and boot.get("percentile", 0) >= 0.95),
        "G2 S_full fade mean > 0": bool(full_mean is not None and full_mean > 0),
        "G3 beats S_imp and S_rand": bool(
            full_mean is not None and imp_mean is not None and rand_mean is not None
            and full_mean > imp_mean and full_mean > rand_mean),
        "G4 n >= 20 for full and fund": len(full) >= MIN_N and len(fund) >= MIN_N,
    }
    for label, ok in gates.items():
        print(f"  {label:<32}{tick(ok)}")
    g1_g4 = gates["G1 primary >= 95%"] and gates["G4 n >= 20 for full and fund"]
    print(f"  G5 held-out: {'evaluating' if g1_g4 else 'NOT evaluated - ETH/SOL stay untouched (section 7)'}")

    head("Secondary layer (section 4) - reported, never a pass/fail criterion")
    bh = cf.buy_hold(panel)
    overlays = {"buy_and_hold": bh,
                "cash_on_S_full": cf.cash_overlay(panel, m["S_full"]),
                "cash_on_S_fund": cf.cash_overlay(panel, m["S_fund"])}
    for name, row in overlays.items():
        print(f"  {name:<20}{pct(row['return'], 2)}   "
              f"maxDD {pct(row['maxDD'], 2)}   robust {row['robust']:>7.3f}")

    payload = {"experiment": "E39", "criteria": "docs/E39_CRITERIA.md",
               "engine": "dynamic_grid/crowding_fade.py", "panel": PANEL,
               "bars": len(panel.close),
               "thresholds": {"ls": cf.LS_THRESH, "funding": cf.FUNDING_THRESH,
                              "oi_lookback": cf.OI_LOOKBACK,
                              "impulse_atr_mult": cf.IMPULSE_ATR_MULT},
               "arms": summaries,
               "primary": {"n_full": len(full), "n_fund": len(fund),
                           "bootstrap": boot},
               "gates": gates, "secondary": overlays,
               "verdict": "PASS" if all(gates.values()) else "FAIL",
               "note": "runner reconstructed 2026-08-12 after an accidental "
                       "overwrite; verified against the recorded E39 section"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
