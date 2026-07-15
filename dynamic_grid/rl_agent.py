"""Tabular Q-learning risk governor - the RL learning loop.

Replaces MemoryOrchestrator's hand-written rules with a LEARNED policy.
Scope is deliberately tabular (numpy-only, no deep RL): 12 states x 3
actions is interpretable, trains in minutes, and every learned preference
can be printed and audited - in keeping with this project's "explain every
decision" principle. If a 36-cell table can't beat fixed weights, a neural
net trained on the same 2000-bar episodes would overfit, not generalize.

MDP (declared before any evaluation):
  step     : every `review_every` bars
  state    : (market regime [4]) x (window equity trend [down/flat/up]) = 12
  action   : global risk scale for all layers in {0.25, 0.5, 1.0}
  reward   : (equity_end/equity_start - 1) - 2 * window_max_drawdown
             (the system's standard risk weighting, unchanged)
  learning : Q-learning, alpha=0.2, gamma=0.9, epsilon-greedy decaying
  training : ``train_q`` = synthetic (legacy E10); ``train_q_on_ohlc`` = real
             bars only (E19 — required before any real-data claim)
  judging  : greedy policy on HELD-OUT real data; never reuse synthetic Q-tables
             on live/real markets (E12).
"""

import json

import numpy as np

from .event_log import DecisionLog
from .grid_engine import DynamicGridEngine

REGIMES = ["sideways", "trend_up", "trend_down", "high_vol"]
TRENDS = ["down", "flat", "up"]          # window equity change bucket
ACTIONS = [0.25, 0.5, 1.0]               # global risk scale
FLAT_BAND = 0.002                        # |window return| < 0.2% -> "flat"


def state_index(regime: str, window_ret: float) -> int:
    r = REGIMES.index(regime) if regime in REGIMES else 0
    t = 1 if abs(window_ret) < FLAT_BAND else (0 if window_ret < 0 else 2)
    return r * len(TRENDS) + t


class RLGovernor:
    """Drives layer engines; a Q-table picks the global risk scale.

    Duck-type compatible with run_backtest_engine. In training mode
    (learn=True) it updates the Q-table online with epsilon-greedy
    exploration; in evaluation mode (learn=False) it acts greedily.
    """

    def __init__(self, layers, q: np.ndarray | None = None,
                 review_every: int = 50, learn: bool = False,
                 alpha: float = 0.2, gamma: float = 0.9,
                 epsilon: float = 0.0, log: DecisionLog | None = None,
                 engine_cls=DynamicGridEngine):
        self.q = q if q is not None else np.zeros((len(REGIMES) * len(TRENDS),
                                                   len(ACTIONS)))
        self.log = log if log is not None else DecisionLog()
        total_w = sum(lyr.weight for lyr in layers)
        self.names = [lyr.name for lyr in layers]
        self.weights = [lyr.weight / total_w for lyr in layers]
        self.engines = [(getattr(lyr, "engine_cls", None) or engine_cls)(
                            lyr.cfg, logger=self.log, agent_id=lyr.name)
                        for lyr in layers]
        self.review_every = review_every
        self.learn = learn
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self.rng = np.random.default_rng(0)
        self.scale = 1.0
        self.n_scale_changes = 0
        self.bar = -1
        self._win_start_eq = None
        self._win_peak = None
        self._win_trough = None
        self._prev_state = None
        self._prev_action = None
        self._last_equity = None

    def _pick(self, s: int) -> int:
        if self.learn and self.rng.random() < self.epsilon:
            return int(self.rng.integers(len(ACTIONS)))
        return int(np.argmax(self.q[s]))

    def on_bar(self, o, h, l, c, equity):
        self.bar += 1
        realized = 0.0
        for eng, w in zip(self.engines, self.weights):
            realized += eng.on_bar(o, h, l, c, equity * w * self.scale)

        eq_now = equity + realized + self.unrealized(c)
        if self._win_start_eq is None:
            self._win_start_eq = self._win_peak = self._win_trough = eq_now
        self._win_peak = max(self._win_peak, eq_now)
        self._win_trough = min(self._win_trough, eq_now)
        self._last_equity = eq_now

        if self.bar > 0 and self.bar % self.review_every == 0:
            self._step(c)
        return realized

    def _step(self, price):
        win_ret = self._last_equity / self._win_start_eq - 1.0
        win_dd = ((self._win_peak - self._win_trough) / self._win_peak
                  if self._win_peak > 0 else 0.0)
        core = self.engines[min(1, len(self.engines) - 1)]
        s = state_index(core.detector.regime, win_ret)

        if self.learn and self._prev_state is not None:
            reward = win_ret - 2.0 * win_dd
            ps, pa = self._prev_state, self._prev_action
            self.q[ps, pa] += self.alpha * (
                reward + self.gamma * self.q[s].max() - self.q[ps, pa])

        a = self._pick(s)
        new_scale = ACTIONS[a]
        if new_scale != self.scale:
            self.n_scale_changes += 1
            self.log.record(
                bar=self.bar, agent_id="rl_governor",
                decision="risk_cut" if new_scale < self.scale else "risk_restore",
                reason=f"learned policy: state ({core.detector.regime}, "
                       f"window {win_ret:+.2%}) -> scale {new_scale}",
                price=price, regime=core.detector.regime,
                momentum=core.detector.momentum, equity=self._last_equity,
                extra={"old_scale": self.scale, "new_scale": new_scale})
        self.scale = new_scale
        self._prev_state, self._prev_action = s, a
        self._win_start_eq = self._win_peak = self._win_trough = self._last_equity

    # duck-typed aggregates
    def unrealized(self, price):
        return sum(e.unrealized(price) for e in self.engines)

    def exposure(self, price):
        return sum(e.exposure(price) for e in self.engines)

    def liquidate(self, price):
        return sum(e.liquidate(price) for e in self.engines
                   if hasattr(e, "liquidate"))

    @property
    def n_tp(self): return sum(e.n_tp for e in self.engines)
    @property
    def n_stopouts(self): return sum(e.n_stopouts for e in self.engines)
    @property
    def n_rebuilds(self): return sum(e.n_rebuilds for e in self.engines)
    @property
    def n_consolidations(self): return sum(e.n_consolidations for e in self.engines)
    @property
    def gross_profit(self): return sum(e.gross_profit for e in self.engines)
    @property
    def gross_loss(self): return sum(e.gross_loss for e in self.engines)


def train_q(make_layers_fn, scenarios, seeds=(1, 2), epochs: int = 8,
            n_bars: int = 2000, verbose: bool = True) -> np.ndarray:
    """Train the Q-table on SYNTHETIC scenarios (legacy E10).

    Do not use the resulting table on real markets (E12). Prefer
    ``train_q_on_ohlc`` for any real-data validation.
    """
    from .synthetic import generate_scenario

    q = np.zeros((len(REGIMES) * len(TRENDS), len(ACTIONS)))
    episode = 0
    total = epochs * len(scenarios) * len(seeds)
    for ep in range(epochs):
        eps = max(0.05, 0.3 * (1 - ep / max(epochs - 1, 1)))
        for name in scenarios:
            for sd in seeds:
                gov = RLGovernor(make_layers_fn(), q=q, learn=True,
                                 epsilon=eps)
                gov.rng = np.random.default_rng(episode)   # vary exploration
                ohlc = generate_scenario(name, n_bars=n_bars, seed=sd)
                equity = 10_000.0
                cash = 0.0
                for o, h, l, c in ohlc:
                    cash += gov.on_bar(o, h, l, c, equity + cash)
                episode += 1
        if verbose:
            print(f"  epoch {ep+1}/{epochs} (eps={eps:.2f}) "
                  f"episodes={episode}/{total}")
    return q


def train_q_on_ohlc(make_layers_fn, ohlc: np.ndarray, epochs: int = 8,
                    seeds=(0, 1, 2), verbose: bool = True) -> np.ndarray:
    """Train a fresh Q-table by replaying REAL OHLC only (E19).

    Never calls synthetic generators. ``seeds`` vary exploration RNG across
    repeated passes of the same bars (>=3 required by project rules).
    """
    ohlc = np.asarray(ohlc, dtype=float)
    if ohlc.ndim != 2 or ohlc.shape[1] < 4:
        raise ValueError("ohlc must be (n, 4+) array")
    if len(seeds) < 3:
        raise ValueError("train_q_on_ohlc requires >= 3 exploration seeds")

    q = np.zeros((len(REGIMES) * len(TRENDS), len(ACTIONS)))
    episode = 0
    total = epochs * len(seeds)
    for ep in range(epochs):
        eps = max(0.05, 0.3 * (1 - ep / max(epochs - 1, 1)))
        for sd in seeds:
            gov = RLGovernor(make_layers_fn(), q=q, learn=True, epsilon=eps)
            gov.rng = np.random.default_rng(int(sd) + ep * 1009)
            equity = 10_000.0
            cash = 0.0
            for o, h, l, c in ohlc:
                cash += gov.on_bar(float(o), float(h), float(l), float(c),
                                   equity + cash)
            episode += 1
        if verbose:
            print(f"  epoch {ep+1}/{epochs} (eps={eps:.2f}) "
                  f"episodes={episode}/{total}")
    return q


def policy_table(q: np.ndarray) -> str:
    """Human-readable learned policy - every cell auditable."""
    lines = [f"{'state':<28} {'Q(0.25)':>9} {'Q(0.5)':>9} {'Q(1.0)':>9}  chosen"]
    for ri, reg in enumerate(REGIMES):
        for ti, tr in enumerate(TRENDS):
            s = ri * len(TRENDS) + ti
            best = ACTIONS[int(np.argmax(q[s]))]
            lines.append(f"{reg+' / eq '+tr:<28} "
                         f"{q[s,0]:>+9.4f} {q[s,1]:>+9.4f} {q[s,2]:>+9.4f}"
                         f"  -> {best}")
    return "\n".join(lines)


def save_q(q: np.ndarray, path: str):
    with open(path, "w") as f:
        json.dump({"regimes": REGIMES, "trends": TRENDS, "actions": ACTIONS,
                   "q": q.tolist()}, f, indent=1)


def load_q(path: str) -> np.ndarray:
    with open(path) as f:
        return np.array(json.load(f)["q"])
