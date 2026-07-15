"""Read-only Binance USDⓈ-M Futures funding connector.

This intentionally imports only funding income and account balances. Futures
fills, positions, collateral transfers, and derivatives valuation remain
separate follow-up work; it cannot certify complete derivatives P/L alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import time
from typing import Mapping, Protocol

from .binance_connector import BinanceReadOnlyCredentials, UrllibBinanceTransport
from .fund_ops import (ConnectorSync, EventType, LedgerEvent, PlatformBalance,
                       PlatformPosition)


class FuturesTransport(Protocol):
    def get(self, path: str, params: Mapping[str, str], api_key: str) -> object:
        ...


class BinanceUsdmFundingReadOnlyConnector:
    """Maps USDⓈ-M ``FUNDING_FEE`` income to canonical funding events.

    This class exposes no method that can submit, amend, or cancel an order.
    Funding is retained as a separate platform/account scope so Spot and Futures
    balances cannot be reconciled against one another by accident.
    """

    platform = "binance_usdm"

    def __init__(self, credentials: BinanceReadOnlyCredentials, *, account_id: str,
                 portfolio_id: str, reporting_asset: str = "USDT",
                 transport: FuturesTransport | None = None,
                 strategy_id: str | None = None, symbols: tuple[str, ...] = ()):
        self.credentials = credentials
        self.account_id = account_id
        self.portfolio_id = portfolio_id
        self.reporting_asset = reporting_asset
        self.strategy_id = strategy_id
        self.symbols = symbols
        self.transport = transport or UrllibBinanceTransport("https://fapi.binance.com")

    def _signed(self, params: Mapping[str, str]) -> dict[str, str]:
        from urllib.parse import urlencode
        values = dict(params)
        values["timestamp"] = str(int(time.time() * 1000))
        values["recvWindow"] = "5000"
        values["signature"] = hmac.new(
            self.credentials.api_secret.encode(), urlencode(values).encode(),
            hashlib.sha256).hexdigest()
        return values

    def _get(self, path: str, params: Mapping[str, str]) -> object:
        return self.transport.get(path, self._signed(params), self.credentials.api_key)

    def sync(self, cursor: str | None = None) -> ConnectorSync:
        raw_balances = self._get("/fapi/v2/balance", {})
        if not isinstance(raw_balances, list):
            raise ValueError("Binance USDⓈ-M balance response must be a list")
        balances = tuple(
            PlatformBalance(str(item["asset"]), float(item["balance"]),
                            float(item["availableBalance"]))
            for item in raw_balances
            if float(item["balance"]) or float(item["availableBalance"]))
        raw_positions = self._get("/fapi/v3/positionRisk", {})
        if not isinstance(raw_positions, list):
            raise ValueError("Binance USDⓈ-M position-risk response must be a list")
        positions = tuple(
            PlatformPosition(str(item["symbol"]), float(item["positionAmt"]),
                             float(item["entryPrice"]), float(item["markPrice"]),
                             float(item["unRealizedProfit"]))
            for item in raw_positions if abs(float(item["positionAmt"])) > 1e-12)

        params = {"incomeType": "FUNDING_FEE", "limit": "1000"}
        if cursor:
            params["startTime"] = cursor
        raw_income = self._get("/fapi/v1/income", params)
        if not isinstance(raw_income, list):
            raise ValueError("Binance USDⓈ-M income response must be a list")

        events: list[LedgerEvent] = []
        newest = cursor
        for item in raw_income:
            if item.get("incomeType") != "FUNDING_FEE":
                continue
            asset = str(item["asset"])
            if asset != self.reporting_asset:
                raise ValueError(
                    f"non-reporting funding asset {asset}; add FX policy before importing")
            occurred_at = datetime.fromtimestamp(int(item["time"]) / 1000, tz=timezone.utc)
            transaction_id = str(item["tranId"])
            events.append(LedgerEvent.cash_event(
                event_id=f"binance-usdm:funding:{transaction_id}",
                external_id=f"binance-usdm:funding:{transaction_id}",
                event_type=EventType.FUNDING, platform=self.platform,
                account_id=self.account_id, portfolio_id=self.portfolio_id,
                strategy_id=self.strategy_id, cash_amount=float(item["income"]),
                source_ref=f"{item.get('symbol', '')}:{transaction_id}",
                occurred_at=occurred_at))
            time_ms = str(item["time"])
            newest = time_ms if newest is None else str(max(int(newest), int(time_ms)))
        transfer_params = {"incomeType": "TRANSFER", "limit": "1000"}
        if cursor:
            transfer_params["startTime"] = cursor
        raw_transfers = self._get("/fapi/v1/income", transfer_params)
        if not isinstance(raw_transfers, list):
            raise ValueError("Binance USDⓈ-M transfer response must be a list")
        for item in raw_transfers:
            if str(item["asset"]) != self.reporting_asset:
                raise ValueError("non-reporting collateral asset; add FX policy before importing")
            occurred_at = datetime.fromtimestamp(int(item["time"]) / 1000, tz=timezone.utc)
            transaction_id = str(item["tranId"])
            events.append(LedgerEvent.cash_event(
                event_id=f"binance-usdm:transfer:{transaction_id}",
                external_id=f"binance-usdm:transfer:{transaction_id}",
                event_type=EventType.TRANSFER, platform=self.platform,
                account_id=self.account_id, portfolio_id=self.portfolio_id,
                strategy_id=self.strategy_id, cash_amount=float(item["income"]),
                source_ref=f"collateral:{transaction_id}", occurred_at=occurred_at))
            time_ms = str(item["time"])
            newest = time_ms if newest is None else str(max(int(newest), int(time_ms)))
        for symbol in self.symbols:
            params = {"symbol": symbol, "limit": "1000"}
            if cursor:
                params["startTime"] = cursor
            trades = self._get("/fapi/v1/userTrades", params)
            if not isinstance(trades, list):
                raise ValueError("Binance USDⓈ-M trade response must be a list")
            for trade in trades:
                if str(trade["commissionAsset"]) != self.reporting_asset:
                    raise ValueError("non-reporting futures commission asset; add FX policy before importing")
                occurred_at = datetime.fromtimestamp(int(trade["time"]) / 1000, tz=timezone.utc)
                trade_id = str(trade["id"])
                events.append(LedgerEvent.derivative_fill(
                    event_id=f"binance-usdm:{symbol}:{trade_id}",
                    external_id=f"binance-usdm:{symbol}:{trade_id}", platform=self.platform,
                    account_id=self.account_id, portfolio_id=self.portfolio_id,
                    strategy_id=self.strategy_id, instrument=symbol,
                    side="buy" if trade["buyer"] else "sell", quantity=float(trade["qty"]),
                    price=float(trade["price"]), fee=float(trade["commission"]),
                    source_ref=f"order:{trade['orderId']}", occurred_at=occurred_at))
                time_ms = str(trade["time"])
                newest = time_ms if newest is None else str(max(int(newest), int(time_ms)))
        return ConnectorSync(self.platform, self.account_id, datetime.now(timezone.utc),
                             newest, balances, tuple(events), positions)
