"""E19: Retrain RL governor on REAL BTC/4h only; judge on held-out test.

Criterion (declared BEFORE run):
  Primary: On BTCUSDT 4h test (last 40%), dual RL robust score
  (return - 2*maxDD) must STRICTLY exceed dual rule, AND RL must engage
  (n_scale_changes > 0).

  Secondary (report only): same fresh Q on bull 1d (load_binance_klines)
  vs dual rule — does not change the pass/fail gate.

Protocol:
  - Fresh Q via train_q_on_ohlc (never load results/q_table*.json)
  - Engines use use_regime_pct=True (scale-invariant state; E12 fix)
  - Dual 75/25 stack; grid params tuned on train with bias/router OFF
  - >=3 exploration seeds during Q training
  - Report negatives equally; do not claim live readiness
"""

import os

from dynamic_grid import DynamicGridConfig, run_backtest_engine, load_binance_klines
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.market_data import market_profile
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.rl_agent import (RLGovernor, policy_table, save_q,
                                   train_q_on_ohlc)
from multiasset_demo import BASE_FEE, N_ITER, tune

TRAIN_SEEDS = (0, 1, 2)
EPOCHS = 8
PCT = dict(use_regime=True, use_regime_pct=True, use_funding_bias=False,
           use_relative_value=False)


def robust(r):
    return r.total_return - 2.0 * r.max_drawdown


def make_cfg(params, profile) -> DynamicGridConfig:
    return DynamicGridConfig(
        **params, **PCT,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"],
        half_spread=0.0,
    )


def main():
    print("E19 criterion: dual RL robust > dual rule on BTC/4h held-out test")
    print("               AND n_scale_changes > 0 (engaged)")
    print("Fresh Q only — never loading synthetic q_table*.json\n")

    prof = market_profile("BTCUSDT", "4h")
    ohlc = prof["ohlc"]
    cut = int(len(ohlc) * 0.6)
    train, test = ohlc[:cut], ohlc[cut:]
    print(f"BTC/4h bars={len(ohlc)} train={len(train)} test={len(test)}")

    params = tune(train, prof, seed=0)
    cfg = make_cfg(params, prof)
    layers_fn = lambda: make_dual_layers(cfg)

    print(f"\n=== Training Q on REAL train window "
          f"(epochs={EPOCHS}, seeds={TRAIN_SEEDS}) ===")
    q = train_q_on_ohlc(layers_fn, train, epochs=EPOCHS, seeds=TRAIN_SEEDS,
                        verbose=True)
    os.makedirs("results", exist_ok=True)
    q_path = os.path.join("results", "q_table_real_e19.json")
    save_q(q, q_path)
    print(f"Saved audit copy (not a usage recommendation): {q_path}")
    print("\n=== Learned policy ===")
    print(policy_table(q))

    print("\n=== Primary: BTC/4h held-out test ===")
    rule = MemoryOrchestrator(make_dual_layers(cfg))
    rl = RLGovernor(make_dual_layers(cfg), q=q, learn=False)
    r_rule = run_backtest_engine(test, rule, liquidate_at_end=True)
    r_rl = run_backtest_engine(test, rl, liquidate_at_end=True)
    s_rule, s_rl = robust(r_rule), robust(r_rl)
    print(f"  dual rule  ret {r_rule.total_return*100:+7.2f}%  "
          f"DD {r_rule.max_drawdown*100:6.2f}%  robust {s_rule:+.4f}")
    print(f"  dual RL    ret {r_rl.total_return*100:+7.2f}%  "
          f"DD {r_rl.max_drawdown*100:6.2f}%  robust {s_rl:+.4f}  "
          f"scale_changes={rl.n_scale_changes}")

    primary_ok = (s_rl > s_rule) and (rl.n_scale_changes > 0)
    print(f"\nPrimary gate: {'PASS' if primary_ok else 'FAIL'} "
          f"(RL robust {'>' if s_rl > s_rule else '<='} rule; "
          f"engaged={rl.n_scale_changes > 0})")

    print("\n=== Secondary (report only): bull 1d, same Q, no retrain ===")
    bull = load_binance_klines()
    # Bull 1d has different vol scale; use same fee bake from BTC 4h profile
    # only for cost continuity — secondary is diagnostic, not the gate.
    rule_b = MemoryOrchestrator(make_dual_layers(cfg))
    rl_b = RLGovernor(make_dual_layers(cfg), q=q, learn=False)
    rb = run_backtest_engine(bull, rule_b, liquidate_at_end=True)
    rlb = run_backtest_engine(bull, rl_b, liquidate_at_end=True)
    print(f"  dual rule  ret {rb.total_return*100:+7.2f}%  "
          f"DD {rb.max_drawdown*100:6.2f}%  robust {robust(rb):+.4f}")
    print(f"  dual RL    ret {rlb.total_return*100:+7.2f}%  "
          f"DD {rlb.max_drawdown*100:6.2f}%  robust {robust(rlb):+.4f}  "
          f"scale_changes={rl_b.n_scale_changes}")
    if robust(rlb) <= robust(rb):
        print("  note: RL does not beat rule on bull 1d "
              "(cross-TF transfer still weak — expected risk per E12)")

    if primary_ok:
        print("\nE19 PASS — still not a live-trading recommendation")
    else:
        print("\nE19 FAIL — keep 'do not use RL' policy in HANDOFF")


if __name__ == "__main__":
    main()
