"""Run the read-only daily-close workflow from the command line.

Example (PowerShell):
  $env:BINANCE_API_KEY = '...'
  $env:BINANCE_API_SECRET = '...'
  python fund_ops_cli.py --account-id ops-spot --symbol BTCUSDT `
    --mark BTC/USDT=65000 --mark BNB/USDT=600
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dynamic_grid.binance_connector import (ApprovedMarksFeeConverter,
                                             BinanceReadOnlyCredentials,
                                             BinanceSpotReadOnlyConnector)
from dynamic_grid.binance_futures_connector import BinanceUsdmFundingReadOnlyConnector
from dynamic_grid.fund_ops_job import run_read_only_daily_close
from dynamic_grid.fund_storage import SQLiteLedgerStore


def parse_marks(values: list[str]) -> dict[str, float]:
    marks: dict[str, float] = {}
    for value in values:
        try:
            instrument, price = value.split("=", 1)
            marks[instrument.strip()] = float(price)
        except ValueError as error:
            raise argparse.ArgumentTypeError(
                "marks must look like BTC/USDT=65000") from error
    return marks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Binance read-only sync and daily P/L close.")
    parser.add_argument("--account-id", required=True, help="Internal account identifier")
    parser.add_argument("--portfolio-id", default="main")
    parser.add_argument("--source", choices=("spot", "usdm-funding"), default="spot",
                        help="Read-only data source (default: spot)")
    parser.add_argument("--symbol", action="append",
                        help="Binance symbol; repeat for multiple symbols, e.g. BTCUSDT")
    parser.add_argument("--mark", action="append", default=[],
                        help="Approved closing/fee mark, e.g. BTC/USDT=65000 or BNB/USDT=600")
    parser.add_argument("--db", default="results/fund_ops.sqlite")
    parser.add_argument("--report", default="results/fund_ops_daily_report.json")
    parser.add_argument("--reporting-asset", default="USDT")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    marks = parse_marks(args.mark)
    if args.source == "spot" and not args.symbol:
        build_parser().error("--symbol is required when --source spot")
    if args.source == "spot" and not marks:
        build_parser().error("at least one --mark is required when --source spot")
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    credentials = BinanceReadOnlyCredentials.from_environment()
    if args.source == "spot":
        fee_converter = ApprovedMarksFeeConverter(
            marks, reporting_asset=args.reporting_asset)
        connector = BinanceSpotReadOnlyConnector(
            credentials, account_id=args.account_id, portfolio_id=args.portfolio_id,
            symbols=tuple(args.symbol), reporting_asset=args.reporting_asset,
            fee_converter=fee_converter)
    else:
        connector = BinanceUsdmFundingReadOnlyConnector(
            credentials, account_id=args.account_id, portfolio_id=args.portfolio_id,
            reporting_asset=args.reporting_asset, symbols=tuple(args.symbol or ()))
    run = run_read_only_daily_close(
        connector=connector, store=SQLiteLedgerStore(args.db),
        portfolio_id=args.portfolio_id, marks=marks, report_path=args.report)
    print(f"events_inserted={run.events_inserted}")
    print(f"reconciliation={run.reconciliation.status.value}")
    print(f"net_pnl={run.report.net_pnl:.2f}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
