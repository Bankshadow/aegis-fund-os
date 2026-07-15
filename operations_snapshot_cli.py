"""CLI for exporting persisted fund-ops data to a dashboard snapshot."""

from __future__ import annotations

import argparse

from dynamic_grid.fund_v2_store import FundV2Store
from dynamic_grid.operations_snapshot import (build_operations_snapshot,
                                               parse_fx_rates,
                                               write_operations_snapshot)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--exceptions-db", required=True)
    parser.add_argument("--portfolio-id", required=True)
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--reporting-currency", default="USD")
    parser.add_argument("--fx", action="append", default=[], metavar="ASSET/BASE=RATE")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = build_operations_snapshot(
        report_path=args.report, exception_store=FundV2Store(args.exceptions_db),
        portfolio_id=args.portfolio_id, report_date=args.report_date,
        reporting_currency=args.reporting_currency.upper(),
        fx_rates=parse_fx_rates(args.fx))
    write_operations_snapshot(snapshot, args.output)
    print(f"wrote {args.output} ({snapshot['status']})")


if __name__ == "__main__":
    main()
