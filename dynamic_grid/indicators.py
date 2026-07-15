"""Streaming indicators used by the grid engine."""


class ATR:
    """Wilder's Average True Range, updated bar by bar."""

    def __init__(self, period: int = 14):
        self.period = period
        self.value = None
        self._prev_close = None
        self._warmup = []

    def update(self, high: float, low: float, close: float) -> float:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(high - low,
                     abs(high - self._prev_close),
                     abs(low - self._prev_close))
        self._prev_close = close

        if self.value is None:
            self._warmup.append(tr)
            if len(self._warmup) >= self.period:
                self.value = sum(self._warmup) / self.period
        else:
            self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value if self.value is not None else tr


class AnomalyDetector:
    """Flags bars whose move is abnormally large relative to recent ATR.

    A bar is an anomaly when |close - prev_close| > z_threshold * ATR.
    Used to trigger zone consolidation (order merging / size scaling).
    """

    def __init__(self, z_threshold: float = 3.0):
        self.z_threshold = z_threshold
        self._prev_close = None

    def update(self, close: float, atr: float | None) -> int:
        """Returns -1 (down anomaly), +1 (up anomaly) or 0 (normal)."""
        prev = self._prev_close
        self._prev_close = close
        if prev is None or atr is None or atr <= 0:
            return 0
        move = close - prev
        if abs(move) > self.z_threshold * atr:
            return 1 if move > 0 else -1
        return 0
