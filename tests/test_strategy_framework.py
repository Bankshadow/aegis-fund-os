import unittest
from types import SimpleNamespace

import numpy as np

from dynamic_grid.allocator import RiskBudgetAllocator
from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.grid_engine import (DynamicGridConfig, DynamicGridEngine,
                                     has_positive_edge, round_trip_cost_frac)
from dynamic_grid.regime import PercentileRegimeDetector, PersistentRegimeDetector
from dynamic_grid.regime_switch import RegimeSwitchingOrchestrator
from dynamic_grid.research import (ExecutionProfile, MultiStrategyResearchFramework,
                                   ResearchDataset, default_strategies)
from dynamic_grid.core_engine import CoreTradingEngine
from dynamic_grid.research import PromotionDecision
from dynamic_grid.short_engine import ShortGridEngine
from dynamic_grid.rl_agent import RLGovernor, train_q_on_ohlc
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.signals import (FundingBiasModel, RegimeSignalModel,
                                   RelativeStrengthModel, StrategySignal)
from dynamic_grid.market_data import align_funding_to_bars, pair_ratio_series
from dynamic_grid.validation import ValidationGate, combinatorial_purged_screen
from rl_walkforward_demo import iter_walkforward_folds


class StrategyFrameworkTests(unittest.TestCase):
    def test_signal_contract_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            StrategySignal("bad", 1.1, 0.5, "trend_up", "normal", "bad")

    def test_allocator_respects_regime_eligibility_and_weight_cap(self):
        allocator = RiskBudgetAllocator({"long": 0.9, "short": 0.1},
                                        max_weight=0.70, lookback=2)
        allocator.record("long", 100.0, 1_000.0)
        weights = allocator.weights({"long": True, "short": True})
        self.assertLessEqual(weights["long"], 0.70)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        directional = allocator.weights({"long": True, "short": False})
        self.assertEqual(directional, {"long": 1.0, "short": 0.0})

    def test_purged_screen_and_gate_accept_stable_candidate(self):
        ohlc = np.zeros((60, 4))
        stable = lambda _: SimpleNamespace(total_return=0.08, max_drawdown=0.01)
        weak = lambda _: SimpleNamespace(total_return=-0.02, max_drawdown=0.03)
        report = combinatorial_purged_screen(
            ohlc, {"stable": stable, "weak": weak}, n_groups=6,
            n_test_groups=2, purge_groups=0)
        self.assertGreaterEqual(len(report.folds), 3)
        self.assertEqual(report.selection_failure_rate, 0.0)
        self.assertTrue(ValidationGate().passes(report))

    def test_router_accepts_optional_allocator(self):
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],
            [100.0, 100.0, 98.0, 99.0],
            [99.0, 100.0, 97.0, 98.0],
        ])
        cfg = DynamicGridConfig(atr_period=1, levels=1, use_regime=False)
        engine = RegimeSwitchingOrchestrator(
            cfg, allocator=RiskBudgetAllocator({"long": 0.5, "short": 0.5}))
        result = run_backtest_engine(bars, engine)
        self.assertTrue(np.isfinite(result.final_equity))

    def test_research_framework_keeps_benchmark_and_rejects_it_for_paper(self):
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],
            [100.0, 100.0, 98.0, 99.0],
            [99.0, 100.0, 97.0, 98.0],
            [98.0, 99.0, 96.0, 97.0],
            [97.0, 98.0, 95.0, 96.0],
            [96.0, 97.0, 94.0, 95.0],
        ])
        dataset = ResearchDataset("TEST", "4h", bars)
        framework = MultiStrategyResearchFramework(
            default_strategies(), execution=ExecutionProfile())
        run = framework.run((dataset,), DynamicGridConfig(atr_period=1, levels=1,
                            use_regime_pct=True), n_groups=3, n_test_groups=2,
                            purge_groups=0)
        self.assertEqual(len(run.results), 5)
        self.assertIn(run.promotion.selected_strategy,
                      {"cash", "buy_hold", "regime_router", "regime_allocator",
                       "dual_pct"})
        if run.promotion.selected_strategy in {"cash", "buy_hold"}:
            self.assertFalse(run.promotion.eligible_for_paper)

    def test_execution_profile_carries_spread_and_funding_into_config(self):
        dataset = ResearchDataset("TEST", "4h", np.zeros((6, 4)),
                                  half_spread=0.001, funding_per_bar=0.00001)
        cfg = ExecutionProfile(extra_stop_slippage_bps=5.0).apply(
            DynamicGridConfig(), dataset)
        self.assertEqual(cfg.funding_rate_per_bar, 0.00001)
        self.assertEqual(cfg.stop_slippage_bps, 15.0)
        self.assertEqual(cfg.half_spread, 0.001)
        self.assertTrue(cfg.conservative_intrabar)

    def test_core_engine_fails_closed_without_research_approval(self):
        bars = np.array([[100.0, 101.0, 99.0, 100.0]])
        core = CoreTradingEngine(DynamicGridConfig(), PromotionDecision(
            "regime_router", False, ("validation failed",)))
        result = run_backtest_engine(bars, core, liquidate_at_end=True)
        self.assertEqual(core.status.mode, "cash")
        self.assertEqual(result.total_return, 0.0)

    def test_core_engine_activates_only_an_approved_deterministic_strategy(self):
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],
            [100.0, 100.0, 98.0, 99.0],
            [99.0, 100.0, 97.0, 98.0],
        ])
        core = CoreTradingEngine(DynamicGridConfig(atr_period=1, levels=1),
            PromotionDecision("regime_allocator", True, ("passed",)))
        result = run_backtest_engine(bars, core)
        self.assertEqual(core.status.mode, "active")
        self.assertTrue(np.isfinite(result.final_equity))
        self.assertTrue(core.config.use_regime_pct)
        self.assertIsInstance(core.engine.signal_model.detector,
                              PercentileRegimeDetector)

    def test_core_engine_activates_dual_pct_when_approved(self):
        from dynamic_grid.orchestrator_agent import MemoryOrchestrator
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],
            [100.0, 100.0, 98.0, 99.0],
            [99.0, 100.0, 97.0, 98.0],
        ])
        core = CoreTradingEngine(DynamicGridConfig(atr_period=1, levels=1),
            PromotionDecision("dual_pct", True, ("passed",)))
        result = run_backtest_engine(bars, core)
        self.assertEqual(core.status.mode, "active")
        self.assertEqual(core.strategy_name, "dual_pct")
        self.assertIsInstance(core.engine, MemoryOrchestrator)
        self.assertTrue(core.config.use_regime_pct)
        self.assertTrue(np.isfinite(result.final_equity))
        names = {s.name for s in default_strategies()}
        self.assertIn("dual_pct", names)

    def test_signal_model_uses_percentile_detector_from_config(self):
        pct = RegimeSignalModel(cfg=DynamicGridConfig(use_regime_pct=True))
        self.assertIsInstance(pct.detector, PercentileRegimeDetector)
        fixed = RegimeSignalModel(cfg=DynamicGridConfig(use_regime_2d=True))
        self.assertIsInstance(fixed.detector, PersistentRegimeDetector)
        self.assertNotIsInstance(fixed.detector, PercentileRegimeDetector)
        router = RegimeSwitchingOrchestrator(
            DynamicGridConfig(use_regime_pct=True, atr_period=1, levels=1))
        self.assertIsInstance(router.signal_model.detector,
                              PercentileRegimeDetector)
        signal = pct.update(101.0, 99.0, 100.0)
        self.assertEqual(signal.name, "percentile_regime")

    def test_round_trip_and_edge_helpers(self):
        cfg = DynamicGridConfig(fee_rate=0.001, half_spread=0.0005,
                                tp_mult=1.0, edge_min_multiple=1.0)
        self.assertAlmostEqual(round_trip_cost_frac(cfg), 0.003)
        # spacing/price = 0.002 < rt 0.003 -> no edge
        self.assertFalse(has_positive_edge(100.0, 0.2, cfg))
        # spacing/price = 0.004 > rt 0.003 -> edge ok
        self.assertTrue(has_positive_edge(100.0, 0.4, cfg))

    def test_require_edge_skips_negative_ev_zone_long_and_short(self):
        # Tiny ATR vs huge fees: TP cannot cover round-trip.
        bars = np.array([
            [100.0, 100.1, 99.9, 100.0],
            [100.0, 100.1, 99.9, 100.0],
            [100.0, 100.1, 99.9, 100.0],
        ])
        bad = DynamicGridConfig(
            atr_period=1, atr_mult=0.1, levels=1, use_regime=False,
            require_edge=True, fee_rate=0.05, half_spread=0.0,
            tp_mult=1.0, cooldown_bars=0, trend_k=100.0)
        long_eng = DynamicGridEngine(bad)
        short_eng = ShortGridEngine(bad)
        run_backtest_engine(bars, long_eng)
        run_backtest_engine(bars, short_eng)
        self.assertIsNone(long_eng.center)
        self.assertGreaterEqual(long_eng.n_edge_skips, 1)
        self.assertEqual(long_eng.n_rebuilds, 0)
        self.assertIsNone(short_eng.center)
        self.assertGreaterEqual(short_eng.n_edge_skips, 1)
        self.assertEqual(short_eng.n_rebuilds, 0)

    def test_require_edge_builds_when_tp_covers_costs(self):
        bars = np.array([
            [100.0, 105.0, 95.0, 100.0],
            [100.0, 105.0, 95.0, 100.0],
            [100.0, 105.0, 95.0, 100.0],
            [100.0, 105.0, 95.0, 100.0],
        ])
        good = DynamicGridConfig(
            atr_period=1, atr_mult=1.0, levels=1, use_regime=False,
            require_edge=True, fee_rate=0.0005, half_spread=0.0,
            tp_mult=1.0, cooldown_bars=0, trend_k=100.0)
        eng = DynamicGridEngine(good)
        run_backtest_engine(bars, eng)
        self.assertIsNotNone(eng.center)
        self.assertGreaterEqual(eng.n_rebuilds, 1)
        self.assertEqual(eng.n_edge_skips, 0)

    def test_require_edge_default_off_preserves_build(self):
        bars = np.array([
            [100.0, 100.1, 99.9, 100.0],
            [100.0, 100.1, 99.9, 100.0],
            [100.0, 100.1, 99.9, 100.0],
        ])
        # Same tiny spacing as the skip test, but require_edge=False (default).
        cfg = DynamicGridConfig(
            atr_period=1, atr_mult=0.1, levels=1, use_regime=False,
            fee_rate=0.05, cooldown_bars=0, trend_k=100.0)
        self.assertFalse(cfg.require_edge)
        eng = DynamicGridEngine(cfg)
        run_backtest_engine(bars, eng)
        self.assertIsNotNone(eng.center)
        self.assertEqual(eng.n_edge_skips, 0)
        self.assertGreaterEqual(eng.n_rebuilds, 1)

    def test_funding_bias_polarity_percentile(self):
        model = FundingBiasModel(pct_window=40, extreme_pct=0.85)
        # Warm history with mid rates so extremes can fire.
        for rate in np.linspace(-0.0001, 0.0001, 30):
            model.update(float(rate))
        short_sig = model.update(0.001)   # well above history
        self.assertEqual(short_sig.value, -1.0)
        self.assertEqual(short_sig.direction, "short_bias")
        long_sig = model.update(-0.001)   # well below history
        self.assertEqual(long_sig.value, 1.0)
        self.assertEqual(long_sig.direction, "long_bias")
        # Flat history -> neutral (no crowding signal).
        flat = FundingBiasModel(pct_window=40, extreme_pct=0.85)
        for _ in range(30):
            mid = flat.update(0.0)
        self.assertEqual(mid.value, 0.0)
        self.assertEqual(mid.direction, "neutral")

    def test_align_funding_to_bars_no_lookahead(self):
        events = [
            {"fundingTime": 1000, "fundingRate": "0.01"},
            {"fundingTime": 3000, "fundingRate": "0.02"},
        ]
        bars = np.array([500, 1000, 2000, 3000, 4000], dtype=np.int64)
        series = align_funding_to_bars(bars, events)
        np.testing.assert_allclose(series, [0.0, 0.01, 0.01, 0.02, 0.02])

    def test_router_funding_tilt_engages_in_sideways(self):
        # Flat bars keep regime sideways; extreme funding should tilt.
        bars = np.tile([100.0, 100.2, 99.8, 100.0], (50, 1))
        # Build a funding series that is mid then extreme positive.
        funding = np.zeros(50)
        funding[:25] = 0.0
        funding[25:] = 0.01
        cfg = DynamicGridConfig(
            atr_period=1, levels=1, use_regime=True, use_regime_pct=True,
            use_funding_bias=True, funding_pct_window=30,
            funding_extreme_pct=0.85, block_high_vol_entries=False,
            cooldown_bars=0, trend_k=100.0)
        router = RegimeSwitchingOrchestrator(
            cfg, range_long_weight=0.5, funding_series=funding)
        run_backtest_engine(bars, router)
        self.assertGreater(router.n_funding_tilts, 0)

    def test_funding_bias_default_off_no_tilts(self):
        bars = np.tile([100.0, 100.2, 99.8, 100.0], (30, 1))
        funding = np.full(30, 0.01)
        cfg = DynamicGridConfig(atr_period=1, levels=1, use_regime_pct=True)
        self.assertFalse(cfg.use_funding_bias)
        router = RegimeSwitchingOrchestrator(cfg, funding_series=funding)
        run_backtest_engine(bars, router)
        self.assertEqual(router.n_funding_tilts, 0)

    def test_relative_strength_polarity(self):
        model = RelativeStrengthModel(pct_window=40, extreme_pct=0.85)
        for mom in np.linspace(-0.01, 0.01, 30):
            model.update(float(mom))
        up = model.update(0.05)
        self.assertEqual(up.direction, "trend_up")
        self.assertEqual(up.value, 1.0)
        down = model.update(-0.05)
        self.assertEqual(down.direction, "trend_down")
        self.assertEqual(down.value, -1.0)
        flat = RelativeStrengthModel(pct_window=40, extreme_pct=0.85)
        for _ in range(30):
            mid = flat.update(0.0)
        self.assertEqual(mid.direction, "sideways")

    def test_pair_ratio_series_momentum_no_lookahead(self):
        pair = pair_ratio_series("ETHUSDT", "BTCUSDT", "4h", lookback=20)
        self.assertEqual(len(pair["momentum"]), len(pair["ratio"]))
        self.assertTrue(np.allclose(pair["momentum"][:20], 0.0))
        # momentum at t uses only ratio[t] and ratio[t-20]
        t = 50
        expected = (np.log(pair["ratio"][t]) - np.log(pair["ratio"][t - 20]))
        self.assertAlmostEqual(pair["momentum"][t], expected)

    def test_router_relative_value_replaces_direction(self):
        bars = np.tile([100.0, 100.2, 99.8, 100.0], (60, 1))
        # Strong positive relative momentum after warm-up -> trend_up routing.
        rel = np.zeros(60)
        rel[:30] = 0.0
        rel[30:] = 0.05
        cfg = DynamicGridConfig(
            atr_period=1, levels=1, use_regime=True, use_regime_pct=True,
            use_relative_value=True, relative_pct_window=30,
            relative_extreme_pct=0.85, cooldown_bars=0, trend_k=100.0)
        router = RegimeSwitchingOrchestrator(
            cfg, range_long_weight=0.5, relative_series=rel)
        run_backtest_engine(bars, router)
        self.assertGreater(router.n_relative_tilts, 0)
        self.assertGreater(router.direction_counts.get("trend_up", 0), 0)

    def test_relative_value_default_off(self):
        bars = np.tile([100.0, 100.2, 99.8, 100.0], (30, 1))
        rel = np.full(30, 0.05)
        cfg = DynamicGridConfig(atr_period=1, levels=1, use_regime_pct=True)
        self.assertFalse(cfg.use_relative_value)
        router = RegimeSwitchingOrchestrator(cfg, relative_series=rel)
        run_backtest_engine(bars, router)
        self.assertEqual(router.n_relative_tilts, 0)

    def test_train_q_on_ohlc_real_bars_only(self):
        bars = np.tile([100.0, 101.0, 99.0, 100.0], (120, 1)).astype(float)
        # Mild drift so equity windows are non-trivial.
        bars[:, 3] = 100.0 + np.linspace(0, 2, len(bars))
        bars[:, 0] = bars[:, 3]
        bars[:, 1] = bars[:, 3] + 1.0
        bars[:, 2] = bars[:, 3] - 1.0
        cfg = DynamicGridConfig(
            atr_period=5, levels=2, use_regime=True, use_regime_pct=True,
            cooldown_bars=0)
        q = train_q_on_ohlc(lambda: make_dual_layers(cfg), bars,
                            epochs=2, seeds=(0, 1, 2), verbose=False)
        self.assertEqual(q.shape, (12, 3))
        self.assertTrue(np.isfinite(q).all())
        with self.assertRaises(ValueError):
            train_q_on_ohlc(lambda: make_dual_layers(cfg), bars,
                            epochs=1, seeds=(0, 1), verbose=False)

    def test_rl_governor_counts_scale_changes(self):
        bars = np.tile([100.0, 101.0, 99.0, 100.0], (80, 1)).astype(float)
        cfg = DynamicGridConfig(atr_period=5, levels=1, use_regime_pct=True,
                                cooldown_bars=0)
        # Force non-uniform Q so greedy policy can change scale.
        q = np.zeros((12, 3))
        q[:, 0] = 1.0   # prefer scale 0.25
        gov = RLGovernor(make_dual_layers(cfg), q=q, learn=False,
                         review_every=10)
        run_backtest_engine(bars, gov)
        self.assertGreaterEqual(gov.n_scale_changes, 1)

    def test_iter_walkforward_folds_indices(self):
        folds = iter_walkforward_folds(2000, 800, 200, 200)
        self.assertEqual(len(folds), 6)
        self.assertEqual(folds[0], (0, 800, 800, 1000))
        self.assertEqual(folds[-1], (1000, 1800, 1800, 2000))
        for ts, te, vs, ve in folds:
            self.assertEqual(te - ts, 800)
            self.assertEqual(ve - vs, 200)
            self.assertEqual(vs, te)
            self.assertLessEqual(ve, 2000)
        self.assertEqual(iter_walkforward_folds(1000, 800, 200, 200),
                         [(0, 800, 800, 1000)])
        with self.assertRaises(ValueError):
            iter_walkforward_folds(100, 0, 10, 10)


if __name__ == "__main__":
    unittest.main()
