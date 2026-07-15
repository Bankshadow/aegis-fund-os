"""Persisted paper-only orders with a global kill switch."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class PaperRiskPolicy:
    allowed_instruments: frozenset[str]; max_notional: float; enabled: bool=True

class PaperBroker:
    def __init__(self, policy: PaperRiskPolicy): self.policy=policy; self.orders=[]
    def kill_switch(self): self.policy=PaperRiskPolicy(self.policy.allowed_instruments,self.policy.max_notional,False)
    def submit(self,instrument,side,quantity,price):
        if not self.policy.enabled: raise PermissionError("paper trading disabled by kill switch")
        if instrument not in self.policy.allowed_instruments or side not in {"buy","sell"}: raise PermissionError("instrument or side rejected")
        if quantity<=0 or price<=0 or quantity*price>self.policy.max_notional: raise ValueError("paper risk limit exceeded")
        order={"instrument":instrument,"side":side,"quantity":quantity,"price":price,"submitted_at":datetime.now(timezone.utc).isoformat(),"mode":"paper"}; self.orders.append(order); return order
