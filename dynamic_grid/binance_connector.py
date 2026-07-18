"""Read-only Binance Spot adapter.

No POST/DELETE request exists in this module.  It syncs account balances,
fill history, and Spot capital deposits/withdrawals into canonical ledger
events for a reconciled P/L record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
from typing import Callable, Mapping, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .fund_ops import ConnectorSync, EventType, LedgerEvent, PlatformBalance


class BinanceTransport(Protocol):
    def get(self, path: str, params: Mapping[str, str], api_key: str) -> object:
        ...


class UrllibBinanceTransport:
    def __init__(self, base_url: str = "https://api.binance.com"):
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, params: Mapping[str, str], api_key: str) -> object:
        query = urlencode(params)
        request = Request(f"{self.base_url}{path}?{query}",
                          headers={"X-MBX-APIKEY": api_key}, method="GET")
        with urlopen(request, timeout=15) as response:  # nosec: URL is fixed by constructor
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True, repr=False)
class BinanceReadOnlyCredentials:
    api_key: str
    api_secret: str

    @classmethod
    def from_environment(cls, prefix: str = "BINANCE") -> "BinanceReadOnlyCredentials":
        import os
        key = os.getenv(f"{prefix}_API_KEY")
        secret = os.getenv(f"{prefix}_API_SECRET")
        if not key or not secret:
            raise RuntimeError(f"set {prefix}_API_KEY and {prefix}_API_SECRET outside the repository")
        return cls(key, secret)


class ApprovedMarksFeeConverter:
    """Convert non-reporting commission assets using operator-approved marks.

    Marks use instrument keys such as ``BNB/USDT``.  Missing marks fail closed
    so net P/L cannot silently understate fees.  Prices are never fetched from
    the exchange — they must come from the same valuation policy as closing marks.
    """

    def __init__(self, marks: Mapping[str, float], reporting_asset: str = "USDT"):
        self.marks = dict(marks)
        self.reporting_asset = reporting_asset

    def __call__(self, commission_asset: str, commission: float,
                 occurred_at: datetime) -> float:
        del occurred_at  # marks are point-in-time operator inputs for this slice
        if commission_asset == self.reporting_asset:
            return float(commission)
        key = f"{commission_asset}/{self.reporting_asset}"
        if key not in self.marks:
            raise ValueError(
                f"unpriced commission asset {commission_asset}; "
                f"provide approved mark {key}=PRICE before syncing")
        price = float(self.marks[key])
        if price <= 0:
            raise ValueError(f"approved mark {key} must be positive")
        return float(commission) * price


class BinanceSpotReadOnlyConnector:
    """Maps Binance Spot account history to canonical ledger events.

    All commissions must be supplied in the reporting currency.  If the
    exchange charges another asset (for example BNB), the caller must pass a
    converter; otherwise syncing fails rather than understating net P/L.

    Spot deposits/withdrawals in the reporting asset become TRANSFER events
    (cash only, never performance P/L).  Non-reporting capital flows fail closed.
    """

    platform = "binance"
    # Binance: deposit status 1 = success; withdraw status 6 = completed
    _DEPOSIT_OK = {1}
    _WITHDRAW_OK = {6}

    def __init__(self, credentials: BinanceReadOnlyCredentials, *, account_id: str,
                 portfolio_id: str, symbols: tuple[str, ...],
                 reporting_asset: str = "USDT", strategy_id: str | None = None,
                 transport: BinanceTransport | None = None,
                 fee_converter: Callable[[str, float, datetime], float] | None = None,
                 capital_fx: Callable[[str, float, datetime], float] | None = None):
        self.credentials = credentials
        self.account_id = account_id
        self.portfolio_id = portfolio_id
        self.symbols = symbols
        self.reporting_asset = reporting_asset
        self.strategy_id = strategy_id
        self.transport = transport or UrllibBinanceTransport()
        self.fee_converter = fee_converter
        self.capital_fx = capital_fx

    def _signed(self, params: Mapping[str, str]) -> dict[str, str]:
        values = dict(params)
        values["timestamp"] = str(int(time.time() * 1000))
        values["recvWindow"] = "5000"
        signature = hmac.new(self.credentials.api_secret.encode(),
                             urlencode(values).encode(), hashlib.sha256).hexdigest()
        values["signature"] = signature
        return values

    def _get(self, path: str, params: Mapping[str, str]) -> object:
        return self.transport.get(path, self._signed(params), self.credentials.api_key)

    def _instrument(self, symbol: str) -> str:
        if not symbol.endswith(self.reporting_asset):
            raise ValueError(f"symbol {symbol} does not end with reporting asset {self.reporting_asset}")
        base = symbol[:-len(self.reporting_asset)]
        if not base:
            raise ValueError(f"cannot derive base asset from {symbol}")
        return f"{base}/{self.reporting_asset}"

    def _fee(self, commission_asset: str, commission: float,
             occurred_at: datetime) -> float:
        if commission_asset == self.reporting_asset:
            return commission
        if self.fee_converter is not None:
            return self.fee_converter(commission_asset, commission, occurred_at)
        raise ValueError("unpriced commission asset " + commission_asset +
                         "; configure fee_converter before syncing")

    def _capital_params(self, cursor: str | None) -> dict[str, str]:
        params: dict[str, str] = {}
        if cursor:
            params["startTime"] = cursor
        return params

    def _capital_amount(self, coin: str, amount: float,
                        occurred_at: datetime) -> tuple[float, dict[str, str]]:
        """Value a capital flow in the reporting asset.

        A reporting-asset flow passes through unchanged. A foreign-asset flow is
        converted with the operator-approved ``capital_fx`` policy and the
        original asset, amount and applied rate are recorded in metadata for
        audit. Without an approved policy a foreign flow fails closed so cash can
        never be silently mis-valued.
        """
        if coin == self.reporting_asset:
            return float(amount), {}
        if self.capital_fx is None:
            raise ValueError(
                f"non-reporting capital asset {coin}; "
                f"multi-currency capital flows are out of scope until FX policy exists")
        reporting = self.capital_fx(coin, float(amount), occurred_at)
        if reporting <= 0:
            raise ValueError(f"approved capital FX for {coin} must be positive")
        rate = reporting / float(amount) if amount else 0.0
        return float(reporting), {
            "original_asset": coin,
            "original_amount": repr(float(amount)),
            "fx_rate": repr(rate),
        }

    def _sync_deposits(self, cursor: str | None) -> list[LedgerEvent]:
        raw = self._get("/sapi/v1/capital/deposit/hisrec", self._capital_params(cursor))
        if not isinstance(raw, list):
            raise ValueError("Binance deposit response must be a list")
        events: list[LedgerEvent] = []
        for item in raw:
            coin = str(item.get("coin", ""))
            status = int(item.get("status", -1))
            if status not in self._DEPOSIT_OK:
                continue
            deposit_id = str(item["id"])
            occurred_at = datetime.fromtimestamp(
                int(item["insertTime"]) / 1000, tz=timezone.utc)
            amount, metadata = self._capital_amount(
                coin, float(item["amount"]), occurred_at)
            events.append(LedgerEvent.cash_event(
                event_id=f"binance:deposit:{deposit_id}",
                external_id=f"binance:deposit:{deposit_id}",
                event_type=EventType.TRANSFER,
                platform=self.platform, account_id=self.account_id,
                portfolio_id=self.portfolio_id, strategy_id=self.strategy_id,
                cash_amount=amount,
                source_ref=str(item.get("txId") or deposit_id),
                occurred_at=occurred_at, metadata=metadata))
        return events

    def _sync_withdrawals(self, cursor: str | None) -> list[LedgerEvent]:
        raw = self._get("/sapi/v1/capital/withdraw/history", self._capital_params(cursor))
        if not isinstance(raw, list):
            raise ValueError("Binance withdraw response must be a list")
        events: list[LedgerEvent] = []
        for item in raw:
            coin = str(item.get("coin", ""))
            status = int(item.get("status", -1))
            if status not in self._WITHDRAW_OK:
                continue
            withdraw_id = str(item["id"])
            amount = float(item["amount"])
            fee = float(item.get("transactionFee", 0.0) or 0.0)
            # applyTime is usually "YYYY-MM-DD HH:MM:SS"; fall back to timestamp ms
            apply_time = item.get("applyTime")
            if isinstance(apply_time, (int, float)) or (
                    isinstance(apply_time, str) and apply_time.isdigit()):
                occurred_at = datetime.fromtimestamp(
                    int(apply_time) / 1000, tz=timezone.utc)
            else:
                occurred_at = datetime.strptime(
                    str(apply_time), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            reporting_amount, metadata = self._capital_amount(
                coin, amount + fee, occurred_at)
            events.append(LedgerEvent.cash_event(
                event_id=f"binance:withdraw:{withdraw_id}",
                external_id=f"binance:withdraw:{withdraw_id}",
                event_type=EventType.TRANSFER,
                platform=self.platform, account_id=self.account_id,
                portfolio_id=self.portfolio_id, strategy_id=self.strategy_id,
                cash_amount=-reporting_amount,
                source_ref=str(item.get("txId") or withdraw_id),
                occurred_at=occurred_at, metadata=metadata))
        return events

    def _sync_dividends(self, cursor: str | None) -> list[LedgerEvent]:
        """Import Spot distribution income (airdrops, launchpool, referral rebates).

        Binance returns these as asset-dividend rows. A reporting-asset payout is
        recorded at face value; a foreign-asset payout is valued with the approved
        ``capital_fx`` policy and otherwise fails closed. All rows land in the
        carry-P/L bucket as REBATE income, never as a capital TRANSFER.
        """
        raw = self._get("/sapi/v1/asset/assetDividend", self._capital_params(cursor))
        if not isinstance(raw, dict):
            raise ValueError("Binance asset-dividend response must be an object")
        rows = raw.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError("Binance asset-dividend rows must be a list")
        events: list[LedgerEvent] = []
        for item in rows:
            coin = str(item.get("asset", ""))
            dividend_id = str(item["id"])
            occurred_at = datetime.fromtimestamp(
                int(item["divTime"]) / 1000, tz=timezone.utc)
            amount, metadata = self._capital_amount(
                coin, float(item["amount"]), occurred_at)
            info = item.get("enInfo")
            if info:
                metadata = {**metadata, "info": str(info)}
            events.append(LedgerEvent.cash_event(
                event_id=f"binance:dividend:{dividend_id}",
                external_id=f"binance:dividend:{dividend_id}",
                event_type=EventType.REBATE,
                platform=self.platform, account_id=self.account_id,
                portfolio_id=self.portfolio_id, strategy_id=self.strategy_id,
                cash_amount=amount,
                source_ref=str(item.get("tranId") or dividend_id),
                occurred_at=occurred_at, metadata=metadata))
        return events

    def sync(self, cursor: str | None = None) -> ConnectorSync:
        account = self._get("/api/v3/account", {})
        if not isinstance(account, dict):
            raise ValueError("Binance account response must be an object")
        balances = tuple(PlatformBalance(
            asset=str(item["asset"]), total=float(item["free"]) + float(item["locked"]),
            available=float(item["free"]))
            for item in account.get("balances", []) if float(item["free"]) or float(item["locked"]))

        events: list[LedgerEvent] = []
        newest = cursor
        for symbol in self.symbols:
            params = {"symbol": symbol}
            if cursor:
                params["startTime"] = cursor
            trades = self._get("/api/v3/myTrades", params)
            if not isinstance(trades, list):
                raise ValueError("Binance trade response must be a list")
            for trade in trades:
                occurred_at = datetime.fromtimestamp(int(trade["time"]) / 1000, tz=timezone.utc)
                fee = self._fee(str(trade["commissionAsset"]), float(trade["commission"]),
                                occurred_at)
                trade_id = str(trade["id"])
                events.append(LedgerEvent.trade_fill(
                    event_id=f"binance:{symbol}:{trade_id}",
                    external_id=f"binance:{symbol}:{trade_id}", platform=self.platform,
                    account_id=self.account_id, portfolio_id=self.portfolio_id,
                    strategy_id=self.strategy_id, instrument=self._instrument(symbol),
                    side="buy" if trade["isBuyer"] else "sell",
                    quantity=float(trade["qty"]), price=float(trade["price"]), fee=fee,
                    source_ref=f"order:{trade['orderId']}", occurred_at=occurred_at))
                time_ms = str(trade["time"])
                newest = time_ms if newest is None else str(max(int(newest), int(time_ms)))

        events.extend(self._sync_deposits(cursor))
        events.extend(self._sync_withdrawals(cursor))
        events.extend(self._sync_dividends(cursor))
        return ConnectorSync(self.platform, self.account_id, datetime.now(timezone.utc),
                             newest, balances, tuple(events))
