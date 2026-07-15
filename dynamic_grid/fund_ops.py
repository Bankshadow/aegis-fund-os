"""Fund-operations MVP primitives.

This module is deliberately execution-free.  It supplies the accounting and
read-only integration boundary needed to build a verifiable track record
before adding paper or live trading.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Mapping, Protocol, Sequence


class EventType(str, Enum):
    TRADE_FILL = "trade_fill"
    DERIVATIVE_FILL = "derivative_fill"
    FUNDING = "funding"
    INTEREST = "interest"
    REBATE = "rebate"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True)
class LedgerEvent:
    """One immutable source-backed financial event.

    Amounts are expressed in the ledger reporting currency for this MVP.
    `external_id` is the idempotency key supplied by the source platform.
    Transfers affect cash but never performance P/L.
    """

    event_id: str
    external_id: str
    occurred_at: datetime
    event_type: EventType
    platform: str
    account_id: str
    portfolio_id: str
    strategy_id: str | None = None
    instrument: str | None = None
    side: str | None = None
    quantity: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    cash_amount: float = 0.0
    source_ref: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if not self.event_id or not self.external_id:
            raise ValueError("event_id and external_id are required")
        if self.event_type in {EventType.TRADE_FILL, EventType.DERIVATIVE_FILL}:
            if self.side not in {"buy", "sell"}:
                raise ValueError("trade fills require side 'buy' or 'sell'")
            if not self.instrument or self.quantity <= 0 or self.price <= 0:
                raise ValueError("trade fills require instrument, positive quantity and price")
        elif self.side is not None:
            raise ValueError("only trade fills may have a side")

    @classmethod
    def trade_fill(cls, *, event_id: str, external_id: str, platform: str,
                   account_id: str, portfolio_id: str, instrument: str,
                   side: str, quantity: float, price: float, fee: float = 0.0,
                   strategy_id: str | None = None, source_ref: str | None = None,
                   occurred_at: datetime | None = None) -> "LedgerEvent":
        return cls(event_id, external_id, occurred_at or datetime.now(timezone.utc),
                   EventType.TRADE_FILL, platform, account_id, portfolio_id,
                   strategy_id, instrument, side, quantity, price, fee, 0.0,
                   source_ref)

    @classmethod
    def derivative_fill(cls, **kwargs) -> "LedgerEvent":
        event = cls.trade_fill(**kwargs)
        return cls(event.event_id, event.external_id, event.occurred_at,
                   EventType.DERIVATIVE_FILL, event.platform, event.account_id,
                   event.portfolio_id, event.strategy_id, event.instrument, event.side,
                   event.quantity, event.price, event.fee, event.cash_amount,
                   event.source_ref, event.metadata)

    @classmethod
    def cash_event(cls, *, event_id: str, external_id: str, event_type: EventType,
                   platform: str, account_id: str, portfolio_id: str,
                   cash_amount: float, strategy_id: str | None = None,
                   source_ref: str | None = None,
                   occurred_at: datetime | None = None) -> "LedgerEvent":
        if event_type is EventType.TRADE_FILL:
            raise ValueError("use trade_fill for trade events")
        return cls(event_id, external_id, occurred_at or datetime.now(timezone.utc),
                   event_type, platform, account_id, portfolio_id, strategy_id,
                   cash_amount=cash_amount, source_ref=source_ref)


@dataclass(frozen=True)
class Position:
    instrument: str
    quantity: float
    average_cost: float
    market_price: float | None
    unrealized_gross_pnl: float
    kind: str = "spot"


@dataclass(frozen=True)
class PnLSnapshot:
    realized_gross_pnl: float
    unrealized_gross_pnl: float
    trade_fees: float
    carry_pnl: float
    adjustment_pnl: float
    net_pnl: float
    reporting_cash_balance: float
    positions: tuple[Position, ...]


class AppendOnlyLedger:
    """In-memory, idempotent ledger for spot-style fills and cash events.

    Events can be exported as JSONL for durable storage.  A sell may only close
    inventory already recorded in the ledger; this fail-closed rule prevents an
    accidental short position from producing misleading P/L in the MVP.
    """

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._external_ids: set[str] = set()

    @property
    def events(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._events)

    def append(self, event: LedgerEvent) -> bool:
        """Append once. Returns False for an already-synced source event."""
        if event.external_id in self._external_ids:
            return False
        self._events.append(event)
        self._external_ids.add(event.external_id)
        return True

    def snapshot(self, marks: Mapping[str, float]) -> PnLSnapshot:
        lots: dict[str, list[tuple[float, float]]] = {}
        derivatives: dict[str, tuple[float, float]] = {}
        realized_gross = 0.0
        trade_fees = 0.0
        carry_pnl = 0.0
        adjustment_pnl = 0.0
        reporting_cash_balance = 0.0

        for event in sorted(self._events, key=lambda item: (item.occurred_at, item.event_id)):
            if event.event_type is EventType.TRADE_FILL:
                trade_fees += event.fee
                inventory = lots.setdefault(event.instrument or "", [])
                if event.side == "buy":
                    reporting_cash_balance -= event.quantity * event.price + event.fee
                    inventory.append((event.quantity, event.price))
                    continue
                reporting_cash_balance += event.quantity * event.price - event.fee
                remaining = event.quantity
                while remaining > 1e-12:
                    if not inventory:
                        raise ValueError(f"sell exceeds recorded inventory for {event.instrument}")
                    lot_quantity, lot_price = inventory[0]
                    closed = min(remaining, lot_quantity)
                    realized_gross += closed * (event.price - lot_price)
                    remaining -= closed
                    if closed == lot_quantity:
                        inventory.pop(0)
                    else:
                        inventory[0] = (lot_quantity - closed, lot_price)
            elif event.event_type is EventType.DERIVATIVE_FILL:
                trade_fees += event.fee
                signed = event.quantity if event.side == "buy" else -event.quantity
                quantity, average = derivatives.get(event.instrument or "", (0.0, 0.0))
                if quantity == 0 or quantity * signed > 0:
                    total = abs(quantity) + abs(signed)
                    average = ((abs(quantity) * average) + (abs(signed) * event.price)) / total
                    derivatives[event.instrument or ""] = (quantity + signed, average)
                else:
                    closed = min(abs(quantity), abs(signed))
                    realized_gross += closed * (event.price - average) * (1 if quantity > 0 else -1)
                    remaining = quantity + signed
                    if remaining == 0:
                        next_average = 0.0
                    elif remaining * quantity > 0:
                        next_average = average
                    else:
                        next_average = event.price
                    derivatives[event.instrument or ""] = (remaining, next_average)
                reporting_cash_balance -= event.fee
            elif event.event_type in {EventType.FUNDING, EventType.INTEREST, EventType.REBATE}:
                carry_pnl += event.cash_amount
                reporting_cash_balance += event.cash_amount
            elif event.event_type is EventType.ADJUSTMENT:
                adjustment_pnl += event.cash_amount
                reporting_cash_balance += event.cash_amount
            elif event.event_type is EventType.TRANSFER:
                reporting_cash_balance += event.cash_amount

        positions: list[Position] = []
        unrealized_gross = 0.0
        for instrument, inventory in lots.items():
            quantity = sum(item[0] for item in inventory)
            if quantity <= 1e-12:
                continue
            average_cost = sum(qty * price for qty, price in inventory) / quantity
            mark = marks.get(instrument)
            unrealized = 0.0 if mark is None else sum(qty * (mark - price) for qty, price in inventory)
            unrealized_gross += unrealized
            positions.append(Position(instrument, quantity, average_cost, mark, unrealized, "spot"))
        for instrument, (quantity, average_cost) in derivatives.items():
            if abs(quantity) <= 1e-12:
                continue
            mark = marks.get(instrument)
            unrealized = 0.0 if mark is None else quantity * (mark - average_cost)
            unrealized_gross += unrealized
            positions.append(Position(instrument, quantity, average_cost, mark, unrealized, "derivative"))

        net = realized_gross + unrealized_gross - trade_fees + carry_pnl + adjustment_pnl
        return PnLSnapshot(realized_gross, unrealized_gross, trade_fees, carry_pnl,
                           adjustment_pnl, net, reporting_cash_balance,
                           tuple(sorted(positions, key=lambda p: p.instrument)))

    def export_jsonl(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8") as handle:
            for event in self._events:
                data = asdict(event)
                data["occurred_at"] = event.occurred_at.isoformat()
                data["event_type"] = event.event_type.value
                handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass(frozen=True)
class PlatformBalance:
    asset: str
    total: float
    available: float


@dataclass(frozen=True)
class PlatformPosition:
    instrument: str
    quantity: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float


@dataclass(frozen=True)
class ConnectorSync:
    platform: str
    account_id: str
    synced_at: datetime
    cursor: str | None
    balances: Sequence[PlatformBalance]
    events: Sequence[LedgerEvent]
    positions: Sequence[PlatformPosition] = ()


class ReadOnlyPlatformConnector(Protocol):
    """Boundary every exchange/broker adapter must implement in Phase 1.

    The connector may fetch data only.  It has no order-placement method by
    design, so the MVP cannot send a live order accidentally.
    """

    def sync(self, cursor: str | None = None) -> ConnectorSync:
        ...
