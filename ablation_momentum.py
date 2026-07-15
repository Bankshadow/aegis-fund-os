"""Ablation: state-based momentum confirmation (v3.1).

Question: does refusing to fill buy levels DURING an active sell-off
(down-anomaly bar, or momentum < -entry_m_block) measurably improve the
system? Judged on held-out seeds with the deep metrics (CVaR, Profit
Factor, Recovery Factor), not just return.
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, SCENARIOS, generate_scenario, run_backtest
from compare_versions import V1_BEST

SEEDS = (7, 11, 13)   # held-out (never used for tuning)
N_BARS = 2000


def evaluate(cfg):
    """Per-scenario means across seeds for the full metric set."""
    rows = {}
    for name in SCENARIOS:
        rs = [run_backtest(generate_scenario(name, n_bars=N_BARS, seed=sd), cfg)
              for sd in SEEDS]
        rows[name] = dict(
            ret=float(np.mean([r.total_return for r in rs])),
            wdd=max(r.max_drawdown for r in rs),
            cvar=float(np.mean([r.cvar_5 for r in rs])),
            pf=float(np.mean([min(r.profit_factor, 99.0) for r in rs])),
            rf=float(np.mean([r.recovery_factor for r in rs])),
        )
    return rows


def show(tag, rows):
    print(f"\n--- {tag} ---")
    print(f"{'scenario':<15} {'ret':>8} {'wDD':>7} {'CVaR5%':>8} {'PF':>6} {'RF':>7}")
    for name, m in rows.items():
        print(f"{name:<15} {m['ret']*100:+7.2f}% {m['wdd']*100:6.2f}% "
              f"{m['cvar']*100:+7.3f}% {m['pf']:6.2f} {m['rf']:+7.2f}")
    mean_ret = np.mean([m["ret"] for m in rows.values()])
    mean_cvar = np.mean([m["cvar"] for m in rows.values()])
    mean_pf = np.mean([m["pf"] for m in rows.values()])
    print(f"{'MEAN':<15} {mean_ret*100:+7.2f}% {'':>7} {mean_cvar*100:+7.3f}% {mean_pf:6.2f}")
    return mean_ret


def main():
    base = dict(V1_BEST, use_regime=True)
    off = evaluate(DynamicGridConfig(**base, momentum_confirm=False))
    show("momentum_confirm = OFF (baseline v2)", off)
    for blk in (0.5, 1.0, 1.5):
        on = evaluate(DynamicGridConfig(**base, momentum_confirm=True,
                                        entry_m_block=blk))
        show(f"momentum_confirm = ON (entry_m_block={blk})", on)


if __name__ == "__main__":
    main()
