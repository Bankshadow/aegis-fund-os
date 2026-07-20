from datetime import datetime, timezone
import unittest

from dynamic_grid.fund_ops import AppendOnlyLedger, EventType, LedgerEvent
from dynamic_grid.performance import (UNATTRIBUTED, attribute_by_strategy,
                                      benchmark_comparison, money_weighted_return)


def at(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


class MoneyWeightedReturnTests(unittest.TestCase):
    def test_doubling_over_one_year_is_about_100_percent(self):
        rate = money_weighted_return([(at(2026, 1, 1), -1000.0), (at(2027, 1, 1), 2000.0)])
        self.assertAlmostEqual(rate, 1.0, places=3)

    def test_flat_investment_returns_zero(self):
        rate = money_weighted_return([(at(2026, 1, 1), -1000.0), (at(2027, 1, 1), 1000.0)])
        self.assertAlmostEqual(rate, 0.0, places=6)

    def test_loss_is_negative(self):
        rate = money_weighted_return([(at(2026, 1, 1), -1000.0), (at(2027, 1, 1), 900.0)])
        self.assertLess(rate, 0.0)
        self.assertAlmostEqual(rate, -0.1, places=3)

    def test_mid_period_contribution_is_time_weighted_by_date(self):
        # A late contribution has less time to earn, so the rate must exceed the
        # naive profit/total-in ratio.
        flows = [(at(2026, 1, 1), -1000.0), (at(2026, 10, 1), -1000.0), (at(2027, 1, 1), 2200.0)]
        rate = money_weighted_return(flows)
        self.assertGreater(rate, 0.0)
        naive = 200.0 / 2000.0
        self.assertGreater(rate, naive)

    def test_fails_closed_without_two_flows(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            money_weighted_return([(at(2026, 1, 1), -1000.0)])

    def test_fails_closed_when_all_flows_share_a_sign(self):
        with self.assertRaisesRegex(ValueError, "negative and positive"):
            money_weighted_return([(at(2026, 1, 1), -1000.0), (at(2027, 1, 1), -500.0)])


class AttributionTests(unittest.TestCase):
    def fill(self, event_id, side, quantity, price, strategy):
        return LedgerEvent.trade_fill(
            event_id=event_id, external_id=event_id, platform="binance",
            account_id="acct-1", portfolio_id="main", strategy_id=strategy,
            instrument="BTC/USDT", side=side, quantity=quantity, price=price,
            occurred_at=at(2026, 7, 20))

    def test_pnl_is_split_per_strategy_and_sums_to_the_total(self):
        ledger = AppendOnlyLedger()
        # grid: buy 1 @100, sell 1 @120  -> realized +20
        ledger.append(self.fill("g1", "buy", 1.0, 100.0, "grid"))
        ledger.append(self.fill("g2", "sell", 1.0, 120.0, "grid"))
        # short: buy 1 @100, sell 1 @90   -> realized -10
        ledger.append(self.fill("s1", "buy", 1.0, 100.0, "short"))
        ledger.append(self.fill("s2", "sell", 1.0, 90.0, "short"))

        attribution = attribute_by_strategy(ledger, {})
        self.assertEqual(sorted(attribution), ["grid", "short"])
        self.assertAlmostEqual(attribution["grid"].realized_gross_pnl, 20.0)
        self.assertAlmostEqual(attribution["short"].realized_gross_pnl, -10.0)
        # attribution must reconcile with the fund-level engine
        total = ledger.snapshot({}).realized_gross_pnl
        self.assertAlmostEqual(sum(s.realized_gross_pnl for s in attribution.values()), total)

    def test_events_without_a_strategy_are_grouped_not_dropped(self):
        ledger = AppendOnlyLedger()
        ledger.append(LedgerEvent.cash_event(
            event_id="c1", external_id="c1", event_type=EventType.FUNDING,
            platform="binance", account_id="acct-1", portfolio_id="main",
            cash_amount=-5.0, occurred_at=at(2026, 7, 20)))
        attribution = attribute_by_strategy(ledger, {})
        self.assertEqual(list(attribution), [UNATTRIBUTED])
        self.assertAlmostEqual(attribution[UNATTRIBUTED].carry_pnl, -5.0)

    def test_inventory_is_matched_within_a_strategy(self):
        # A sell attributed to a strategy that never bought must fail closed
        # rather than silently borrowing another strategy's inventory.
        ledger = AppendOnlyLedger()
        ledger.append(self.fill("g1", "buy", 1.0, 100.0, "grid"))
        ledger.append(self.fill("x1", "sell", 1.0, 120.0, "other"))
        with self.assertRaisesRegex(ValueError, "exceeds recorded inventory"):
            attribute_by_strategy(ledger, {})


class BenchmarkTests(unittest.TestCase):
    def test_excess_return_over_buy_and_hold(self):
        result = benchmark_comparison(0.10, benchmark_start=100.0, benchmark_end=104.0)
        self.assertAlmostEqual(result.benchmark_return, 0.04)
        self.assertAlmostEqual(result.excess_return, 0.06)
        self.assertTrue(result.outperformed)

    def test_losing_to_the_benchmark_is_not_credited(self):
        result = benchmark_comparison(0.02, benchmark_start=100.0, benchmark_end=110.0)
        self.assertAlmostEqual(result.excess_return, -0.08)
        self.assertFalse(result.outperformed)

    def test_fails_closed_on_non_positive_start(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            benchmark_comparison(0.05, benchmark_start=0.0, benchmark_end=110.0)


if __name__ == "__main__":
    unittest.main()
