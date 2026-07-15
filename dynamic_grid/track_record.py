"""Track-record metrics and export for locked portfolio closes."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable

def metrics(closes: Iterable[dict]) -> dict:
    rows=list(closes)
    if not rows: return {"twr":0.0,"max_drawdown":0.0,"monthly_pnl":{}}
    nav=[float(r["nav"]) for r in rows]
    peak=nav[0]; drawdown=0.0
    for value in nav:
        peak=max(peak,value); drawdown=max(drawdown,(peak-value)/peak if peak else 0)
    twr=nav[-1]/nav[0]-1 if len(nav)>1 and nav[0] else 0.0
    monthly={}
    for row in rows: monthly[row["report_date"][:7]]=monthly.get(row["report_date"][:7],0)+float(row["net_pnl"])
    return {"twr":twr,"max_drawdown":drawdown,"monthly_pnl":monthly}

def export_csv(closes: Iterable[dict], path: str|Path) -> None:
    rows=list(closes)
    with Path(path).open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=["portfolio_id","report_date","nav","net_pnl","status","locked","approved_by"])
        writer.writeheader(); writer.writerows(rows)
