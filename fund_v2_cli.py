"""Create and persist a unified portfolio close from account daily-close JSON files."""
import argparse, json
from dataclasses import fields
from dynamic_grid.fund_reporting import DailyCloseReport
from dynamic_grid.fund_v2 import aggregate_closes
from dynamic_grid.fund_v2_store import FundV2Store

def main():
    p=argparse.ArgumentParser(); p.add_argument("--portfolio",required=True); p.add_argument("--opening-nav",type=float,required=True); p.add_argument("reports",nargs="+"); p.add_argument("--db",default="results/fund_v2.sqlite")
    a=p.parse_args(); names={f.name for f in fields(DailyCloseReport)}
    reports=[DailyCloseReport(**{k:v for k,v in json.load(open(path,encoding="utf-8")).items() if k in names}) for path in a.reports]
    close=aggregate_closes(a.portfolio,reports,a.opening_nav); store=FundV2Store(a.db); store.record_close(close)
    print(json.dumps(close.__dict__,default=list))
if __name__=="__main__": main()
