"""Market regime detection (streaming, no lookahead).

Classifies each bar into one of four regimes using two signals:

  momentum m = (EMA_fast - EMA_slow) / ATR     ... ทิศทาง/ความชันของตลาด
  vol ratio v = ATR_fast / ATR_slow            ... ความผันผวนกำลังเร่งหรือสงบ

  v > vol_hi                -> "high_vol"   (ผันผวนเร่งผิดปกติ)
  m > m_threshold           -> "trend_up"
  m < -m_threshold          -> "trend_down"
  otherwise                 -> "sideways"

The grid engine uses the regime to scale risk budget and grid spacing at
zone-construction time, and to refuse building against a strong downtrend.
"""

from .indicators import ATR


class RegimeDetector:
    def __init__(self, ema_fast: int = 20, ema_slow: int = 60,
                 atr_fast: int = 10, atr_slow: int = 50,
                 m_threshold: float = 0.5, vol_hi: float = 1.4):
        self.m_threshold = m_threshold
        self.vol_hi = vol_hi
        self._kf = 2.0 / (ema_fast + 1)
        self._ks = 2.0 / (ema_slow + 1)
        self._ema_f: float | None = None
        self._ema_s: float | None = None
        self.atr_f = ATR(atr_fast)
        self.atr_s = ATR(atr_slow)
        self.regime: str = "sideways"
        self.momentum: float = 0.0
        self.vol_ratio: float = 1.0

    def update(self, high: float, low: float, close: float) -> str:
        if self._ema_f is None:
            self._ema_f = self._ema_s = close
        else:
            self._ema_f += self._kf * (close - self._ema_f)
            self._ema_s += self._ks * (close - self._ema_s)
        self.atr_f.update(high, low, close)
        self.atr_s.update(high, low, close)

        if self.atr_s.value is None or self.atr_s.value <= 0:
            return self.regime  # not warmed up yet -> keep default

        self.momentum = (self._ema_f - self._ema_s) / self.atr_s.value
        self.vol_ratio = ((self.atr_f.value or self.atr_s.value)
                          / self.atr_s.value)

        if self.vol_ratio > self.vol_hi:
            self.regime = "high_vol"
        elif self.momentum > self.m_threshold:
            self.regime = "trend_up"
        elif self.momentum < -self.m_threshold:
            self.regime = "trend_down"
        else:
            self.regime = "sideways"
        return self.regime


class PersistentRegimeDetector(RegimeDetector):
    """Two-dimensional regime detector with confirmation and hysteresis.

    Direction and volatility are deliberately independent.  A market can
    therefore be both ``trend_down`` and ``high_vol``; the legacy detector
    collapsed those conditions into one label and high volatility masked the
    directional risk.  ``regime`` remains backward-compatible for logging and
    old governors, while engines can consume ``direction`` and ``volatility``.

    State changes need ``confirm_bars`` consecutive observations and must
    survive ``min_dwell_bars`` in the current state.  Exit thresholds are
    lower than entry thresholds (hysteresis), reducing boundary whipsaw.
    """

    def __init__(self, *args, confirm_bars: int = 3,
                 min_dwell_bars: int = 5, hysteresis: float = 0.7, **kwargs):
        super().__init__(*args, **kwargs)
        self.confirm_bars = max(int(confirm_bars), 1)
        self.min_dwell_bars = max(int(min_dwell_bars), 0)
        self.hysteresis = min(max(float(hysteresis), 0.1), 0.99)
        self.direction = "sideways"
        self.volatility = "normal"
        self._dir_candidate = self.direction
        self._vol_candidate = self.volatility
        self._dir_count = self._vol_count = 0
        self._dir_dwell = self._vol_dwell = 0

    def _confirmed(self, current: str, candidate: str, candidate_attr: str,
                   count_attr: str, dwell_attr: str) -> str:
        dwell = getattr(self, dwell_attr) + 1
        setattr(self, dwell_attr, dwell)
        if candidate == current:
            setattr(self, candidate_attr, current)
            setattr(self, count_attr, 0)
            return current
        if candidate != getattr(self, candidate_attr):
            setattr(self, candidate_attr, candidate)
            setattr(self, count_attr, 1)
            return current
        count = getattr(self, count_attr) + 1
        setattr(self, count_attr, count)
        if dwell < self.min_dwell_bars or count < self.confirm_bars:
            return current
        setattr(self, dwell_attr, 0)
        setattr(self, count_attr, 0)
        return candidate

    def update(self, high: float, low: float, close: float) -> str:
        # Reuse the streaming indicator calculations but do not use the
        # legacy mutually-exclusive state decision.
        if self._ema_f is None:
            self._ema_f = self._ema_s = close
        else:
            self._ema_f += self._kf * (close - self._ema_f)
            self._ema_s += self._ks * (close - self._ema_s)
        self.atr_f.update(high, low, close)
        self.atr_s.update(high, low, close)
        if self.atr_s.value is None or self.atr_s.value <= 0:
            return self.regime

        self.momentum = (self._ema_f - self._ema_s) / self.atr_s.value
        self.vol_ratio = ((self.atr_f.value or self.atr_s.value)
                          / self.atr_s.value)

        enter_m = self.m_threshold
        exit_m = enter_m * self.hysteresis
        if self.direction == "trend_up" and self.momentum >= exit_m:
            raw_direction = "trend_up"
        elif self.direction == "trend_down" and self.momentum <= -exit_m:
            raw_direction = "trend_down"
        elif self.momentum > enter_m:
            raw_direction = "trend_up"
        elif self.momentum < -enter_m:
            raw_direction = "trend_down"
        else:
            raw_direction = "sideways"

        exit_vol = self.vol_hi * self.hysteresis
        raw_volatility = (
            "high_vol" if self.vol_ratio > self.vol_hi else
            "high_vol" if (self.volatility == "high_vol" and
                            self.vol_ratio >= exit_vol) else
            "normal"
        )
        self.direction = self._confirmed(
            self.direction, raw_direction, "_dir_candidate", "_dir_count",
            "_dir_dwell")
        self.volatility = self._confirmed(
            self.volatility, raw_volatility, "_vol_candidate", "_vol_count",
            "_vol_dwell")
        self.regime = ("high_vol" if self.volatility == "high_vol"
                       else self.direction)
        return self.regime


def build_detector(cfg):
    """Factory shared by DynamicGridEngine and ShortGridEngine so both
    engines pick the same detector class from one config, consistently.
    """
    if getattr(cfg, "use_regime_pct", False):
        return PercentileRegimeDetector(
            m_threshold=cfg.regime_m_threshold, vol_hi=cfg.regime_vol_hi,
            confirm_bars=cfg.regime_confirm_bars,
            min_dwell_bars=cfg.regime_min_dwell_bars,
            hysteresis=cfg.regime_hysteresis,
            pct_window=getattr(cfg, "regime_pct_window", 250),
            trend_pct=getattr(cfg, "regime_trend_pct", 0.85),
            vol_pct=getattr(cfg, "regime_vol_pct", 0.85))
    if cfg.use_regime_2d:
        return PersistentRegimeDetector(
            m_threshold=cfg.regime_m_threshold, vol_hi=cfg.regime_vol_hi,
            confirm_bars=cfg.regime_confirm_bars,
            min_dwell_bars=cfg.regime_min_dwell_bars,
            hysteresis=cfg.regime_hysteresis)
    return RegimeDetector(m_threshold=cfg.regime_m_threshold,
                          vol_hi=cfg.regime_vol_hi)


class PercentileRegimeDetector(PersistentRegimeDetector):
    """Regime detector with SCALE-INVARIANT (percentile-rank) thresholds.

    Root-cause fix for the failure mode found across E8 (synthetic-tuned
    config produces degenerate zones on real BTC prices - ATR ~5%/bar vs
    synthetic ~0.8%), E12 (RL policy's state signal, computed on synthetic
    dynamics, misclassifies real markets and turns a real bull run into a
    loss), and E13 (fixed-threshold PersistentRegimeDetector's effect on
    real cross-asset data was indistinguishable from seed noise - BTC/1d
    and SOL/1d have wildly different momentum/vol_ratio SCALES, so one
    m_threshold/vol_hi pair cannot fit both).

    Instead of comparing momentum/vol_ratio to fixed constants, this class
    ranks the CURRENT value against its own trailing distribution (a
    rolling window of `pct_window` bars) and fires when it is an extreme
    observation FOR THAT SERIES - e.g. "momentum is in the most extreme
    15% of this asset's last 250 bars" rather than "momentum > 0.5". The
    same code and same default parameters should therefore behave
    sensibly whether momentum's typical magnitude is 0.1 or 10 - no
    per-asset/per-timeframe retuning needed, by construction.

    Confirmation/dwell/hysteresis machinery is inherited unchanged from
    PersistentRegimeDetector - only the raw_direction/raw_volatility
    classification step changes from fixed-threshold to percentile-rank.
    """

    def __init__(self, *args, pct_window: int = 250,
                 trend_pct: float = 0.85, vol_pct: float = 0.85,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.pct_window = max(int(pct_window), 20)
        self.trend_pct = min(max(float(trend_pct), 0.5), 0.99)
        self.vol_pct = min(max(float(vol_pct), 0.5), 0.99)
        self._mom_hist: list[float] = []
        self._vol_hist: list[float] = []

    @staticmethod
    def _rank(history: list[float], value: float) -> float:
        """Fraction of history <= value (0..1). Empty/short history -> 0.5
        (neutral - no regime signal until enough data has accumulated)."""
        if len(history) < 20:
            return 0.5
        return sum(1 for x in history if x <= value) / len(history)

    def update(self, high: float, low: float, close: float) -> str:
        if self._ema_f is None:
            self._ema_f = self._ema_s = close
        else:
            self._ema_f += self._kf * (close - self._ema_f)
            self._ema_s += self._ks * (close - self._ema_s)
        self.atr_f.update(high, low, close)
        self.atr_s.update(high, low, close)
        if self.atr_s.value is None or self.atr_s.value <= 0:
            return self.regime

        self.momentum = (self._ema_f - self._ema_s) / self.atr_s.value
        self.vol_ratio = ((self.atr_f.value or self.atr_s.value)
                          / self.atr_s.value)

        # rank BEFORE appending current value - no lookahead into itself
        mom_rank_hi = self._rank(self._mom_hist, self.momentum)
        mom_rank_lo = self._rank(self._mom_hist, -self.momentum)  # symmetric
        vol_rank = self._rank(self._vol_hist, self.vol_ratio)
        self._mom_hist.append(self.momentum)
        self._vol_hist.append(self.vol_ratio)
        if len(self._mom_hist) > self.pct_window:
            self._mom_hist.pop(0)
            self._vol_hist.pop(0)

        exit_pct = self.trend_pct * self.hysteresis
        if self.direction == "trend_up" and mom_rank_hi >= exit_pct:
            raw_direction = "trend_up"
        elif self.direction == "trend_down" and mom_rank_lo >= exit_pct:
            raw_direction = "trend_down"
        elif mom_rank_hi >= self.trend_pct:
            raw_direction = "trend_up"
        elif mom_rank_lo >= self.trend_pct:
            raw_direction = "trend_down"
        else:
            raw_direction = "sideways"

        exit_vol_pct = self.vol_pct * self.hysteresis
        if vol_rank >= self.vol_pct:
            raw_volatility = "high_vol"
        elif self.volatility == "high_vol" and vol_rank >= exit_vol_pct:
            raw_volatility = "high_vol"
        else:
            raw_volatility = "normal"

        self.direction = self._confirmed(
            self.direction, raw_direction, "_dir_candidate", "_dir_count",
            "_dir_dwell")
        self.volatility = self._confirmed(
            self.volatility, raw_volatility, "_vol_candidate", "_vol_count",
            "_vol_dwell")
        self.regime = ("high_vol" if self.volatility == "high_vol"
                       else self.direction)
        return self.regime
