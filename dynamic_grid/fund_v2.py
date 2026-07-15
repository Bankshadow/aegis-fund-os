"""MVP v2 operations: unified close, NAV/TWR, approvals, valuation and paper gate."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Iterable, Mapping
from .fund_controls import AccessController, Operation, Role
from .fund_reporting import DailyCloseReport
from .fund_ops import PlatformBalance

@dataclass(frozen=True)
class ValuationPolicy:
    base_currency: str; as_of: datetime; marks: Mapping[str, float]
    def price(self, instrument: str) -> float:
        value=self.marks.get(instrument)
        if value is None or value <= 0: raise ValueError(f"missing approved mark for {instrument}")
        return float(value)


@dataclass(frozen=True)
class ApprovedFxValuation:
    """Fail-closed conversion of account assets into one reporting currency."""

    reporting_currency: str
    as_of: datetime
    rates: Mapping[str, float]

    def rate(self, asset: str) -> float:
        if asset == self.reporting_currency:
            return 1.0
        value = self.rates.get(f"{asset}/{self.reporting_currency}")
        if value is None or float(value) <= 0:
            raise ValueError(
                f"missing approved FX rate for {asset}/{self.reporting_currency}")
        return float(value)

    def convert(self, asset: str, amount: float) -> float:
        return float(amount) * self.rate(asset)

    def value_balances(self, balances: Iterable[PlatformBalance]) -> float:
        return sum(self.convert(balance.asset, balance.total) for balance in balances)

@dataclass(frozen=True)
class PortfolioClose:
    portfolio_id: str; report_date: str; net_pnl: float; nav: float; status: str; exceptions: int; sources: tuple[str,...]

def aggregate_closes(portfolio_id: str, reports: Iterable[DailyCloseReport], opening_nav: float) -> PortfolioClose:
    rows=tuple(reports)
    if not rows: raise ValueError("at least one account close is required")
    net=sum(r.net_pnl for r in rows); exceptions=sum(len(r.reconciliation_exceptions) for r in rows)
    return PortfolioClose(portfolio_id,rows[0].report_date,net,opening_nav+net,"clean" if exceptions==0 else "provisional",exceptions,tuple(f"{r.platform}:{r.account_id}" for r in rows))

def time_weighted_return(periods: Iterable[tuple[float,float,float]]) -> float:
    growth=1.0
    for opening,closing,flow in periods:
        if opening<=0: raise ValueError("opening NAV must be positive")
        growth*=(closing-flow)/opening
    return growth-1.0

class CloseRegistry:
    def __init__(self,path:str|Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def _data(self): return json.loads(self.path.read_text()) if self.path.exists() else {"closes":{}}
    def _save(self,data): self.path.write_text(json.dumps(data,indent=2),encoding="utf-8")
    def record(self,close:PortfolioClose):
        data=self._data(); key=f"{close.portfolio_id}:{close.report_date}"
        if key in data["closes"]: raise ValueError("close already recorded")
        data["closes"][key]={**close.__dict__,"locked":False,"approved_by":None}; self._save(data)
    def approve_and_lock(self,portfolio_id:str,report_date:str,actor:str):
        data=self._data(); close=data["closes"].get(f"{portfolio_id}:{report_date}")
        if close is None: raise ValueError("close not found")
        if close["status"]!="clean": raise ValueError("cannot lock provisional close")
        close["locked"]=True; close["approved_by"]=actor; self._save(data)

@dataclass(frozen=True)
class PaperOrder:
    instrument:str; side:str; quantity:float; limit_price:float; submitted_at:datetime

class PaperExecutionGate:
    def __init__(self,allowed_instruments:set[str],max_notional:float): self.allowed_instruments=allowed_instruments; self.max_notional=max_notional; self.orders:list[PaperOrder]=[]
    def submit(self,instrument:str,side:str,quantity:float,limit_price:float)->PaperOrder:
        if instrument not in self.allowed_instruments or side not in {"buy","sell"}: raise PermissionError("paper order rejected")
        if quantity<=0 or limit_price<=0 or quantity*limit_price>self.max_notional: raise ValueError("paper risk limit exceeded")
        order=PaperOrder(instrument,side,quantity,limit_price,datetime.now(timezone.utc)); self.orders.append(order); return order

class InternalReportService:
    def __init__(self,controls:AccessController): self.controls=controls
    def read(self,actor:str,role:Role,path:str|Path)->dict:
        self.controls.authorize(actor,role,Operation.VIEW_REPORT)
        return json.loads(Path(path).read_text(encoding="utf-8"))
