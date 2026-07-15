"""Synthetic OHLC scenario generators for stress-testing grid systems.

Each generator returns an (n, 4) float array of [open, high, low, close].
Intrabar high/low come from simulating sub-steps inside each bar, so grid
fills between open and close are represented realistically.

Convention: mu / sigma are TOTAL drift / volatility over the whole series
(e.g. sigma=0.35 -> ~35% log-price standard deviation end-to-end), which
keeps scenarios realistic regardless of bar count.
"""

import numpy as np

SUBSTEPS = 8  # intrabar path resolution


def _path_to_ohlc(path: np.ndarray) -> np.ndarray:
    """Fold a fine-grained price path into OHLC bars of SUBSTEPS points."""
    n = len(path) // SUBSTEPS
    p = path[: n * SUBSTEPS].reshape(n, SUBSTEPS)
    ohlc = np.empty((n, 4))
    ohlc[:, 0] = p[:, 0]
    ohlc[:, 1] = p.max(axis=1)
    ohlc[:, 2] = p.min(axis=1)
    ohlc[:, 3] = p[:, -1]
    return ohlc


def _gbm_path(n_steps, s0, mu, sigma, rng):
    """Geometric Brownian motion; mu/sigma are totals over the series."""
    dt = 1.0 / n_steps
    z = rng.standard_normal(n_steps)
    log_ret = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    return s0 * np.exp(np.cumsum(np.concatenate(([0.0], log_ret))))


def _ou_path(n_steps, s0, theta, sigma, rng):
    """Mean-reverting log price (sideways market).

    theta = number of mean-reversion 'pulls' over the series;
    stationary std of log price ~= sigma / sqrt(2*theta).
    """
    dt = 1.0 / n_steps
    x = np.empty(n_steps + 1)
    x[0] = np.log(s0)
    mean = np.log(s0)
    sq = sigma * np.sqrt(dt)
    z = rng.standard_normal(n_steps)
    for i in range(n_steps):
        x[i + 1] = x[i] + theta * (mean - x[i]) * dt + sq * z[i]
    return np.exp(x)


def generate_scenario(name: str, n_bars: int = 2000, s0: float = 100.0,
                      seed: int = 0) -> np.ndarray:
    """Generate an OHLC array for a named scenario."""
    rng = np.random.default_rng(seed)
    n_steps = n_bars * SUBSTEPS

    if name == "sideways":
        # oscillates ~ +/-15% around s0
        path = _ou_path(n_steps, s0, theta=8.0, sigma=0.6, rng=rng)

    elif name == "uptrend":
        path = _gbm_path(n_steps, s0, mu=0.9, sigma=0.35, rng=rng)

    elif name == "downtrend":
        path = _gbm_path(n_steps, s0, mu=-0.9, sigma=0.35, rng=rng)

    elif name == "crash":
        # calm drift with sudden downward jumps (price anomaly)
        path = _gbm_path(n_steps, s0, mu=0.15, sigma=0.25, rng=rng)
        n_jumps = 3
        idx = rng.integers(n_steps // 4, n_steps, n_jumps)
        for i in sorted(idx):
            path[i:] *= 1.0 - rng.uniform(0.06, 0.15)  # 6-15% gap down

    elif name == "regime_switch":
        # alternate sideways / trend / high-vol blocks
        blocks, cur = [], s0
        kinds = ["sideways", "uptrend", "high_vol", "downtrend", "sideways"]
        per = n_steps // len(kinds)
        for k in kinds:
            if k == "sideways":
                b = _ou_path(per, cur, theta=4.0, sigma=0.3, rng=rng)
            elif k == "uptrend":
                b = _gbm_path(per, cur, mu=0.35, sigma=0.15, rng=rng)
            elif k == "downtrend":
                b = _gbm_path(per, cur, mu=-0.35, sigma=0.15, rng=rng)
            else:
                b = _gbm_path(per, cur, mu=0.0, sigma=0.5, rng=rng)
            blocks.append(b[:-1])
            cur = b[-1]
        path = np.concatenate(blocks)

    elif name == "high_vol":
        path = _gbm_path(n_steps, s0, mu=0.0, sigma=1.0, rng=rng)

    else:
        raise ValueError(f"unknown scenario: {name}")

    return _path_to_ohlc(path)


SCENARIOS = ["sideways", "uptrend", "downtrend", "crash", "regime_switch", "high_vol"]
