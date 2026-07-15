"""Risk-per-zone position sizing.

The zone's worst case is: every buy level fills, then price hits the zone
stop below the lowest level.  We budget that worst-case loss to a fixed
fraction of equity (risk_per_zone) and split it equally across levels, so
deeper levels get slightly larger size (their stop distance is smaller).
"""


def size_levels(equity: float, levels: list[float], stop_price: float,
                risk_per_zone: float) -> list[float]:
    """Return position size (units) for each buy level.

    equity        : current account equity
    levels        : buy level prices (descending)
    stop_price    : zone stop below the lowest level
    risk_per_zone : max fraction of equity lost if all levels fill and stop
    """
    if not levels:
        return []
    budget_per_level = equity * risk_per_zone / len(levels)
    sizes = []
    for lv in levels:
        stop_dist = max(lv - stop_price, 1e-9)
        sizes.append(budget_per_level / stop_dist)
    return sizes
