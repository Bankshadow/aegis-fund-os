"""Held-out validation: tuned regime config vs v1, on seeds not used for tuning."""

from dynamic_grid import DynamicGridConfig
from compare_versions import V1_BEST, evaluate, SCENARIOS

# regime params tuned on seeds (1, 2); validated here on seeds (7, 11, 13)
V2_REGIME = dict(regime_m_threshold=0.61, regime_vol_hi=1.75,
                 hv_risk_scale=0.346, hv_spacing_scale=1.841,
                 up_risk_scale=0.853)


def main():
    v1 = evaluate(DynamicGridConfig(**V1_BEST, use_regime=False))
    v2 = evaluate(DynamicGridConfig(**V1_BEST, use_regime=True, **V2_REGIME))
    print(f"{'scenario':<15} {'v1 ret':>8} {'v1 wDD':>7}   {'v2 ret':>8} {'v2 wDD':>7}")
    print("-" * 54)
    m1 = m2 = 0.0
    for s in SCENARIOS:
        r1, d1 = v1[s]
        r2, d2 = v2[s]
        m1 += r1
        m2 += r2
        print(f"{s:<15} {r1*100:+7.2f}% {d1*100:6.2f}%   "
              f"{r2*100:+7.2f}% {d2*100:6.2f}%")
    print("-" * 54)
    print(f"{'mean return':<15} {m1/6*100:+7.2f}% {'':>7}   {m2/6*100:+7.2f}%")


if __name__ == "__main__":
    main()
