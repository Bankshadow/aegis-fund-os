"""Persistent regime router for long/short grid sleeves.

The router does not forecast returns.  It decides which sleeve is allowed to
add inventory and how much risk budget it receives.  Existing inventory is
always managed to TP/stop even after its sleeve is disabled.

Optional funding bias (E17): when ``use_funding_bias`` is on and a
``funding_series`` is supplied, extreme funding tilts sleeves only while
the regime is sideways — it does not override confirmed trends.

Optional relative value (E18): when ``use_relative_value`` is on and a
``relative_series`` (log-ratio momentum vs numeraire) is supplied, that
signal REPLACES own-price direction for sleeve routing. Own-price detector
still drives high_vol risk scaling.
"""

import numpy as np

from .grid_engine import DynamicGridConfig, DynamicGridEngine
from .short_engine import ShortGridEngine
from .signals import FundingBiasModel, RegimeSignalModel, RelativeStrengthModel


class RegimeSwitchingOrchestrator:
    """Route risk between long, short, and balanced range modes."""

    def __init__(self, long_cfg: DynamicGridConfig,
                 short_cfg: DynamicGridConfig | None = None,
                 range_long_weight: float = 0.5,
                 high_vol_risk_scale: float = 0.25,
                 allocator=None,
                 funding_series: np.ndarray | None = None,
                 relative_series: np.ndarray | None = None):
        short_cfg = short_cfg or long_cfg
        self.long = DynamicGridEngine(long_cfg)
        self.short = ShortGridEngine(short_cfg)
        self.engines = [self.long, self.short]
        self.range_long_weight = min(max(range_long_weight, 0.0), 1.0)
        self.high_vol_risk_scale = min(max(high_vol_risk_scale, 0.0), 1.0)
        # Same factory as long/short engines: use_regime_pct > use_regime_2d.
        self.signal_model = RegimeSignalModel(cfg=long_cfg)
        self.detector = self.signal_model.detector  # compatibility diagnostics
        self.allocator = allocator
        self.direction_counts = {"sideways": 0, "trend_up": 0,
                                 "trend_down": 0}
        self.high_vol_bars = 0
        self.bar_idx = -1
        self.n_funding_tilts = 0
        self.n_relative_tilts = 0
        self.funding_series = (None if funding_series is None
                               else np.asarray(funding_series, dtype=float))
        self.relative_series = (None if relative_series is None
                                else np.asarray(relative_series, dtype=float))
        self.use_funding_bias = bool(getattr(long_cfg, "use_funding_bias", False))
        self.use_relative_value = bool(
            getattr(long_cfg, "use_relative_value", False))
        self.funding_bias = None
        if self.use_funding_bias:
            self.funding_bias = FundingBiasModel(
                pct_window=getattr(long_cfg, "funding_pct_window", 90),
                extreme_pct=getattr(long_cfg, "funding_extreme_pct", 0.85))
        self.relative_model = None
        if self.use_relative_value:
            self.relative_model = RelativeStrengthModel(
                pct_window=getattr(long_cfg, "relative_pct_window", 90),
                extreme_pct=getattr(long_cfg, "relative_extreme_pct", 0.85))

    @staticmethod
    def _set_enabled(engine, enabled: bool) -> None:
        was_enabled = engine.entries_enabled
        engine.entries_enabled = enabled
        # A flat zone that sat disabled may be far from the market. Rebuild
        # from current information when the sleeve becomes active again.
        if enabled and not was_enabled and not engine.lots:
            engine.center = None
            engine.levels = []
            engine.cooldown = 0

    def on_bar(self, o, h, l, c, equity):
        self.bar_idx += 1
        signal = self.signal_model.update(h, l, c)
        direction = signal.direction
        # E18: relative strength replaces own-price direction for routing.
        if (self.use_relative_value and self.relative_model is not None
                and self.relative_series is not None
                and 0 <= self.bar_idx < len(self.relative_series)):
            rel = self.relative_model.update(
                float(self.relative_series[self.bar_idx]))
            if rel.direction != direction:
                self.n_relative_tilts += 1
            direction = rel.direction

        self.direction_counts[direction] = (
            self.direction_counts.get(direction, 0) + 1)
        if self.detector.volatility == "high_vol":
            self.high_vol_bars += 1
        risk_scale = (self.high_vol_risk_scale
                      if self.detector.volatility == "high_vol" else 1.0)

        if direction == "trend_up":
            long_w, short_w = 1.0, 0.0
        elif direction == "trend_down":
            long_w, short_w = 0.0, 1.0
        else:
            long_w = self.range_long_weight
            short_w = 1.0 - long_w

        # Funding tilt only in sideways — never override confirmed trend.
        # E18 keeps funding off in demos; left here for opt-in experiments.
        if (self.use_funding_bias and self.funding_bias is not None
                and self.funding_series is not None
                and 0 <= self.bar_idx < len(self.funding_series)):
            bias = self.funding_bias.update(
                float(self.funding_series[self.bar_idx]))
            if direction == "sideways" and bias.value != 0.0:
                if bias.value > 0.0:   # favor long
                    long_w, short_w = 1.0, 0.0
                else:                  # favor short
                    long_w, short_w = 0.0, 1.0
                self.n_funding_tilts += 1

        if self.allocator is not None:
            weights = self.allocator.weights(
                {"long": long_w > 0.0, "short": short_w > 0.0},
                {"long": long_w, "short": short_w})
            long_w, short_w = weights["long"], weights["short"]

        self._set_enabled(self.long, long_w > 0.0)
        self._set_enabled(self.short, short_w > 0.0)
        long_equity = equity * long_w * risk_scale
        short_equity = equity * short_w * risk_scale
        long_pnl = self.long.on_bar(o, h, l, c, long_equity)
        short_pnl = self.short.on_bar(o, h, l, c, short_equity)
        if self.allocator is not None:
            self.allocator.record("long", long_pnl, long_equity)
            self.allocator.record("short", short_pnl, short_equity)
        return long_pnl + short_pnl

    def unrealized(self, price):
        return self.long.unrealized(price) + self.short.unrealized(price)

    def exposure(self, price):
        return self.long.exposure(price) + self.short.exposure(price)

    def liquidate(self, price):
        return self.long.liquidate(price) + self.short.liquidate(price)

    @property
    def n_tp(self): return self.long.n_tp + self.short.n_tp
    @property
    def n_stopouts(self): return self.long.n_stopouts + self.short.n_stopouts
    @property
    def n_rebuilds(self): return self.long.n_rebuilds + self.short.n_rebuilds
    @property
    def n_consolidations(self):
        return self.long.n_consolidations + self.short.n_consolidations
    @property
    def gross_profit(self):
        return self.long.gross_profit + self.short.gross_profit
    @property
    def gross_loss(self):
        return self.long.gross_loss + self.short.gross_loss
