"""Honest baselines used by the research framework."""


class CashBenchmark:
    """A no-trade benchmark; it must be allowed to win a bad strategy contest."""

    n_tp = n_stopouts = n_rebuilds = n_consolidations = 0
    gross_profit = gross_loss = 0.0

    def on_bar(self, o, h, l, c, equity):
        return 0.0

    def unrealized(self, price):
        return 0.0

    def liquidate(self, price):
        return 0.0


class BuyHoldBenchmark:
    """One-times buy-and-hold benchmark with the same entry/exit fee model."""

    n_tp = n_stopouts = n_rebuilds = n_consolidations = 0

    def __init__(self, fee_rate: float = 0.0):
        self.fee_rate = fee_rate
        self.entry = None
        self.units = 0.0
        self.closed = False
        self.gross_profit = 0.0
        self.gross_loss = 0.0

    def on_bar(self, o, h, l, c, equity):
        if self.entry is None:
            self.entry = float(o)
            self.units = equity / self.entry if self.entry > 0 else 0.0
            fee = self.units * self.entry * self.fee_rate
            self.gross_loss += fee
            return -fee
        return 0.0

    def unrealized(self, price):
        if self.entry is None or self.closed:
            return 0.0
        return self.units * (price - self.entry)

    def liquidate(self, price):
        if self.entry is None or self.closed:
            return 0.0
        self.closed = True
        pnl = self.units * (price - self.entry) - self.units * price * self.fee_rate
        if pnl >= 0:
            self.gross_profit += pnl
        else:
            self.gross_loss += -pnl
        return pnl
