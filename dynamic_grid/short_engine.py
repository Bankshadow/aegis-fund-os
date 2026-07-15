"""Short-side dynamic grid: sell rallies inside a falling market, TP below.

Exact mirror of DynamicGridEngine (grid_engine.py):

                       zone stop  (ABOVE the top level)
    sell L5  ─────────────────────
    sell L4  ─────────────────────   levels ABOVE center, spacing = atr_mult*ATR
    sell L3  ─────────────────────   fill when High sweeps a level
    ...
    center   ═════════════════════   built at market
    (TP = entry - tp_mult*spacing, i.e. buy back LOWER)

Mirrored safeguards:
  - trend gate: refuse to build zones against a confirmed UPtrend
    (regime == trend_up, or close > EMA + trend_k*ATR)
  - zone stop ABOVE the zone caps worst-case loss at risk_per_zone
  - momentum confirmation: defer fills during an active up-spike
    (up anomaly bar, or momentum > +entry_m_block)
  - consolidation on UP anomalies: merge pending sell levels upward
  - recenter DOWN: follow the market down when price escapes below

PnL for a short lot: (entry - exit) * size, fees on notional both sides.
Same DecisionLog vocabulary; agent decisions log identically, so the
Virtual Office / Cognee stack works unchanged.

NOTE (honesty): sizing assumes a linear short (futures/margin-style) with
no funding-rate cost. Real perpetual funding would change bear-market
economics materially - flagged in docs as a known limitation.
"""

from .grid_engine import (DynamicGridConfig, _Level, _Lot,
                          has_positive_edge, round_trip_cost_frac)
from .indicators import ATR, AnomalyDetector
from .regime import RegimeDetector, PersistentRegimeDetector, build_detector
from .risk import size_levels


class ShortGridEngine:
    """Short-accumulation grid: sell rallies in the zone, TP one spacing down."""

    def __init__(self, cfg: DynamicGridConfig, logger=None, agent_id="short"):
        self.cfg = cfg
        self.logger = logger
        self.agent_id = agent_id
        self.bar_idx = -1
        self.atr = ATR(cfg.atr_period)
        self.anomaly = AnomalyDetector(cfg.anomaly_z)
        self.detector = build_detector(cfg)
        self.center = None
        self.entries_enabled = True
        self.cooldown = 0
        self.ema = None
        self.spacing = 0.0
        self.stop_price = 0.0
        self.levels: list[_Level] = []
        self.lots: list[_Lot] = []
        self.n_tp = 0
        self.n_stopouts = 0
        self.n_rebuilds = 0
        self.n_consolidations = 0
        self.n_entry_blocks = 0
        self.n_edge_skips = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.builds_by_regime: dict[str, int] = {}

    def _log(self, decision, reason, price, equity, **extra):
        if self.logger is None:
            return
        self.logger.record(bar=self.bar_idx, agent_id=self.agent_id,
                           decision=decision, reason=reason, price=price,
                           regime=self.detector.regime,
                           momentum=self.detector.momentum,
                           equity=equity, extra=extra)

    def _trend_ok(self, price):
        """Mirror: block new zones while the market is in a confirmed UPtrend."""
        direction = getattr(self.detector, "direction", self.detector.regime)
        volatility = getattr(self.detector, "volatility", "normal")
        if ((self.cfg.use_regime_2d or self.cfg.use_regime_pct) and
                self.cfg.block_high_vol_entries and volatility == "high_vol"):
            return False
        if self.cfg.use_regime and direction == "trend_up":
            return False
        if self.ema is None or self.atr.value is None:
            return True
        return price <= self.ema + self.cfg.trend_k * self.atr.value

    def _build(self, price, equity):
        cfg = self.cfg
        risk = cfg.risk_per_zone
        spacing_scale = 1.0
        regime = self.detector.regime if cfg.use_regime else "off"
        if cfg.use_regime:
            volatility = getattr(self.detector, "volatility",
                                 "high_vol" if regime == "high_vol" else "normal")
            direction = getattr(self.detector, "direction", regime)
            if volatility == "high_vol":
                risk *= cfg.hv_risk_scale
                spacing_scale = cfg.hv_spacing_scale
            if direction == "trend_down":  # mirror of long's trend_up boost
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
        prices = [price + self.spacing * (i + 1) for i in range(cfg.levels)]
        self.stop_price = prices[-1] + cfg.stop_mult * self.spacing
        # mirror sizing: worst case is every sell filling then price hitting
        # the stop ABOVE. size_levels works on |level - stop| distances, so
        # feed it mirrored coordinates (negate) to reuse the same math.
        sizes = size_levels(equity, [-p for p in prices], -self.stop_price,
                            risk)
        self.levels = [_Level(i, p, s) for i, (p, s) in enumerate(zip(prices, sizes))]
        self.n_rebuilds += 1
        self._log("build_zone",
                  f"short zone for {regime} regime "
                  f"(risk={risk:.3f}, spacing={self.spacing:.4g})",
                  price, equity, levels=cfg.levels, spacing=self.spacing,
                  stop_price=self.stop_price)

    def _consolidate(self):
        """On an UP anomaly, merge pending sell levels (keep the higher)."""
        pending = [lv for lv in self.levels if lv.pending]
        if len(pending) < 2:
            return
        merged, others = [], [lv for lv in self.levels if not lv.pending]
        for i in range(0, len(pending) - 1, 2):
            a, b = pending[i], pending[i + 1]
            keep = b       # pending sorted ascending idx = ascending price
            keep.size = (a.size + b.size) * self.cfg.consolidation_scale
            merged.append(keep)
        if len(pending) % 2 == 1:
            merged.append(pending[-1])
        self.levels = sorted(others + merged, key=lambda lv: lv.price)
        for i, lv in enumerate(self.levels):
            lv.idx = i
        self.n_consolidations += 1

    def on_bar(self, o, h, l, c, equity):
        cfg = self.cfg
        self.bar_idx += 1
        self.atr.update(h, l, c)
        anom = self.anomaly.update(c, self.atr.value)
        self.detector.update(h, l, c)
        self.ema = c if self.ema is None else \
            self.ema + (2.0 / (cfg.ema_period + 1)) * (c - self.ema)

        if self.center is None:
            if self.cooldown > 0:
                self.cooldown -= 1
            elif not self.entries_enabled:
                return 0.0
            elif self.atr.value is not None and not self._trend_ok(c):
                self._log("skip_build",
                          "uptrend filter / regime blocked a new short zone",
                          c, equity)
            elif self.atr.value is not None:
                self._build(c, equity)
            return 0.0

        realized = 0.0
        if cfg.funding_rate_per_bar and self.lots:
            # Positive perpetual funding is paid by longs and received by
            # shorts.  Negative rates naturally reverse this cash flow.
            funding = self.exposure(o) * cfg.funding_rate_per_bar
            realized += funding
            self.gross_profit += max(funding, 0.0)
            self.gross_loss += max(-funding, 0.0)

        stop_hit = h >= self.stop_price

        # 1) take-profits: buy back lots whose TP (below entry) was reached
        still_open = []
        for lot in self.lots:
            if lot.tp >= l and not (cfg.conservative_intrabar and stop_hit):
                fees = (lot.tp * lot.size * cfg.fee_rate
                        if cfg.book_entry_fees_immediately else
                        (lot.tp + lot.entry) * lot.size * cfg.fee_rate)
                pnl = (lot.entry - lot.tp) * lot.size - fees
                realized += pnl
                self.gross_profit += max(pnl, 0.0)
                self.gross_loss += max(-pnl, 0.0)
                self.n_tp += 1
                self._log("take_profit", "short lot bought back at its TP",
                          lot.tp, equity + realized, pnl=pnl)
                if lot.level in self.levels:
                    lot.level.pending = True
            else:
                still_open.append(lot)
        self.lots = still_open

        # 2) sell fills: pending levels swept by the bar's high,
        #    unless an up-spike is in progress (mirrored momentum confirm)
        rallying = (not self.entries_enabled) or (
            cfg.momentum_confirm and (
                anom == 1 or self.detector.momentum > cfg.entry_m_block))
        if not rallying:
            for lv in self.levels:
                if lv.pending and h >= lv.price:
                    lv.pending = False
                    self.lots.append(_Lot(lv, lv.price, lv.size,
                                          lv.price - cfg.tp_mult * self.spacing))
                    if cfg.book_entry_fees_immediately:
                        entry_fee = lv.price * lv.size * cfg.fee_rate
                        realized -= entry_fee
                        self.gross_loss += entry_fee
                    self._log("fill", "price swept a pending sell level",
                              lv.price, equity + realized, size=lv.size)
        else:
            self.n_entry_blocks += 1
            if any(lv.pending and h >= lv.price for lv in self.levels):
                self._log("entry_block",
                          "momentum confirmation deferred fill during rally",
                          c, equity + realized)

        # 3) zone stop ABOVE: cut everything, pause, wait out the squeeze
        if stop_hit:
            slip = max(cfg.stop_slippage_bps, 0.0) / 10_000.0
            base_stop_fill = (max(self.stop_price, o)
                              if cfg.conservative_intrabar else self.stop_price)
            stop_fill = base_stop_fill * (1.0 + slip)
            for lot in self.lots:
                fees = (stop_fill * lot.size * cfg.fee_rate
                        if cfg.book_entry_fees_immediately else
                        (stop_fill + lot.entry) * lot.size * cfg.fee_rate)
                pnl = (lot.entry - stop_fill) * lot.size - fees
                realized += pnl
                self.gross_loss += max(-pnl, 0.0)
                self.gross_profit += max(pnl, 0.0)
                self.n_stopouts += 1
            self._log("stop_out",
                      f"rally hit short-zone stop; cut {len(self.lots)} lots, "
                      f"cooldown {cfg.cooldown_bars} bars",
                      self.stop_price, equity + realized,
                      cut_lots=len(self.lots))
            self.lots = []
            self.center = None
            self.cooldown = cfg.cooldown_bars
            return realized

        # 4) up anomaly -> consolidate remaining sell orders upward
        if anom == 1:
            before = len([lv for lv in self.levels if lv.pending])
            self._consolidate()
            if before >= 2:
                self._log("consolidate",
                          f"up anomaly (>{cfg.anomaly_z}xATR) merged pending "
                          f"sells, accumulating higher", c, equity + realized)

        # 5) price escaped BELOW the zone -> recenter down, follow the market
        bottom = self.center - cfg.shift_trigger * self.spacing
        if self.entries_enabled and c <= bottom and not self.lots:
            self._log("recenter", "price escaped below zone, following down",
                      c, equity + realized)
            self._build(c, equity + realized)

        return realized

    def unrealized(self, price):
        return sum((lot.entry - price) * lot.size for lot in self.lots)

    def exposure(self, price):
        return sum(lot.size for lot in self.lots) * price

    def liquidate(self, price):
        cfg = self.cfg
        slip = max(cfg.stop_slippage_bps, 0.0) / 10_000.0
        fill = price * (1.0 + slip)
        realized = 0.0
        for lot in self.lots:
            fees = (fill * lot.size * cfg.fee_rate
                    if cfg.book_entry_fees_immediately else
                    (fill + lot.entry) * lot.size * cfg.fee_rate)
            pnl = (lot.entry - fill) * lot.size - fees
            realized += pnl
            self.gross_profit += max(pnl, 0.0)
            self.gross_loss += max(-pnl, 0.0)
        self.lots = []
        return realized
