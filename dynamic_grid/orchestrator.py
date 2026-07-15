"""Multi-Layer Grid Orchestrator.

Runs several DynamicGridEngine instances side by side, each tuned to a
different price scale (tight/fast, core, wide/slow), and allocates a
SHARE of total portfolio equity to each layer. Because each layer's
Risk-per-Zone budget is computed from its own equity slice, the total
risk exposure across all layers is capped by construction:

    total_worst_case_loss <= equity * sum(weight_i * risk_per_zone_i)

Rationale (ต่อยอดจากระบบ single-layer):
- โซนเดียวจับได้แค่ 1 สเกลความผันผวน (spacing คงที่ต่อรอบ zone)
- ตลาดจริงมีทั้งการแกว่งไว (noise) และการแกว่งช้า (swing ใหญ่) พร้อมกัน
- Layer เร็ว (atr_mult เล็ก) เก็บกำไรจาก noise ถี่ๆ
- Layer ช้า (atr_mult ใหญ่) รอจับ swing ใหญ่ ไม่ตื่นตกใจไปกับ noise
- แต่ละ layer ยังมี zone stop / cooldown / regime gate ของตัวเอง (independent)
  ความเสี่ยงจึงไม่ทบซ้อนกันแบบไม่มีเพดาน — ถูก partition ด้วย weight ตั้งแต่ต้น
"""

from dataclasses import dataclass, field

from .grid_engine import DynamicGridConfig, DynamicGridEngine


@dataclass
class LayerSpec:
    name: str
    weight: float               # สัดส่วน equity/risk budget ของ layer นี้ (จะถูก normalize รวม =1)
    cfg: DynamicGridConfig
    engine_cls: type | None = None   # None = ใช้ engine_cls กลางของ orchestrator
                                     # (ตั้งเป็น ShortGridEngine ได้ -> พอร์ต long+short)


@dataclass
class LayerStats:
    name: str
    weight: float
    n_tp: int
    n_stopouts: int
    n_rebuilds: int
    n_consolidations: int


def make_layers(base: DynamicGridConfig,
                fast_scale: float = 0.7, fast_weight: float = 0.10,
                core_weight: float = 0.70,
                wide_scale: float = 2.0, wide_weight: float = 0.20) -> list[LayerSpec]:
    """Derive a 3-layer stack (fast/core/wide) from one base config.

    atr_mult sets each layer's price scale; risk_per_zone and stop_mult
    are re-scaled WITH it so the zone stop stays roughly the same number
    of ATRs away regardless of scale (a naive spacing-only rescale makes
    the fast layer's stop too close in ATR terms, so it dies to normal
    noise - confirmed by an initial test where the fast layer alone
    racked up 60 stop-outs in a plain sideways scenario). Regime gates
    and cooldown behaviour stay shared so each layer still gets the
    zone-stop / trend-filter / anomaly-consolidation safety net.
    """
    import copy

    fast = copy.deepcopy(base)
    fast.atr_mult = max(base.atr_mult * fast_scale, 0.3)
    fast.stop_mult = base.stop_mult / fast_scale        # keep stop ~constant in ATR units
    fast.risk_per_zone = base.risk_per_zone * 0.5        # smaller bite per (more frequent) stop-out
    fast.tp_mult = max(base.tp_mult * 0.7, 0.5)
    fast.cooldown_bars = max(int(base.cooldown_bars * 0.5), 5)

    core = copy.deepcopy(base)

    wide = copy.deepcopy(base)
    wide.atr_mult = base.atr_mult * wide_scale
    wide.stop_mult = base.stop_mult / wide_scale
    wide.tp_mult = base.tp_mult * 1.3
    wide.cooldown_bars = int(base.cooldown_bars * 1.5)

    return [
        LayerSpec("fast", fast_weight, fast),
        LayerSpec("core", core_weight, core),
        LayerSpec("wide", wide_weight, wide),
    ]


def make_dual_layers(base: DynamicGridConfig, short_cfg=None,
                     short_weight: float = 0.25) -> list[LayerSpec]:
    """Long fast/core/wide stack + one short layer = dual-side portfolio.

    The two sides' regime gates are natural complements: long layers refuse
    to build in trend_down, the short layer refuses in trend_up - so a fixed
    split self-selects the active side per regime instead of needing a
    switching rule. short_weight=0.25 is declared up front (not swept after
    seeing results); the long stack keeps its internal 10/70/20 proportions
    inside the remaining 75%.
    """
    from .short_engine import ShortGridEngine

    longs = make_layers(base)
    long_total = sum(l.weight for l in longs)
    for l in longs:
        l.weight = l.weight / long_total * (1.0 - short_weight)
    longs.append(LayerSpec("short", short_weight, short_cfg or base,
                           engine_cls=ShortGridEngine))
    return longs


class MultiLayerOrchestrator:
    """Coordinates N grid layers sharing one equity/risk budget."""

    def __init__(self, layers: list[LayerSpec], engine_cls=DynamicGridEngine,
                max_gross_exposure: float | None = None):
        """
        max_gross_exposure: cap on combined exposure across ALL layers, as a
        fraction of equity (e.g. 0.6 = never let all layers' open notional
        exceed 60% of equity at once). None = uncisabled (v3 behaviour).

        Per-zone risk is already capped by `risk_per_zone` inside each
        layer, but nothing previously stopped every layer from opening a
        zone in the SAME bar - a trending move can make all 3 layers build
        together, stacking notional exposure well past any single layer's
        own budget. This cap closes that gap: when combined exposure is at
        or above the ceiling, layers that are currently flat (no open zone)
        defer their next build by one bar instead of piling on. It does not
        touch layers that already have a zone open - the goal is to stop
        NEW simultaneous entries, not to force-close existing risk.
        """
        if not layers:
            raise ValueError("MultiLayerOrchestrator needs at least one layer")
        total_w = sum(lyr.weight for lyr in layers)
        self.layers = layers
        self.weights = [lyr.weight / total_w for lyr in layers]  # normalize to sum=1
        self.engines = [(lyr.engine_cls or engine_cls)(lyr.cfg)
                        for lyr in layers]
        self.max_gross_exposure = max_gross_exposure

    def on_bar(self, o: float, h: float, l: float, c: float,
              equity: float) -> float:
        """Feed the bar to every layer; each gets its equity slice.

        Layer risk is naturally partitioned: layer i can only ever put
        `equity * weight_i * risk_per_zone_i` at risk in a single zone.
        """
        if self.max_gross_exposure is not None and equity > 0:
            current = self.exposure(o) / equity
            if current >= self.max_gross_exposure:
                for eng in self.engines:
                    if eng.center is None and eng.cooldown == 0:
                        eng.cooldown = 1  # defer this bar's build; don't stack on

        realized_total = 0.0
        for eng, w in zip(self.engines, self.weights):
            realized_total += eng.on_bar(o, h, l, c, equity * w)
        return realized_total

    def unrealized(self, price: float) -> float:
        return sum(eng.unrealized(price) for eng in self.engines)

    def exposure(self, price: float) -> float:
        return sum(eng.exposure(price) for eng in self.engines)

    def liquidate(self, price: float) -> float:
        return sum(eng.liquidate(price) for eng in self.engines
                   if hasattr(eng, "liquidate"))

    def layer_stats(self) -> list[LayerStats]:
        return [
            LayerStats(lyr.name, w, eng.n_tp, eng.n_stopouts,
                      eng.n_rebuilds, eng.n_consolidations)
            for lyr, w, eng in zip(self.layers, self.weights, self.engines)
        ]

    # -- aggregate stats, mirroring DynamicGridEngine's attributes so the
    #    same backtest/report code can treat an orchestrator like one engine
    @property
    def n_tp(self) -> int:
        return sum(eng.n_tp for eng in self.engines)

    @property
    def n_stopouts(self) -> int:
        return sum(eng.n_stopouts for eng in self.engines)

    @property
    def n_rebuilds(self) -> int:
        return sum(eng.n_rebuilds for eng in self.engines)

    @property
    def n_consolidations(self) -> int:
        return sum(eng.n_consolidations for eng in self.engines)

    @property
    def gross_profit(self) -> float:
        return sum(eng.gross_profit for eng in self.engines)

    @property
    def gross_loss(self) -> float:
        return sum(eng.gross_loss for eng in self.engines)
