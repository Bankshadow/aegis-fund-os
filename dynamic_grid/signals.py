"""Portable, deterministic signal contracts for the strategy layer.

Signals describe a market view. They never size an order, override a risk
limit, or call an execution engine.
"""

from dataclasses import dataclass, field

from .regime import (PercentileRegimeDetector, PersistentRegimeDetector,
                     build_detector)


@dataclass(frozen=True)
class StrategySignal:
    """A normalized strategy view plus enough context to audit it."""

    name: str
    value: float
    confidence: float
    direction: str
    volatility: str
    rationale: str
    metadata: dict[str, float | str] = field(default_factory=dict)

    def __post_init__(self):
        if not -1.0 <= self.value <= 1.0:
            raise ValueError("StrategySignal.value must be in [-1, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("StrategySignal.confidence must be in [0, 1]")


class RegimeSignalModel:
    """Turn a regime detector (via build_detector) into a common signal.

    Prefer ``RegimeSignalModel(cfg=long_cfg)`` so the router uses the same
    factory as DynamicGridEngine / ShortGridEngine (percentile > 2d > legacy).
    The ``**detector_kwargs`` path remains for backward-compatible tests.
    """

    def __init__(self, cfg=None, **detector_kwargs):
        if cfg is not None:
            if (getattr(cfg, "use_regime_pct", False)
                    or getattr(cfg, "use_regime_2d", False)):
                self.detector = build_detector(cfg)
            else:
                # Router needs direction/volatility; default to persistent 2d.
                self.detector = PersistentRegimeDetector(
                    m_threshold=cfg.regime_m_threshold,
                    vol_hi=cfg.regime_vol_hi,
                    confirm_bars=cfg.regime_confirm_bars,
                    min_dwell_bars=cfg.regime_min_dwell_bars,
                    hysteresis=cfg.regime_hysteresis)
        else:
            self.detector = PersistentRegimeDetector(**detector_kwargs)

    def update(self, high: float, low: float, close: float) -> StrategySignal:
        self.detector.update(high, low, close)
        direction = self.detector.direction
        value = {"trend_up": 1.0, "trend_down": -1.0}.get(direction, 0.0)
        high_vol = self.detector.volatility == "high_vol"
        confidence = 0.5 if direction == "sideways" else 0.85
        if high_vol:
            confidence *= 0.6
        kind = ("percentile_regime"
                if isinstance(self.detector, PercentileRegimeDetector)
                else "persistent_regime")
        return StrategySignal(
            name=kind, value=value, confidence=confidence,
            direction=direction, volatility=self.detector.volatility,
            rationale=f"{kind} {direction}; volatility={self.detector.volatility}",
            metadata={"momentum": self.detector.momentum,
                      "vol_ratio": self.detector.vol_ratio},
        )


class FundingBiasModel:
    """Percentile-rank funding bias: extreme crowding leans the other way.

    Positive funding (longs pay) at a high percentile -> short bias (-1).
    Negative funding (longs receive) at a low percentile -> long bias (+1).
    Mid-range -> neutral (0). Ranking uses only the trailing history
    (append after rank) so there is no lookahead.
    """

    def __init__(self, pct_window: int = 90, extreme_pct: float = 0.85):
        self.pct_window = max(int(pct_window), 20)
        self.extreme_pct = min(max(float(extreme_pct), 0.5), 0.99)
        self._hist: list[float] = []
        self.last_rate: float = 0.0
        self.last_rank: float = 0.5

    @staticmethod
    def _rank(history: list[float], value: float) -> float:
        if len(history) < 20:
            return 0.5
        # Flat history has no crowding signal — stay neutral.
        if max(history) - min(history) < 1e-15:
            return 0.5
        return sum(1 for x in history if x <= value) / len(history)

    def update(self, funding_rate: float) -> StrategySignal:
        self.last_rate = float(funding_rate)
        rank = self._rank(self._hist, self.last_rate)
        self.last_rank = rank
        self._hist.append(self.last_rate)
        if len(self._hist) > self.pct_window:
            self._hist.pop(0)

        lo = 1.0 - self.extreme_pct
        if rank >= self.extreme_pct:
            value, direction = -1.0, "short_bias"
            rationale = "extreme positive funding; longs overcrowded -> favor short"
        elif rank <= lo:
            value, direction = 1.0, "long_bias"
            rationale = "extreme negative funding; shorts overcrowded -> favor long"
        else:
            value, direction = 0.0, "neutral"
            rationale = "funding not extreme; no directional tilt"

        confidence = 0.85 if value != 0.0 else 0.4
        return StrategySignal(
            name="funding_bias", value=value, confidence=confidence,
            direction=direction, volatility="normal",
            rationale=rationale,
            metadata={"funding_rate": self.last_rate, "funding_rank": rank},
        )


class RelativeStrengthModel:
    """Percentile-rank relative strength vs a numeraire (e.g. SOL/BTC).

    Input is precomputed log-ratio momentum
    ``mom = log(alt/btc)_t - log(alt/btc)_{t-lookback}``.
    High rank -> alt outperforming -> trend_up; low rank -> trend_down.
    """

    def __init__(self, pct_window: int = 90, extreme_pct: float = 0.85):
        self.pct_window = max(int(pct_window), 20)
        self.extreme_pct = min(max(float(extreme_pct), 0.5), 0.99)
        self._hist: list[float] = []
        self.last_mom: float = 0.0
        self.last_rank: float = 0.5

    @staticmethod
    def _rank(history: list[float], value: float) -> float:
        if len(history) < 20:
            return 0.5
        if max(history) - min(history) < 1e-15:
            return 0.5
        return sum(1 for x in history if x <= value) / len(history)

    def update(self, momentum: float) -> StrategySignal:
        self.last_mom = float(momentum)
        rank = self._rank(self._hist, self.last_mom)
        self.last_rank = rank
        self._hist.append(self.last_mom)
        if len(self._hist) > self.pct_window:
            self._hist.pop(0)

        lo = 1.0 - self.extreme_pct
        if rank >= self.extreme_pct:
            value, direction = 1.0, "trend_up"
            rationale = "alt outperforming numeraire (high relative momentum)"
        elif rank <= lo:
            value, direction = -1.0, "trend_down"
            rationale = "alt underperforming numeraire (low relative momentum)"
        else:
            value, direction = 0.0, "sideways"
            rationale = "relative momentum not extreme"

        confidence = 0.85 if value != 0.0 else 0.45
        return StrategySignal(
            name="relative_strength", value=value, confidence=confidence,
            direction=direction, volatility="normal",
            rationale=rationale,
            metadata={"rel_momentum": self.last_mom, "rel_rank": rank},
        )
