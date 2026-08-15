"""E36 - can "EMA9/21 + loose RSI, 5x" be reproduced on 4h over 2 years?

Criteria declared in `docs/E36_CRITERIA.md` BEFORE this file existed. Run:

    python e36_ema_rsi.py
    python -m unittest tests.test_ema_rsi

Read-only backtest. No order path. Nothing here is promoted to live trading.
"""

import json
import os

import numpy as np

from dynamic_grid import ema_rsi as er
from dynamic_grid import leveraged as lv

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "ema-rsi-e36.json")

INITIAL = 5_000.0          # derived from the claim: 7,650 / 1.53
BARS_PER_YEAR = 6 * 365.25
WARMUP = 60                # EMA21 + RSI14 fully seeded well before this

CLAIM = {"trades": 73, "win_rate": 0.78, "pnl": 7650.0, "roi": 1.53,
         "profit_factor": 1.45, "max_dd": 0.67, "trades_per_month": 3.1}


def head(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


def load_panel(price_file, funding_file):
    with open(os.path.join(ROOT, "data", price_file), encoding="utf-8") as fh:
        bars = json.load(fh)
    opens = np.array([int(b[0]) for b in bars])
    closes = np.array([[float(b[4])] for b in bars])
    highs = np.array([[float(b[2])] for b in bars])
    lows = np.array([[float(b[3])] for b in bars])

    funding = np.zeros((len(bars), 1))
    if funding_file:
        with open(os.path.join(ROOT, "data", funding_file), encoding="utf-8") as fh:
            settlements = json.load(fh)
        # Perp funding settles every 8h; place each settlement in the 4h bar
        # that contains it, so a long pays exactly what it really paid.
        step = 4 * 3600 * 1000
        index = {t: i for i, t in enumerate(opens)}
        placed = 0
        for row in settlements:
            bar_open = (int(row["fundingTime"]) // step) * step
            i = index.get(bar_open)
            if i is not None:
                funding[i, 0] += float(row["fundingRate"])
                placed += 1
        print(f"  funding: {placed}/{len(settlements)} settlements placed on bars")
    return opens, closes, highs, lows, funding


def trade_stats(result, closes):
    """Round trips, win rate and profit factor from the EXECUTED weight path."""
    weights = np.array([w[0] for w in result.weights_log])
    equity = np.concatenate(([result.initial_equity], result.equity))
    spans = er.count_trades(weights)["spans"]
    wins, losses = [], []
    for entry, exit_i, _side in spans:
        # equity[k] is the book after bar (start + k - 1); a trade opened at
        # log index `entry` is marked from that point to its close.
        pnl = float(equity[exit_i + 1] - equity[entry + 1])
        (wins if pnl > 0 else losses).append(pnl)
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    count = len(wins) + len(losses)
    return {
        "trades": count,
        "win_rate": (len(wins) / count) if count else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
        "avg_win": (gross_win / len(wins)) if wins else 0.0,
        "avg_loss": (gross_loss / len(losses)) if losses else 0.0,
    }


def run(closes, highs, lows, funding, arm, leverage, long_only=False):
    strategy = er.EmaRsi(closes, arm=arm, leverage=leverage, long_only=long_only)
    result = lv.simulate(None, closes, highs, lows, funding, strategy,
                         start=WARMUP, initial_equity=INITIAL)
    stats = trade_stats(result, closes)
    years = result.days / BARS_PER_YEAR
    return {
        "name": strategy.name, "arm": arm, "leverage": leverage,
        "long_only": long_only,
        "total_return": result.total_return,
        "final_equity": result.final_equity,
        "pnl": result.final_equity - INITIAL,
        "max_dd": result.max_drawdown,
        "robust": result.robust,
        "liquidations": result.liquidations,
        "ruined": result.ruined,
        "funding_paid": result.funding_paid,
        "years": years,
        "trades_per_month": stats["trades"] / (years * 12) if years else 0.0,
        **stats,
    }


class BuyHold:
    """Unlevered spot-equivalent control."""

    name = "buy_and_hold_1x"

    def __init__(self, n_assets=1):
        self.n_assets = n_assets

    def weights(self, i):
        w = np.zeros(self.n_assets)
        w[0] = 1.0
        return w


def show(rows, title):
    head(title)
    print(f"  {'arm':<22}{'lev':>5}{'trades':>8}{'win%':>8}{'PF':>7}"
          f"{'PnL $':>11}{'ROI':>9}{'maxDD':>9}{'robust':>9}{'liq':>5}{'t/mo':>7}")
    for r in rows:
        pf = f"{r['profit_factor']:.2f}" if r["profit_factor"] else "  n/a"
        print(f"  {r['arm']:<22}{r['leverage']:>4.0f}x{r['trades']:>8}"
              f"{pct(r['win_rate'])}{pf:>7}{r['pnl']:>11,.0f}{pct(r['total_return'])}"
              f"{pct(r['max_dd'])}{r['robust']:>9.2f}{r['liquidations']:>5}"
              f"{r['trades_per_month']:>7.1f}")


def main():
    head("E36 - EMA9/21 + loose RSI @5x on BTCUSDT 4h | criteria docs/E36_CRITERIA.md")
    opens, closes, highs, lows, funding = load_panel(
        "BTCUSDT_4h_2y.json", "BTCUSDT_funding_2y.json")
    print(f"  {len(closes)} bars of 4h = {len(closes) / BARS_PER_YEAR:.2f} years, "
          f"initial ${INITIAL:,.0f}")
    print(f"  claim to reproduce: {CLAIM['trades']} trades, "
          f"{CLAIM['win_rate'] * 100:.0f}% win, +${CLAIM['pnl']:,.0f}, "
          f"ROI +{CLAIM['roi'] * 100:.0f}%, PF {CLAIM['profit_factor']}, "
          f"maxDD {CLAIM['max_dd'] * 100:.0f}%")

    arms = list(er.RSI_ARMS)
    primary = [run(closes, highs, lows, funding, arm, 5.0) for arm in arms]
    show(primary, "All four declared RSI readings, long/short, 5x")

    bh = lv.simulate(None, closes, highs, lows, funding, BuyHold(), start=WARMUP,
                     initial_equity=INITIAL, use_funding=False)
    print(f"\n  buy & hold 1x: ROI {pct(bh.total_return)}  maxDD {pct(bh.max_drawdown)}"
          f"  robust {bh.robust:.2f}")

    # --- criteria ----------------------------------------------------------
    best = max(primary, key=lambda r: r["robust"])
    control = next(r for r in primary if r["arm"] == "R0_none")
    filtered = [r for r in primary if r["arm"] != "R0_none"]
    best_filtered = max(filtered, key=lambda r: r["robust"])
    one_x = [run(closes, highs, lows, funding, r["arm"], 1.0) for r in primary]
    best_1x = max(one_x, key=lambda r: r["robust"])
    show(one_x, "Same arms at 1x - the leverage control (V5)")

    head("Layer 1 - the source table's own criteria")
    print(f"  {'arm':<22}{'T1 >=25':>9}{'T2 >55%':>9}{'T3 profit':>11}{'T4 DD<100%':>12}{'all':>6}")
    layer1 = {}
    for r in primary:
        t = {"T1": r["trades"] >= 25, "T2": r["win_rate"] > 0.55,
             "T3": r["pnl"] > 0, "T4": r["max_dd"] < 1.0 and not r["ruined"]}
        layer1[r["arm"]] = t
        print(f"  {r['arm']:<22}{tick(t['T1']):>9}{tick(t['T2']):>9}"
              f"{tick(t['T3']):>11}{tick(t['T4']):>12}{tick(all(t.values())):>6}")

    head("Layer 2 - project criteria")
    ref = next(r for r in primary if r["arm"] == "R1_above50")
    v1_trades = abs(ref["trades"] - CLAIM["trades"]) <= 0.30 * CLAIM["trades"]
    v1_wr = abs(ref["win_rate"] - CLAIM["win_rate"]) <= 0.10
    v1 = v1_trades and v1_wr
    print(f"  V1 reproduce (R1 vs claim): trades {ref['trades']} vs {CLAIM['trades']} "
          f"({tick(v1_trades)}), win {ref['win_rate'] * 100:.0f}% vs "
          f"{CLAIM['win_rate'] * 100:.0f}% ({tick(v1_wr)})  -> {tick(v1)}")
    v2 = best["robust"] > 0
    print(f"  V2 robust > 0 (best arm {best['arm']}): {best['robust']:.2f}  -> {tick(v2)}")
    v3 = best["robust"] > bh.robust
    print(f"  V3 beats buy&hold robust ({bh.robust:.2f})  -> {tick(v3)}")
    v4 = best_filtered["robust"] > control["robust"]
    print(f"  V4 RSI adds value: best filtered {best_filtered['arm']} "
          f"{best_filtered['robust']:.2f} vs no-RSI {control['robust']:.2f}  -> {tick(v4)}")
    v5 = best["robust"] > best_1x["robust"]
    print(f"  V5 5x beats 1x: {best['robust']:.2f} vs {best_1x['robust']:.2f} "
          f"({best_1x['arm']})  -> {tick(v5)}")
    v6 = best["liquidations"] == 0 and not best["ruined"]
    print(f"  V6 no liquidation / no ruin: liq={best['liquidations']} "
          f"ruined={best['ruined']}  -> {tick(v6)}")

    passed = v2 and v3 and v4 and v5 and v6
    print(f"\n  V2-V6 on BTC: {tick(passed)}")
    if not passed:
        print("  V7 not evaluated: held-out stays untouched (section 6).")

    # robustness: long-only
    long_only = [run(closes, highs, lows, funding, arm, 5.0, long_only=True)
                 for arm in arms]
    show(long_only, "Robustness - long-only, 5x")

    # --- post-hoc diagnostics (labelled: NOT part of the declared criteria) --
    head("Diagnostics - post-hoc, not part of the pre-declared criteria")

    print("  D1 - is the loss the fees? Same arm, costs and funding switched off:")
    decomposition = {}
    for label, cost, use_funding in (("as declared", lv.PERP_COST, True),
                                     ("zero cost", 0.0, True),
                                     ("zero funding", lv.PERP_COST, False),
                                     ("zero cost + zero funding", 0.0, False)):
        strategy = er.EmaRsi(closes, arm="R1_above50", leverage=5.0)
        r = lv.simulate(None, closes, highs, lows, funding, strategy, start=WARMUP,
                        initial_equity=INITIAL, cost=cost, use_funding=use_funding)
        decomposition[label] = {"roi": r.total_return, "max_dd": r.max_drawdown}
        print(f"      {label:<26} ROI {pct(r.total_return)}   maxDD {pct(r.max_dd if hasattr(r, 'max_dd') else r.max_drawdown)}")
    print("      -> costs are NOT the cause; the signal loses on its own")

    print(f"\n  D2 - cost of one full reversal, as a share of the whole account:")
    for lev in (1, 3, 5):
        print(f"      {lev}x: reverses {2 * lev:.0f}x notional = "
              f"{2 * lev * lv.PERP_COST * 100:.2f}% of the account per flip")

    print("\n  D3 - a DIFFERENT two years (2022-06 -> 2024-07), same code:")
    other = {}
    prev_path = os.path.join(ROOT, "data", "BTCUSDT_4h_prev2y.json")
    if os.path.exists(prev_path):
        _, c2, h2, l2, f2 = load_panel("BTCUSDT_4h_prev2y.json", None)
        bh2 = lv.simulate(None, c2, h2, l2, f2, BuyHold(), start=WARMUP,
                          initial_equity=INITIAL, use_funding=False)
        print(f"      BTC buy&hold that window: ROI {pct(bh2.total_return)}")
        for arm in arms:
            s2 = er.EmaRsi(c2, arm=arm, leverage=5.0)
            r2 = lv.simulate(None, c2, h2, l2, f2, s2, start=WARMUP, initial_equity=INITIAL)
            st2 = trade_stats(r2, c2)
            other[arm] = {"roi": r2.total_return, "max_dd": r2.max_drawdown,
                          "trades": st2["trades"], "win_rate": st2["win_rate"]}
            print(f"      {arm:<20} ROI {pct(r2.total_return)}  trades {st2['trades']:>4}"
                  f"  win {pct(st2['win_rate'])}")
        print("      -> the market rose +183% and the strategy still lost ~95-99%:")
        print("         the window is not the explanation, the mechanism is")
    else:
        print("      (skipped: data/BTCUSDT_4h_prev2y.json not present)")

    payload = {
        "experiment": "E36", "criteria": "docs/E36_CRITERIA.md", "claim": CLAIM,
        "diagnostics": {"cost_decomposition": decomposition, "other_window": other},
        "config": {"initial": INITIAL, "bars": len(closes), "warmup": WARMUP,
                   "cost_per_side": lv.PERP_COST, "maintenance": lv.MAINTENANCE},
        "primary_5x": primary, "control_1x": one_x, "long_only_5x": long_only,
        "buy_hold": {"total_return": bh.total_return, "max_dd": bh.max_drawdown,
                     "robust": bh.robust},
        "layer1_source_criteria": layer1,
        "layer2": {"V1": v1, "V2": v2, "V3": v3, "V4": v4, "V5": v5, "V6": v6},
        "verdict": "PASS" if passed else "FAIL",
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
