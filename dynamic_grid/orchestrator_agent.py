"""Memory-loop orchestrator: reads shared agent memory, adjusts risk budgets.

This closes the last open loop in the MAS stack:

    layer agents --write--> DecisionLog (shared memory) --read--> orchestrator
         ^                                                          |
         +---------------- adjusts risk budgets <-------------------+

Unlike MultiLayerOrchestrator (fixed weights forever), MemoryOrchestrator
periodically REVIEWS the shared DecisionLog and applies pre-declared
governance rules:

  RULE 1 (cut):     a layer with >= stop_threshold stop-outs since the last
                    review gets its risk budget halved (floor: min_scale).
                    Default threshold is 1: after any stop-out the layer
                    re-enters at reduced size and must earn its budget back
                    (anti-martingale / equity-curve throttling). NOTE: the
                    first design used threshold=2 per 50-bar window, which
                    was mechanically impossible at tuned configs (cooldowns
                    are 36-109 bars and stop events landed 270+ bars apart)
                    - the rule was dead on arrival. Changed for feasibility
                    BEFORE looking at ON-vs-OFF scores, not after.
  RULE 2 (restore): a layer with zero stop-outs and at least one take-profit
                    since the last review earns its budget back (doubling,
                    cap 1.0). Recovery must be earned by evidence, not time.

Every orchestrator action is itself logged into the same DecisionLog (agent
id "orchestrator") - so the Virtual Office animates it, Cognee ingests its
reasoning, and the audit trail is complete.

Honesty notes, declared before evaluation (see orchestrator_demo.py):
  - The judging metric is the system's standard robust score
    (return - 2*maxDD), averaged over 6 scenarios x 3 seeds, ON vs OFF.
  - The rules are deliberately dumb-but-transparent. This is the minimal
    memory loop, not RL; if it doesn't beat fixed weights, we say so.
"""

from .event_log import DecisionLog, RISK_CUT, RISK_RESTORE, STOP_OUT, TAKE_PROFIT
from .grid_engine import DynamicGridEngine


class MemoryOrchestrator:
    """Drives layer engines and governs their risk budgets from shared memory.

    Duck-type compatible with run_backtest_engine (on_bar / unrealized /
    n_tp / n_stopouts / n_rebuilds / n_consolidations / gross_*).
    """

    def __init__(self, layers, log: DecisionLog | None = None,
                 review_every: int = 200, stop_threshold: int = 1,
                 cut_factor: float = 0.5, min_scale: float = 0.25,
                 engine_cls=DynamicGridEngine):
        # review_every must be long enough that stop_threshold stop-outs are
        # mechanically POSSIBLE: after a stop a layer sits in cooldown
        # (36-109 bars at tuned configs) before it can even rebuild. A 50-bar
        # window with threshold 2 can never fire - found the hard way.
        if not layers:
            raise ValueError("MemoryOrchestrator needs at least one layer")
        self.log = log if log is not None else DecisionLog()
        total_w = sum(lyr.weight for lyr in layers)
        self.names = [lyr.name for lyr in layers]
        self.weights = [lyr.weight / total_w for lyr in layers]
        self.engines = [(getattr(lyr, "engine_cls", None) or engine_cls)(
                            lyr.cfg, logger=self.log, agent_id=lyr.name)
                        for lyr in layers]
        self.review_every = review_every
        self.stop_threshold = stop_threshold
        self.cut_factor = cut_factor
        self.min_scale = min_scale
        self.risk_scale = {n: 1.0 for n in self.names}
        self.bar = -1
        self._cursor = 0            # first log event not yet reviewed
        self.n_reviews = 0
        self.n_interventions = 0

    # -- per bar ------------------------------------------------------------
    def on_bar(self, o: float, h: float, l: float, c: float,
              equity: float) -> float:
        self.bar += 1
        realized = 0.0
        for eng, w, name in zip(self.engines, self.weights, self.names):
            # governance lever: the equity slice (risk budget) handed to the
            # layer is scaled by what the orchestrator learned from memory
            realized += eng.on_bar(o, h, l, c,
                                   equity * w * self.risk_scale[name])
        if self.bar > 0 and self.bar % self.review_every == 0:
            self._review(c, equity)
        return realized

    # -- the memory loop ----------------------------------------------------
    def _review(self, price: float, equity: float) -> None:
        """Read the shared log since the last review; apply governance rules."""
        self.n_reviews += 1
        window = self.log.events[self._cursor:]
        self._cursor = len(self.log.events)

        per: dict[str, dict[str, int]] = {}
        for e in window:
            per.setdefault(e.agent_id, {})
            per[e.agent_id][e.decision] = per[e.agent_id].get(e.decision, 0) + 1

        core = self.engines[min(1, len(self.engines) - 1)]  # regime reference
        for name in self.names:
            stats = per.get(name, {})
            stops = stats.get(STOP_OUT, 0)
            tps = stats.get(TAKE_PROFIT, 0)
            scale = self.risk_scale[name]

            if stops >= self.stop_threshold and scale > self.min_scale:
                new = max(self.min_scale, scale * self.cut_factor)
                self.risk_scale[name] = new
                self.n_interventions += 1
                self._log_action(RISK_CUT, name, core, price, equity,
                                 f"layer '{name}' took {stops} stop-outs in the "
                                 f"last {self.review_every} bars; budget "
                                 f"{scale:.2f} -> {new:.2f}", scale, new)
            elif stops == 0 and tps > 0 and scale < 1.0:
                new = min(1.0, scale * 2.0)
                self.risk_scale[name] = new
                self.n_interventions += 1
                self._log_action(RISK_RESTORE, name, core, price, equity,
                                 f"layer '{name}' ran clean ({tps} TPs, 0 "
                                 f"stop-outs) since last review; budget "
                                 f"{scale:.2f} -> {new:.2f}", scale, new)

    def _log_action(self, decision, target, core, price, equity, reason,
                    old, new) -> None:
        self.log.record(
            bar=self.bar, agent_id="orchestrator", decision=decision,
            reason=reason, price=price,
            regime=core.detector.regime, momentum=core.detector.momentum,
            equity=equity, extra={"target": target, "old_scale": old,
                                  "new_scale": new})

    # -- duck-typed aggregate interface (same as MultiLayerOrchestrator) ----
    def unrealized(self, price):
        return sum(eng.unrealized(price) for eng in self.engines)

    def exposure(self, price):
        return sum(eng.exposure(price) for eng in self.engines)

    def liquidate(self, price):
        return sum(eng.liquidate(price) for eng in self.engines
                   if hasattr(eng, "liquidate"))

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
