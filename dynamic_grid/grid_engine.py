"""Adaptive (dynamic) grid construction and lifecycle.

Key ideas implemented here, mirroring the design notes:

1. Grid Construction ปรับตามพฤติกรรมราคา
   - order distance (spacing) = atr_mult * ATR ณ เวลาสร้างโซน
   - โซนใหม่จะกว้าง/แคบตาม volatility ขณะนั้น ไม่ fix ตายตัว

2. Zone ไม่คงที่ + Risk per Zone
   - worst-case loss ของทั้งโซนถูกจำกัดไว้ที่ risk_per_zone ของ equity
   - เมื่อราคาหลุด zone stop -> ตัดขาดทุนทั้งโซน แล้วสร้างโซนใหม่ที่ราคาปัจจุบัน
     (แก้ปัญหา "โดนลาก" / drawdown 80-90% ของกริดคงที่)

3. Zone consolidation เมื่อเจอ Price Anomaly
   - เมื่อแท่งราคาเคลื่อนผิดปกติ (>z*ATR) จะรวบ order level ที่ยังไม่ fill
     เป็นครึ่งหนึ่ง แต่ position size ต่อไม้ใหญ่ขึ้น (สะสมทบ)
"""

from dataclasses import dataclass, field

from .indicators import ATR, AnomalyDetector
from .regime import RegimeDetector, PersistentRegimeDetector, build_detector
from .risk import size_levels


@dataclass
class DynamicGridConfig:
    levels: int = 6              # จำนวน buy level ต่อโซน
    atr_period: int = 14
    atr_mult: float = 1.5        # order distance = atr_mult * ATR
    risk_per_zone: float = 0.04  # ความเสี่ยงสูงสุดต่อโซน (สัดส่วนของ equity)
    stop_mult: float = 1.0       # zone stop อยู่ต่ำกว่า level ล่างสุด stop_mult*spacing
    shift_trigger: float = 2.0   # recenter เมื่อราคาพ้นขอบบนโซน trigger*spacing
    anomaly_z: float = 3.0       # เกณฑ์ตรวจ price anomaly (เท่าของ ATR)
    consolidation_scale: float = 1.0  # ตัวคูณ size ตอนรวบโซน (1.0 = รวม budget เดิม)
    cooldown_bars: int = 20      # พักหลังโดน zone stop ก่อนสร้างโซนใหม่ (กัน whipsaw)
    tp_mult: float = 1.0         # ระยะ take-profit = tp_mult * spacing
    ema_period: int = 50         # trend filter reference
    trend_k: float = 2.0         # ห้ามสร้างโซนใหม่ถ้า close < EMA - trend_k*ATR
    fee_rate: float = 0.0005     # ค่าธรรมเนียมต่อ notional ต่อข้าง
    # -- regime adaptation (v2) --
    use_regime: bool = True      # เปิด/ปิดการปรับตาม market regime
    regime_m_threshold: float = 0.5   # เกณฑ์ momentum แยก trend/sideways
    regime_vol_hi: float = 1.4        # เกณฑ์ ATR_fast/ATR_slow เข้าโหมด high_vol
    hv_risk_scale: float = 0.5        # high_vol: ลด risk budget ต่อโซน
    hv_spacing_scale: float = 1.4     # high_vol: ถ่างกริดกว้างขึ้น
    up_risk_scale: float = 1.2        # trend_up: เพิ่ม risk budget เล็กน้อย
    # -- state-based momentum confirmation (v3.1) --
    momentum_confirm: bool = False    # ระงับ fill ชั่วคราวขณะตลาดกำลังเทขาย
    entry_m_block: float = 1.0        # ระงับ fill เมื่อ momentum < -entry_m_block
    # -- persistent two-dimensional regime model (research v4) --
    use_regime_2d: bool = False
    regime_confirm_bars: int = 3
    regime_min_dwell_bars: int = 5
    regime_hysteresis: float = 0.7
    block_high_vol_entries: bool = False
    # -- scale-invariant percentile-rank regime (v4, E14) --
    use_regime_pct: bool = False       # เปิดใช้ percentile-rank แทน fixed threshold
    regime_pct_window: int = 250       # จำนวนแท่งใน rolling distribution
    regime_trend_pct: float = 0.85     # percentile ที่ถือว่า momentum สุดขั้ว = trend
    regime_vol_pct: float = 0.85       # percentile ที่ถือว่า vol_ratio สุดขั้ว = high_vol
    # -- execution realism (all zero/False preserves legacy results) --
    conservative_intrabar: bool = False
    stop_slippage_bps: float = 0.0
    funding_rate_per_bar: float = 0.0
    book_entry_fees_immediately: bool = False
    # -- edge filter before zone build (E16; default off = legacy) --
    require_edge: bool = False         # อย่าวางโซนถ้า TP ไม่คุ้ม round-trip
    edge_min_multiple: float = 1.0     # tp_frac ต้อง >= multiple * rt_frac
    half_spread: float = 0.0           # แยกจาก fee เมื่อยังไม่ bake เข้า fee_rate
    # -- funding directional bias (E17; default off = legacy) --
    use_funding_bias: bool = False     # เอียง long/short จาก funding สุดขั้ว
    funding_pct_window: int = 90       # trailing window สำหรับ percentile-rank
    funding_extreme_pct: float = 0.85  # rank สุดขั้วที่ถือว่า overcrowded
    # -- cross-asset relative value (E18; default off = legacy) --
    use_relative_value: bool = False   # แทน direction ด้วย alt/BTC momentum
    relative_pct_window: int = 90
    relative_extreme_pct: float = 0.85
    relative_lookback: int = 20        # bars ใน log-ratio momentum


def round_trip_cost_frac(cfg: DynamicGridConfig) -> float:
    """Round-trip cost as a fraction of price: 2*fee + 2*half_spread.

    When multiasset demos bake CS half-spread into ``fee_rate``, leave
    ``half_spread=0``. When ``ExecutionProfile`` keeps spread separate,
    set ``half_spread`` from the dataset.
    """
    return 2.0 * max(cfg.fee_rate, 0.0) + 2.0 * max(cfg.half_spread, 0.0)


def has_positive_edge(price: float, spacing: float,
                      cfg: DynamicGridConfig) -> bool:
    """True when TP distance covers round-trip cost by ``edge_min_multiple``."""
    if price <= 0 or spacing <= 0:
        return False
    tp_frac = (cfg.tp_mult * spacing) / price
    rt_frac = round_trip_cost_frac(cfg)
    if rt_frac <= 0:
        return True
    return tp_frac >= max(cfg.edge_min_multiple, 0.0) * rt_frac


@dataclass
class _Level:
    idx: int
    price: float
    size: float
    pending: bool = True


@dataclass
class _Lot:
    level: "_Level"
    entry: float
    size: float
    tp: float


class DynamicGridEngine:
    """Long-accumulation grid: buy dips inside the zone, TP one spacing up."""

    def __init__(self, cfg: DynamicGridConfig, logger=None, agent_id="grid"):
        self.cfg = cfg
        # Optional structured decision logging (opt-in; None = zero behaviour
        # change, so all prior tests/results reproduce). See event_log.py.
        self.logger = logger
        self.agent_id = agent_id
        self.bar_idx = -1
        self.atr = ATR(cfg.atr_period)
        self.anomaly = AnomalyDetector(cfg.anomaly_z)
        self.detector = build_detector(cfg)
        self.center: float | None = None
        self.entries_enabled: bool = True
        self.cooldown: int = 0
        self.ema: float | None = None
        self.spacing: float = 0.0
        self.stop_price: float = 0.0
        self.levels: list[_Level] = []
        self.lots: list[_Lot] = []
        # stats
        self.n_tp = 0
        self.n_stopouts = 0
        self.n_rebuilds = 0
        self.n_consolidations = 0
        self.n_entry_blocks = 0
        self.n_edge_skips = 0
        self.gross_profit = 0.0   # รวมกำไรจากไม้ TP (หลังหักค่าธรรมเนียม)
        self.gross_loss = 0.0     # รวมขาดทุนจากไม้ stop-out (ค่าบวก)
        self.builds_by_regime: dict[str, int] = {}

    def _log(self, decision: str, reason: str, price: float, equity: float,
             **extra) -> None:
        """Emit a structured decision event (no-op when no logger attached)."""
        if self.logger is None:
            return
        self.logger.record(
            bar=self.bar_idx, agent_id=self.agent_id, decision=decision,
            reason=reason, price=price,
            regime=self.detector.regime, momentum=self.detector.momentum,
            equity=equity, extra=extra)

    def _trend_ok(self, price: float) -> bool:
        """Block new zones while price is deep below the EMA (steep downtrend)."""
        direction = getattr(self.detector, "direction", self.detector.regime)
        volatility = getattr(self.detector, "volatility", "normal")
        if ((self.cfg.use_regime_2d or self.cfg.use_regime_pct) and
                self.cfg.block_high_vol_entries and volatility == "high_vol"):
            return False
        if self.cfg.use_regime and direction == "trend_down":
            return False                      # ไม่วางกริดสวนขาลงที่ยืนยันแล้ว
        if self.ema is None or self.atr.value is None:
            return True
        return price >= self.ema - self.cfg.trend_k * self.atr.value

    # -- zone construction -------------------------------------------------
    def _build(self, price: float, equity: float) -> None:
        cfg = self.cfg
        risk = cfg.risk_per_zone
        spacing_scale = 1.0
        regime = self.detector.regime if cfg.use_regime else "off"
        if cfg.use_regime:
            volatility = getattr(self.detector, "volatility",
                                 "high_vol" if regime == "high_vol" else "normal")
            direction = getattr(self.detector, "direction", regime)
            if volatility == "high_vol":  # volatility and trend can coexist
                risk *= cfg.hv_risk_scale
                spacing_scale = cfg.hv_spacing_scale
            if direction == "trend_up":   # ขาขึ้น: เพิ่ม budget เล็กน้อย
                risk *= cfg.up_risk_scale

        self.spacing = max(cfg.atr_mult * spacing_scale * self.atr.value,
                           price * 1e-5)
        if cfg.require_edge and not has_positive_edge(price, self.spacing, cfg):
            self.n_edge_skips += 1
            self.center = None
            self.levels = []
            self.stop_price = 0.0
            self._log("edge_skip",
                      f"TP distance below round-trip cost "
                      f"(spacing={self.spacing:.4g}, "
                      f"rt={round_trip_cost_frac(cfg):.4g})",
                      price, equity, spacing=self.spacing,
                      rt_frac=round_trip_cost_frac(cfg))
            return

        self.builds_by_regime[regime] = self.builds_by_regime.get(regime, 0) + 1
        self.center = price
        prices = [price - self.spacing * (i + 1) for i in range(cfg.levels)]
        self.stop_price = prices[-1] - cfg.stop_mult * self.spacing
        sizes = size_levels(equity, prices, self.stop_price, risk)
        self.levels = [_Level(i, p, s) for i, (p, s) in enumerate(zip(prices, sizes))]
        self.n_rebuilds += 1
        self._log("build_zone",
                  f"ATR spacing set for {regime} regime "
                  f"(risk={risk:.3f}, spacing={self.spacing:.4g})",
                  price, equity, levels=cfg.levels, spacing=self.spacing,
                  stop_price=self.stop_price)

    def _consolidate(self) -> None:
        """Merge adjacent pending levels: half the orders, bigger size each."""
        pending = [lv for lv in self.levels if lv.pending]
        if len(pending) < 2:
            return
        merged, others = [], [lv for lv in self.levels if not lv.pending]
        for i in range(0, len(pending) - 1, 2):
            a, b = pending[i], pending[i + 1]
            keep = b  # keep the lower level: accumulate deeper into the move
            keep.size = (a.size + b.size) * self.cfg.consolidation_scale
            merged.append(keep)
        if len(pending) % 2 == 1:
            merged.append(pending[-1])
        self.levels = sorted(others + merged, key=lambda lv: -lv.price)
        for i, lv in enumerate(self.levels):
            lv.idx = i
        self.n_consolidations += 1

    # -- per-bar processing -------------------------------------------------
    def on_bar(self, o: float, h: float, l: float, c: float,
               equity: float) -> float:
        """Process one bar; returns realized PnL (fees included)."""
        cfg = self.cfg
        self.bar_idx += 1
        self.atr.update(h, l, c)
        anom = self.anomaly.update(c, self.atr.value)
        self.detector.update(h, l, c)
        if self.ema is None:
            self.ema = c
        else:
            self.ema += (2.0 / (cfg.ema_period + 1)) * (c - self.ema)

        if self.center is None:
            if self.cooldown > 0:
                self.cooldown -= 1
            elif not self.entries_enabled:
                return 0.0
            elif self.atr.value is not None and not self._trend_ok(c):
                self._log("skip_build",
                          "trend filter / regime blocked a new zone",
                          c, equity)
            elif self.atr.value is not None:
                self._build(c, equity)
            return 0.0

        realized = 0.0
        if cfg.funding_rate_per_bar and self.lots:
            funding = self.exposure(o) * cfg.funding_rate_per_bar
            realized -= funding
            self.gross_loss += max(funding, 0.0)

        stop_hit = l <= self.stop_price

        # 1) take-profits on existing lots (lot bought earlier, tp reached)
        still_open = []
        for lot in self.lots:
            if lot.tp <= h and not (cfg.conservative_intrabar and stop_hit):
                fees = (lot.tp * lot.size * cfg.fee_rate
                        if cfg.book_entry_fees_immediately else
                        (lot.tp + lot.entry) * lot.size * cfg.fee_rate)
                pnl = (lot.tp - lot.entry) * lot.size - fees
                realized += pnl
                self.gross_profit += max(pnl, 0.0)
                self.gross_loss += max(-pnl, 0.0)
                self.n_tp += 1
                self._log("take_profit", "lot reached its TP", lot.tp,
                          equity + realized, pnl=pnl)
                if lot.level in self.levels:    # re-arm the level for reuse
                    lot.level.pending = True
            else:
                still_open.append(lot)
        self.lots = still_open

        # 2) buy fills: any pending level swept by the bar's low.
        #    Momentum confirmation: while the market is actively selling off
        #    (down anomaly bar, or momentum deeply negative), price level
        #    alone is not a reason to buy - levels stay pending and can
        #    fill on a later, calmer bar instead. (state-based entry)
        selling_off = (not self.entries_enabled) or (
            cfg.momentum_confirm and (
                anom == -1 or self.detector.momentum < -cfg.entry_m_block))
        if not selling_off:
            for lv in self.levels:
                if lv.pending and l <= lv.price:
                    lv.pending = False
                    self.lots.append(_Lot(lv, lv.price, lv.size,
                                          lv.price + cfg.tp_mult * self.spacing))
                    if cfg.book_entry_fees_immediately:
                        entry_fee = lv.price * lv.size * cfg.fee_rate
                        realized -= entry_fee
                        self.gross_loss += entry_fee
                    self._log("fill", "price swept a pending buy level",
                              lv.price, equity + realized, size=lv.size)
        else:
            self.n_entry_blocks += 1
            if any(lv.pending and l <= lv.price for lv in self.levels):
                self._log("entry_block",
                          "momentum confirmation deferred fill during sell-off",
                          c, equity + realized)

        # 3) zone stop: cut the whole zone, pause, then rebuild at market
        if stop_hit:
            slip = max(cfg.stop_slippage_bps, 0.0) / 10_000.0
            base_stop_fill = (min(self.stop_price, o)
                              if cfg.conservative_intrabar else self.stop_price)
            stop_fill = base_stop_fill * (1.0 - slip)
            for lot in self.lots:
                fees = (stop_fill * lot.size * cfg.fee_rate
                        if cfg.book_entry_fees_immediately else
                        (stop_fill + lot.entry) * lot.size * cfg.fee_rate)
                pnl = (stop_fill - lot.entry) * lot.size - fees
                realized += pnl
                self.gross_loss += max(-pnl, 0.0)
                self.gross_profit += max(pnl, 0.0)
                self.n_stopouts += 1
            self._log("stop_out",
                      f"price hit zone stop; cut {len(self.lots)} lots, "
                      f"cooldown {cfg.cooldown_bars} bars",
                      self.stop_price, equity + realized, cut_lots=len(self.lots))
            self.lots = []
            self.center = None                  # wait out the move
            self.cooldown = cfg.cooldown_bars
            return realized

        # 4) price anomaly -> consolidate remaining orders (รวบโซน/สะสมทบ)
        if anom == -1:
            before = len([lv for lv in self.levels if lv.pending])
            self._consolidate()
            if before >= 2:
                self._log("consolidate",
                          f"down anomaly (>{cfg.anomaly_z}xATR) merged pending "
                          f"orders, accumulating deeper", c, equity + realized)

        # 5) price escaped above the zone -> recenter (follow the market up)
        top = self.center + cfg.shift_trigger * self.spacing
        if self.entries_enabled and c >= top and not self.lots:
            self._log("recenter", "price escaped above zone, following up",
                      c, equity + realized)
            self._build(c, equity + realized)

        return realized

    def unrealized(self, price: float) -> float:
        return sum((price - lot.entry) * lot.size for lot in self.lots)

    def exposure(self, price: float) -> float:
        return sum(lot.size for lot in self.lots) * price

    def liquidate(self, price: float) -> float:
        """Close all open lots at an adverse market price at test end."""
        cfg = self.cfg
        slip = max(cfg.stop_slippage_bps, 0.0) / 10_000.0
        fill = price * (1.0 - slip)
        realized = 0.0
        for lot in self.lots:
            fees = (fill * lot.size * cfg.fee_rate
                    if cfg.book_entry_fees_immediately else
                    (fill + lot.entry) * lot.size * cfg.fee_rate)
            pnl = (fill - lot.entry) * lot.size - fees
            realized += pnl
            self.gross_profit += max(pnl, 0.0)
            self.gross_loss += max(-pnl, 0.0)
        self.lots = []
        return realized


class StaticGridEngine(DynamicGridEngine):
    """Classic fixed grid baseline: built once, never recenters, never stops.

    Same sizing model for a fair comparison, but it holds losing lots
    through any move - the behaviour that produces 80-90% drawdowns.
    """

    def on_bar(self, o, h, l, c, equity):
        cfg = self.cfg
        self.atr.update(h, l, c)
        if self.center is None:
            if self.atr.value is not None:
                self._build(c, equity)
                self.stop_price = -1e18  # disable the zone stop
            return 0.0

        realized = 0.0
        still_open = []
        for lot in self.lots:
            if lot.tp <= h:
                pnl = ((lot.tp - lot.entry) * lot.size
                       - (lot.tp + lot.entry) * lot.size * cfg.fee_rate)
                realized += pnl
                self.gross_profit += max(pnl, 0.0)
                self.gross_loss += max(-pnl, 0.0)
                self.n_tp += 1
                if lot.level in self.levels:
                    lot.level.pending = True
            else:
                still_open.append(lot)
        self.lots = still_open

        for lv in self.levels:
            if lv.pending and l <= lv.price:
                lv.pending = False
                self.lots.append(_Lot(lv, lv.price, lv.size,
                                      lv.price + cfg.tp_mult * self.spacing))
        return realized
