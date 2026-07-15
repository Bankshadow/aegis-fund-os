"""Build a versioned read-only operations snapshot for the local dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Mapping

from .fund_v2_store import FundV2Store

SCHEMA_VERSION = 1


def parse_fx_rates(values: list[str]) -> dict[str, float]:
    rates: dict[str, float] = {}
    for value in values:
        pair, separator, raw_rate = value.partition("=")
        if not separator or "/" not in pair or not raw_rate:
            raise ValueError(f"invalid FX rate {value}; expected ASSET/BASE=RATE")
        rate = float(raw_rate)
        if rate <= 0:
            raise ValueError(f"FX rate {pair} must be positive")
        rates[pair.upper()] = rate
    return rates


def build_operations_snapshot(*, report_path: str | Path,
                              exception_store: FundV2Store,
                              portfolio_id: str, report_date: str,
                              reporting_currency: str,
                              fx_rates: Mapping[str, float]) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    exceptions = exception_store.list_exceptions(portfolio_id, report_date)
    open_exceptions = [item for item in exceptions if item["status"] == "open"]
    rates = {pair.upper(): float(rate) for pair, rate in fx_rates.items()}
    if any(rate <= 0 for rate in rates.values()):
        raise ValueError("FX rates must be positive")

    # This is deliberately conservative: the report's cash and marked
    # positions are already in its reporting currency for the current MVP.
    base_value = float(report.get("reporting_cash_balance", 0.0))
    for position in report.get("positions", []):
        mark = position.get("market_price")
        if mark is not None:
            base_value += float(position.get("quantity", 0.0)) * float(mark)

    ready = report.get("status") == "clean" and not open_exceptions and bool(rates)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "ready" if ready else "provisional",
        "source": "persisted_snapshot",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "reportDate": report_date,
        "reportingCurrency": reporting_currency,
        "fx": {
            "reportingCurrency": reporting_currency,
            "asOf": report.get("data_as_of") or report.get("generated_at"),
            "status": "Approved" if ready else "Provisional",
            "totalBaseValue": base_value,
            "rates": [
                {"pair": pair, "rate": rate,
                 "status": "Approved" if ready else "Provisional"}
                for pair, rate in sorted(rates.items())
            ],
        },
        "exceptions": [
            {"id": f"EXC-{item['id']}", "asset": item["asset"],
             "reason": item["reason"], "owner": item["owner"],
             "status": "Open" if item["status"] == "open" else "Resolved",
             **({"approvedBy": item["approved_by"]} if item.get("approved_by") else {})}
            for item in exceptions
        ],
        "quality": {
            "reportStatus": report.get("status", "unknown"),
            "openExceptionCount": len(open_exceptions),
            "fxRateCount": len(rates),
        },
    }


def write_operations_snapshot(snapshot: dict, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                            prefix=f".{target.name}.", delete=False) as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(target)
