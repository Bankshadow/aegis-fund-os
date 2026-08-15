"""E30 — which directional BTC logic makes the most from 10,000 USDT?

Criteria were declared in `docs/BTC_E30_CRITERIA.md` BEFORE this ran and are
not edited afterwards. Run:

    python btc_directional_e30.py

Writes `docs/btc-directional-e30.json` (raw per-window output) and prints the
decision tables. Read-only backtest: no exchange call, no order path.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np

from dynamic_grid import directional as d

DATA = os.path.join(os.path.dirname(__file__), "data")
WARMUP = 200
OOS = 252          # ~1 trading year of daily bars
IS = 504           # ~2 years
INITIAL = 10_000.0
CANDIDATES = list(d.CANDIDATES)
RISKY = [c for c in CANDIDATES if c != "B0_buy_hold"]


def load(path):
    with open(os.path.join(DATA, path)) as f:
        raw = json.load(f)
    bars = np.array([[float(k[1]), float(k[2]), float(k[3]), float(k[4])]
                     for k in raw])
    dates = [datetime.fromtimestamp(k[0] / 1000, timezone.utc).date().isoformat()
             for k in raw]
    return bars, dates


def stats(res):
    return {
        "return": res.total_return,
        "maxDD": res.max_drawdown,
        "robust": res.robust,
        "final_equity": res.final_equity,
        "n_trades": res.n_trades,
        "win_rate": res.win_rate,
        "avg_win": res.avg_win,
        "avg_loss": res.avg_loss,
        "rr": res.rr,
        "expectancy": res.expectancy,
        "profit_factor": res.profit_factor,
    }


def pooled(trades):
    """Trade-level statistics over a pool of trades from many windows."""
    if not trades:
        return {"n_trades": 0}
    nets = [t.net_return for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [-x for x in nets if x <= 0]
    aw = float(np.mean(wins)) if wins else None
    al = float(np.mean(losses)) if losses else None
    return {
        "n_trades": len(nets),
        "win_rate": len(wins) / len(nets),
        "avg_win": aw,
        "avg_loss": al,
        "rr": (aw / al) if (aw and al) else None,
        "expectancy": float(np.mean(nets)),
        "profit_factor": (sum(wins) / sum(losses)) if losses else float("inf"),
    }


def pct(x, nd=2):
    return "     -" if x is None else f"{x * 100:+{nd + 5}.{nd}f}%"


def num(x, nd=2):
    return "    -" if x is None else f"{x:{nd + 4}.{nd}f}"


# --------------------------------------------------------------------------
# Layer A — fixed parameters, non-overlapping OOS windows
# --------------------------------------------------------------------------

def layer_a(bars, dates):
    n = len(bars)
    n_windows = (n - WARMUP) // OOS
    offset = n - n_windows * OOS          # keep the most recent bars, not the oldest
    windows, rows = [], {c: [] for c in CANDIDATES}
    trades = {c: [] for c in CANDIDATES}

    for w in range(n_windows):
        start = offset + w * OOS
        end = start + OOS
        windows.append({"window": w + 1, "start": dates[start],
                        "end": dates[end - 1]})
        for name in CANDIDATES:
            res = d.run(bars[:end], name, start=start, initial_equity=INITIAL)
            rows[name].append(stats(res))
            trades[name].extend(res.trades)
    return windows, rows, trades


# --------------------------------------------------------------------------
# Layer B — pick the best in-sample return, measure it out-of-sample
# --------------------------------------------------------------------------

def layer_b(bars, dates):
    folds = []
    i = WARMUP
    while i + IS + OOS <= len(bars):
        is_start, is_end = i, i + IS
        oos_end = is_end + OOS
        is_ret = {c: d.run(bars[:is_end], c, start=is_start,
                           initial_equity=INITIAL).total_return
                  for c in RISKY}
        picked = max(is_ret, key=is_ret.get)
        oos_ret = {c: d.run(bars[:oos_end], c, start=is_end,
                            initial_equity=INITIAL).total_return
                   for c in RISKY}
        best_oos = max(oos_ret, key=oos_ret.get)
        folds.append({
            "fold": len(folds) + 1,
            "is_start": dates[is_start], "is_end": dates[is_end - 1],
            "oos_start": dates[is_end], "oos_end": dates[oos_end - 1],
            "picked": picked,
            "picked_is_return": is_ret[picked],
            "picked_oos_return": oos_ret[picked],
            "random_oos_return": float(np.mean(list(oos_ret.values()))),
            "best_possible_oos": best_oos,
            "best_possible_oos_return": oos_ret[best_oos],
            "picked_was_best": picked == best_oos,
        })
        i += OOS
    return folds


# --------------------------------------------------------------------------
# Descriptive views. NOT evidence: no criterion is attached to either, and
# neither may be used to choose a candidate. They exist because "what does
# 10,000 become?" is a single-path question and Layer A restarts every window.
# --------------------------------------------------------------------------

def layer_zero(bars, dates):
    """One continuous run over the whole history — a single path, in-sample."""
    out = {}
    for name in CANDIDATES:
        res = d.run(bars, name, start=WARMUP, initial_equity=INITIAL)
        out[name] = stats(res)
    return out


def held_out(names):
    """Same fixed parameters on ETH and SOL. Descriptive unless C1-C5 passed."""
    out = {}
    for sym, path in (("ETHUSDT", "ETHUSDT_1d.json"),
                      ("SOLUSDT", "SOLUSDT_1d.json")):
        bars, dates = load(path)
        out[sym] = {"bars": len(bars), "first": dates[0], "last": dates[-1],
                    "results": {}}
        for name in names:
            res = d.run(bars, name, start=WARMUP, initial_equity=INITIAL)
            out[sym]["results"][name] = stats(res)
    return out


def main():
    bars, dates = load("btc_daily_full.json")
    print(f"BTCUSDT 1d - {len(bars)} bars, {dates[0]} -> {dates[-1]}\n")

    windows, rows, trades = layer_a(bars, dates)
    b0 = rows["B0_buy_hold"]

    print("=" * 100)
    print("LAYER A — fixed parameters, non-overlapping 252-bar OOS windows")
    print("=" * 100)
    header = "window    period                 " + "".join(
        f"{c.split('_')[0]:>11}" for c in CANDIDATES)
    print(header)
    for w, meta in enumerate(windows):
        line = f"  {meta['window']:>2}    {meta['start']} {meta['end']}  "
        for c in CANDIDATES:
            line += f"{rows[c][w]['return'] * 100:>10.1f}%"
        print(line)
    print("-" * 100)

    summary = {}
    for c in CANDIDATES:
        rets = [r["return"] for r in rows[c]]
        dds = [r["maxDD"] for r in rows[c]]
        robs = [r["robust"] for r in rows[c]]
        beat = sum(1 for i, r in enumerate(rets) if r > b0[i]["return"])
        engaged = sum(1 for r in rows[c] if r["n_trades"] > 0)
        compounded = INITIAL
        for r in rets:
            compounded *= (1 + r)
        summary[c] = {
            "mean_return": float(np.mean(rets)),
            "median_return": float(np.median(rets)),
            "mean_maxDD": float(np.mean(dds)),
            "mean_robust": float(np.mean(robs)),
            "windows_beating_b0": beat,
            "windows": len(rets),
            "engaged_windows": engaged,
            "compounded_equity_10k": compounded,
            "pooled_trades": pooled(trades[c]),
        }

    print(f"{'candidate':<22}{'meanRet':>10}{'medRet':>10}{'meanDD':>10}"
          f"{'robust':>10}{'>B0':>6}{'eng':>6}{'trades':>8}{'WR':>8}"
          f"{'RR':>7}{'expect':>9}{'PF':>7}{'10k ->':>12}")
    for c in CANDIDATES:
        s = summary[c]
        p = s["pooled_trades"]
        print(f"{c:<22}{pct(s['mean_return'], 1)}{pct(s['median_return'], 1)}"
              f"{pct(s['mean_maxDD'], 1)}{pct(s['mean_robust'], 1)}"
              f"{s['windows_beating_b0']:>4}/{s['windows']:<1}"
              f"{s['engaged_windows']:>4}/{s['windows']:<1}"
              f"{p.get('n_trades', 0):>8}"
              f"{pct(p.get('win_rate'), 1)}{num(p.get('rr'))}"
              f"{pct(p.get('expectancy'), 2)}{num(p.get('profit_factor'))}"
              f"{s['compounded_equity_10k']:>12,.0f}")

    folds = layer_b(bars, dates)
    picked_wins = sum(1 for f in folds
                      if f["picked_oos_return"] > f["random_oos_return"])
    hit = sum(1 for f in folds if f["picked_was_best"])
    print("\n" + "=" * 100)
    print("LAYER B — does picking the best in-sample return actually work?")
    print("=" * 100)
    print(f"{'fold':<6}{'OOS period':<26}{'picked (best IS)':<24}"
          f"{'IS ret':>9}{'OOS ret':>10}{'avg cand':>10}{'best was':>22}")
    for f in folds:
        print(f"{f['fold']:<6}{f['oos_start']} {f['oos_end']:<12}"
              f"{f['picked']:<24}{pct(f['picked_is_return'], 1)}"
              f"{pct(f['picked_oos_return'], 1)}{pct(f['random_oos_return'], 1)}"
              f"{f['best_possible_oos']:>22}")
    print(f"\n  picked beat the average candidate OOS: "
          f"{picked_wins}/{len(folds)} = {picked_wins / len(folds) * 100:.1f}%")
    print(f"  picked WAS the best candidate OOS:     "
          f"{hit}/{len(folds)} = {hit / len(folds) * 100:.1f}%"
          f"   (chance = {100 / len(RISKY):.1f}%)")

    l0 = layer_zero(bars, dates)
    print("\n" + "=" * 100)
    print("DESCRIPTIVE — one continuous run, 10,000 USDT, "
          f"{dates[WARMUP]} -> {dates[-1]} (single path, NOT evidence)")
    print("=" * 100)
    print(f"{'candidate':<22}{'final equity':>16}{'return':>12}{'maxDD':>10}"
          f"{'robust':>10}{'trades':>8}{'WR':>8}{'RR':>7}{'expect':>9}")
    for c in sorted(CANDIDATES, key=lambda x: -l0[x]["final_equity"]):
        s = l0[c]
        print(f"{c:<22}{s['final_equity']:>16,.0f}{pct(s['return'], 1)}"
              f"{pct(s['maxDD'], 1)}{pct(s['robust'], 1)}{s['n_trades']:>8}"
              f"{pct(s['win_rate'], 1)}{num(s['rr'])}{pct(s['expectancy'], 2)}")

    ho = held_out(RISKY)
    print("\n" + "=" * 100)
    print("HELD-OUT — same fixed parameters on ETH and SOL")
    print("=" * 100)
    for sym, block in ho.items():
        print(f"\n{sym}  {block['first']} -> {block['last']}  "
              f"({block['bars']} bars)")
        print(f"{'candidate':<22}{'final equity':>16}{'return':>12}"
              f"{'trades':>8}{'WR':>8}{'RR':>7}{'expect':>9}")
        for c in RISKY:
            s = block["results"][c]
            print(f"{c:<22}{s['final_equity']:>16,.0f}{pct(s['return'], 1)}"
                  f"{s['n_trades']:>8}{pct(s['win_rate'], 1)}{num(s['rr'])}"
                  f"{pct(s['expectancy'], 2)}")

    out = {
        "experiment": "E30",
        "generated": datetime.now(timezone.utc).isoformat(),
        "data": {"symbol": "BTCUSDT", "interval": "1d", "bars": len(bars),
                 "first": dates[0], "last": dates[-1]},
        "config": {"initial_equity": INITIAL, "cost_per_side": d.COST_PER_SIDE,
                   "warmup": WARMUP, "oos": OOS, "is": IS},
        "layer_a": {"windows": windows, "per_candidate": rows,
                    "summary": summary},
        "layer_b": {"folds": folds,
                    "picked_beat_average": picked_wins,
                    "picked_was_best": hit,
                    "n_folds": len(folds)},
        "descriptive_continuous": l0,
        "descriptive_held_out": ho,
    }
    path = os.path.join(os.path.dirname(__file__), "docs",
                        "btc-directional-e30.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nraw output -> {path}")
    return summary, folds


if __name__ == "__main__":
    main()
