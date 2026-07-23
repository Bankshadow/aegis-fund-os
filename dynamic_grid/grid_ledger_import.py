"""Import D1 grid fills into the fund-ops ledger.

The other half of the bridge described in ``docs/FIRST_REAL_TRACK_RECORD.md``
§ P2.  Grid execution is recorded in Cloudflare D1 by the TypeScript worker;
NAV, XIRR and strategy attribution live here.  ``grid-ledger-export.ts``
produces a versioned document, this module validates it and folds it into an
``AppendOnlyLedger``.

The validator is deliberately strict.  Anything it cannot represent faithfully
is refused, because the point of the exercise is a track record that can be
trusted, not one that is merely complete.  In particular an export that still
carries rejected rows is refused outright: a partial ledger that looks whole is
worse than an obvious failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .fund_ops import AppendOnlyLedger, LedgerEvent

SUPPORTED_VERSION = 1

_REQUIRED_DOCUMENT_KEYS = (
    "version",
    "generatedAt",
    "platform",
    "accountId",
    "portfolioId",
    "reportingCurrency",
    "fills",
    "rejected",
    "sourceRowCount",
)

_REQUIRED_FILL_KEYS = (
    "externalId",
    "exchangeOrderId",
    "strategyId",
    "platform",
    "accountId",
    "portfolioId",
    "instrument",
    "side",
    "quantity",
    "price",
    "fee",
    "feeAsset",
    "occurredAt",
    "sourceRef",
)


class GridLedgerImportError(ValueError):
    """The export cannot be trusted; nothing was written to the ledger."""


@dataclass(frozen=True)
class ImportResult:
    """What actually happened, so a caller never has to assume."""

    appended: int
    duplicates: int
    events: tuple[LedgerEvent, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GridLedgerImportError(message)


def _parse_timestamp(value: Any, field: str) -> datetime:
    _require(isinstance(value, str) and value, f"{field} must be a non-empty string")
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:  # pragma: no cover - message varies by input
        raise GridLedgerImportError(f"{field} is not an ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise GridLedgerImportError(f"{field} must be timezone-aware: {value!r}")
    return parsed.astimezone(timezone.utc)


def _parse_number(value: Any, field: str, *, positive: bool) -> float:
    _require(isinstance(value, (str, int, float)), f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GridLedgerImportError(f"{field} is not a number: {value!r}") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise GridLedgerImportError(f"{field} is not finite: {value!r}")
    if positive and number <= 0:
        raise GridLedgerImportError(f"{field} must be positive: {value!r}")
    if not positive and number < 0:
        raise GridLedgerImportError(f"{field} must not be negative: {value!r}")
    return number


def parse_grid_ledger_export(document: Mapping[str, Any]) -> tuple[LedgerEvent, ...]:
    """Validate an export document and convert it to ledger events.

    Raises ``GridLedgerImportError`` and converts nothing if the document is not
    exactly what this importer understands.
    """
    _require(isinstance(document, Mapping), "export must be a mapping")
    missing = [key for key in _REQUIRED_DOCUMENT_KEYS if key not in document]
    _require(not missing, f"export is missing keys: {', '.join(missing)}")
    _require(
        document["version"] == SUPPORTED_VERSION,
        f"unsupported export version {document['version']!r}; expected {SUPPORTED_VERSION}",
    )

    rejected = document["rejected"]
    _require(isinstance(rejected, Sequence) and not isinstance(rejected, str),
             "rejected must be a list")
    # A partial import would produce a ledger that reconciles against nothing
    # and a NAV that is quietly wrong. Refuse the whole document instead.
    _require(
        len(rejected) == 0,
        f"export carries {len(rejected)} rejected row(s); resolve them at the source "
        "before importing (see docs/FIRST_REAL_TRACK_RECORD.md § P2)",
    )

    reporting_currency = document["reportingCurrency"]
    _require(isinstance(reporting_currency, str) and reporting_currency,
             "reportingCurrency must be a non-empty string")

    fills = document["fills"]
    _require(isinstance(fills, Sequence) and not isinstance(fills, str), "fills must be a list")
    _require(
        document["sourceRowCount"] == len(fills),
        f"sourceRowCount {document['sourceRowCount']!r} does not match {len(fills)} fill(s); "
        "the export is inconsistent with itself",
    )

    events: list[LedgerEvent] = []
    seen: set[str] = set()
    for index, fill in enumerate(fills):
        where = f"fills[{index}]"
        _require(isinstance(fill, Mapping), f"{where} must be a mapping")
        absent = [key for key in _REQUIRED_FILL_KEYS if key not in fill]
        _require(not absent, f"{where} is missing keys: {', '.join(absent)}")

        external_id = fill["externalId"]
        _require(isinstance(external_id, str) and external_id,
                 f"{where}.externalId must be a non-empty string")
        # Duplicates inside one document are a producer bug, not a replay.
        _require(external_id not in seen, f"{where}.externalId {external_id!r} is duplicated")
        seen.add(external_id)

        side = fill["side"]
        _require(side in ("buy", "sell"), f"{where}.side must be 'buy' or 'sell'")

        fee_asset = fill["feeAsset"]
        fee = _parse_number(fill["fee"], f"{where}.fee", positive=False)
        # Mirrors the exporter's rule. Checked again here because this module is
        # the last gate before the number becomes a track record.
        _require(
            fee == 0 or fee_asset == reporting_currency,
            f"{where}.fee is charged in {fee_asset!r} but the reporting currency is "
            f"{reporting_currency!r}; an operator-approved mark is required",
        )

        instrument = fill["instrument"]
        _require(isinstance(instrument, str) and instrument,
                 f"{where}.instrument must be a non-empty string")
        strategy_id = fill["strategyId"]
        _require(isinstance(strategy_id, str) and strategy_id,
                 f"{where}.strategyId must be a non-empty string")

        events.append(
            LedgerEvent.trade_fill(
                event_id=f"grid-{external_id}",
                external_id=external_id,
                platform=str(fill["platform"]),
                account_id=str(fill["accountId"]),
                portfolio_id=str(fill["portfolioId"]),
                instrument=instrument,
                side=side,
                quantity=_parse_number(fill["quantity"], f"{where}.quantity", positive=True),
                price=_parse_number(fill["price"], f"{where}.price", positive=True),
                fee=fee,
                strategy_id=strategy_id,
                source_ref=str(fill["sourceRef"]),
                occurred_at=_parse_timestamp(fill["occurredAt"], f"{where}.occurredAt"),
            )
        )

    return tuple(events)


def import_grid_fills(ledger: AppendOnlyLedger, document: Mapping[str, Any]) -> ImportResult:
    """Fold a validated export into ``ledger``.

    Validation happens in full before anything is appended, so a malformed
    document leaves the ledger untouched rather than half-written.  Re-importing
    the same export appends nothing: the exporter's idempotency key is the
    deterministic clientOrderId, and the ledger already refuses a repeat.
    """
    events = parse_grid_ledger_export(document)
    appended = 0
    for event in events:
        if ledger.append(event):
            appended += 1
    return ImportResult(appended=appended, duplicates=len(events) - appended, events=events)
