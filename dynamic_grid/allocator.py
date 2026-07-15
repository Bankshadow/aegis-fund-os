"""Deterministic capital allocator for pre-approved strategy sleeves."""

from collections import deque


class RiskBudgetAllocator:
    """Tilt base weights toward recent realized performance within hard caps."""

    def __init__(self, base_weights: dict[str, float], *, max_weight: float = 0.75,
                 lookback: int = 20, performance_tilt: float = 2.0):
        if not base_weights or any(weight < 0 for weight in base_weights.values()):
            raise ValueError("base_weights must contain non-negative weights")
        if not 0.0 < max_weight <= 1.0:
            raise ValueError("max_weight must be in (0, 1]")
        if lookback < 1 or performance_tilt < 0:
            raise ValueError("lookback must be positive and performance_tilt non-negative")
        total = sum(base_weights.values())
        if total <= 0:
            raise ValueError("base_weights must sum to more than zero")
        self.base_weights = {name: weight / total for name, weight in base_weights.items()}
        self.max_weight = max_weight
        self.performance_tilt = performance_tilt
        self.history = {name: deque(maxlen=lookback) for name in self.base_weights}

    def record(self, name: str, realized_pnl: float, allocated_equity: float) -> None:
        if name not in self.history:
            raise KeyError(f"unknown sleeve: {name}")
        if allocated_equity > 0:
            self.history[name].append(realized_pnl / allocated_equity)

    def weights(self, enabled: dict[str, bool],
                base_weights: dict[str, float] | None = None) -> dict[str, float]:
        if set(enabled) != set(self.base_weights):
            raise ValueError("enabled must name exactly the allocator sleeves")
        active = [name for name, allowed in enabled.items() if allowed]
        out = {name: 0.0 for name in self.base_weights}
        if not active:
            return out
        source = base_weights or self.base_weights
        raw = {}
        for name in active:
            observations = self.history[name]
            avg_return = sum(observations) / len(observations) if observations else 0.0
            multiplier = max(0.0, 1.0 + self.performance_tilt * avg_return)
            raw[name] = max(source.get(name, 0.0), 0.0) * multiplier
        total = sum(raw.values())
        if total <= 0:
            raw = {name: 1.0 for name in active}
            total = float(len(active))
        out.update({name: value / total for name, value in raw.items()})
        if len(active) > 1:
            capped = {name: min(out[name], self.max_weight) for name in active}
            remainder = 1.0 - sum(capped.values())
            eligible = [name for name in active if capped[name] < self.max_weight]
            while remainder > 1e-12 and eligible:
                share = remainder / len(eligible)
                next_eligible = []
                for name in eligible:
                    room = self.max_weight - capped[name]
                    add = min(room, share)
                    capped[name] += add
                    remainder -= add
                    if capped[name] < self.max_weight - 1e-12:
                        next_eligible.append(name)
                eligible = next_eligible
            out.update(capped)
        return out
