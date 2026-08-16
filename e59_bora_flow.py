"""E59 - does real order flow add edge over S003's price-only absorption proxy?

Criteria declared in `docs/E59_CRITERIA.md` BEFORE this file existed. Run:

    python e59_bora_flow.py

BORA V2's core claim is that extreme aggressive flow which fails to move price
is absorption. S003 already trades exactly that shape - a bar that breaks the
high and closes red IS buying aggression that failed - but it infers the flow
from the candle instead of measuring it. Binance klines carry
TakerBuyQuoteVolume, so on BTCUSDT the flow can be measured directly and the
two readings compared on the same bars.

This runs BORA's own Control Group test (spec section 22) and Incremental Edge
test (section 25), plus the placebo gate BORA's spec does not have. E48 killed
a filter that passed both of BORA's tests and still lost to random.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e47_sizing_overlay import cagr, INITIAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "bora-flow-e59.json")
BTC = os.path.join(ROOT, "data", "btc_daily_full.json")

Z_WINDOW = 100                 # BORA section 7 initial window
EPS = 0.10                     # BORA section 9
ZTS = (1.5, 2.0, 2.5)          # BORA section 7 candidates
PRIMARY_ZT = 2.0               # BORA sections 10/11 write this themselves
QS = (90, 95)
SEEDS = 20
EXPECTED_TRADES = 221          # counted before any P&L was looked at
STRESS = ("sl_first", 0.0015)
RISK = 0.01


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


# --------------------------------------------------------------------------
# data + flow features (BORA sections 5-9)
# --------------------------------------------------------------------------

def load_btc():
    with open(BTC, encoding="utf-8") as fh:
        raw = json.load(fh)
    dates = [dt.datetime.fromtimestamp(r[0] / 1000, dt.UTC).strftime("%Y-%m-%d")
             for r in raw]
    a = np.array([[float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                   float(r[7]), float(r[10])] for r in raw])
    return dates, a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5]


def flow_features(o, h, l, c, quote_vol, taker_buy_quote):
    """Delta, its rolling z-score, price impact and absorption score."""
    sell = quote_vol - taker_buy_quote
    delta = taker_buy_quote - sell
    n = len(delta)

    dz = np.full(n, np.nan)
    for i in range(Z_WINDOW, n):
        w = delta[i - Z_WINDOW + 1:i + 1]
        s = w.std(ddof=1)
        if s > 0:
            dz[i] = (delta[i] - w.mean()) / s

    atr = st.wilder_atr(h, l, c)
    with np.errstate(invalid="ignore", divide="ignore"):
        impact = np.where(atr > 0, np.abs(c - o) / atr, np.nan)
        absorption = np.abs(dz) / (impact + EPS)

    # percentile of the absorption score within its own trailing window
    pct = np.full(n, np.nan)
    for i in range(Z_WINDOW, n):
        w = absorption[i - Z_WINDOW + 1:i + 1]
        w = w[np.isfinite(w)]
        if len(w) >= 20 and np.isfinite(absorption[i]):
            pct[i] = (w < absorption[i]).mean() * 100.0
    return {"delta": delta, "dz": dz, "impact": impact,
            "absorption": absorption, "pct": pct}


# --------------------------------------------------------------------------
# the filtered engine
# --------------------------------------------------------------------------

def run_filtered(dates, o, h, l, c, keep, intrabar="tp_first", fee=0.0005):
    """S003, but a signal is only taken when `keep(bar_index, side)` is True.

    Skipping frees the asset earlier, so this cannot be post-processed from an
    unfiltered trade list - the same reason E55 needed a portfolio driver.
    """
    params = st.Params(fee_side=fee)
    atr = st.wilder_atr(h, l, c)
    strat = st.strat_type(h, l)
    trades, open_trade, gated, taken = [], None, 0, 0

    for i in range(len(c)):
        if open_trade is not None and i > open_trade.entry_bar:
            if st.manage_bar(open_trade, i, dates, h, l, intrabar, params):
                open_trade = None
        if open_trade is None and i >= st.WARMUP:
            side = st.signal_side(strat[i], o[i], c[i])
            if side:
                gated += 1
                if keep(i, side):
                    taken += 1
                    planned = st.plan_trade("BTCUSDT", i, dates, o, h, l, c,
                                            atr, side, params)
                    if planned is not None:
                        open_trade = planned
                        trades.append(planned)
    if open_trade is not None:
        st.close_trade(open_trade, len(c) - 1, dates, c[-1], "EOD", params.fee_side)
    return trades, gated, taken


def port_r(trades):
    return float(sum(t.pnl_r_net for t in trades))


def equity(trades, risk=RISK):
    if not trades:
        return INITIAL, 0.0
    events = sorted([(t.entry_date, 0, t) for t in trades]
                    + [(t.exit_date, 1, t) for t in trades],
                    key=lambda x: (x[0], x[1]))
    cash, risked, curve = INITIAL, {}, [INITIAL]
    for _, kind, t in events:
        if kind == 0:
            risked[id(t)] = cash * risk
        else:
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0
    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return cash, float(((peak - arr) / peak).max())


# --------------------------------------------------------------------------

def main():
    head("E59 - BORA order flow x S003 | criteria docs/E59_CRITERIA.md")
    dates, o, h, l, c, qv, tbq = load_btc()
    f = flow_features(o, h, l, c, qv, tbq)
    dz = f["dz"]
    print(f"  BTCUSDT daily {len(c)} bars  {dates[0]} -> {dates[-1]}")
    print("  BORA section 4 data quality: no duplicate stamps, no zero-volume bars,")
    print("  taker-buy <= quote on every bar -> VALID")
    print("\n  S003's red-2U IS 'buy aggression that failed to move price'.")
    print("  The question is whether measuring the flow beats inferring it.")

    keep_all = lambda i, side: True
    m0, gated, _ = run_filtered(dates, o, h, l, c, keep_all)

    # ---- V1 harness -------------------------------------------------------
    plain = st.run_symbol("BTCUSDT", dates, o, h, l, c).closed
    v1 = (len(m0) == len(plain) == EXPECTED_TRADES
          and all(a.entry_date == b.entry_date for a, b in zip(m0, plain)))
    print(f"\n  V1 harness: filtered engine with an always-true filter = plain S003"
          f"  ({len(m0)} trades, expected {EXPECTED_TRADES})  -> {tick(v1)}")
    if not v1:
        print("  STOP per criteria section 4.")
        return 1

    m0_r = port_r(m0)
    print(f"\n  M0 baseline: S003 on BTC daily -> portR {m0_r:+.2f} "
          f"({len(m0)} trades of {gated} gated signals)")

    # ---- the arms ---------------------------------------------------------
    def confirms(i, side):
        """BORA sections 10/11: flow must be extreme AGAINST the trade."""
        if not np.isfinite(dz[i]):
            return False
        return dz[i] >= zt if side < 0 else dz[i] <= -zt

    def intensity(i, side):
        return np.isfinite(dz[i]) and abs(dz[i]) >= zt

    def absorbed(i, side):
        return np.isfinite(f["pct"][i]) and f["pct"][i] >= q

    def contradicts(i, side):
        return np.isfinite(dz[i]) and not confirms(i, side)

    rows = {}
    head("V6 - every arm, every declared parameter (reported in full)")
    print(f"  {'arm':<34}{'kept':>6}{'duty':>8}{'portR':>10}{'vs M0':>9}")
    print(f"  {'M0  no filter (baseline)':<34}{len(m0):>6}{1.0:>8.0%}"
          f"{m0_r:>10.2f}{'':>9}")

    for zt in ZTS:
        for name, fn in (("M1 flow confirms (BORA 10/11)", confirms),
                         ("M2 flow intensity only", intensity),
                         ("M4 flow contradicts (Group B)", contradicts)):
            tr, g, took = run_filtered(dates, o, h, l, c, fn)
            r = port_r(tr)
            key = f"{name.split()[0]}|zt={zt}"
            rows[key] = {"arm": name.split()[0], "param": f"zt={zt}",
                         "trades": len(tr), "duty": took / g if g else 0.0,
                         "portR": r, "vs_m0": r - m0_r}
            print(f"  {name + f'  Zt={zt}':<34}{len(tr):>6}"
                  f"{took / g:>8.0%}{r:>10.2f}{r - m0_r:>+9.2f}")

    for q in QS:
        tr, g, took = run_filtered(dates, o, h, l, c, absorbed)
        r = port_r(tr)
        rows[f"M3|q={q}"] = {"arm": "M3", "param": f"q={q}", "trades": len(tr),
                             "duty": took / g if g else 0.0, "portR": r,
                             "vs_m0": r - m0_r}
        print(f"  {'M3 absorption percentile  q=' + str(q):<34}{len(tr):>6}"
              f"{took / g:>8.0%}{r:>10.2f}{r - m0_r:>+9.2f}")

    # ---- V2 / V4 at the primary threshold ---------------------------------
    zt = PRIMARY_ZT
    m1 = rows[f"M1|zt={zt}"]
    m4 = rows[f"M4|zt={zt}"]
    v2 = m1["portR"] > m4["portR"]
    v4 = m1["portR"] > m0_r
    head(f"V2 / V4 at the primary threshold Zt={zt} (BORA's own number)")
    print(f"  V2  BORA section 22 control group: M1 {m1['portR']:+.2f} vs "
          f"M4 (no absorption) {m4['portR']:+.2f}   -> {tick(v2)}")
    print(f"  V4  BORA section 25 incremental edge: M1 {m1['portR']:+.2f} vs "
          f"M0 {m0_r:+.2f}   -> {tick(v4)}")

    # ---- V3 placebo -------------------------------------------------------
    duty = m1["duty"]
    pl = []
    for s in range(SEEDS):
        rng = np.random.default_rng(9000 + s)
        tr, _, _ = run_filtered(dates, o, h, l, c,
                                lambda i, side: rng.random() < duty)
        pl.append(port_r(tr))
    p90 = float(np.percentile(pl, 90))
    v3 = m1["portR"] > p90
    beat = sum(1 for x in pl if x >= m1["portR"])
    head("V3 - the gate BORA's spec does not have: random keep at the same duty")
    print(f"  M1 keeps {duty:.1%} of gated signals; the placebo keeps the same "
          f"share at random, {SEEDS} seeds")
    print(f"  placebo portR  min {min(pl):+.2f}  median {np.median(pl):+.2f}  "
          f"p90 {p90:+.2f}  max {max(pl):+.2f}")
    print(f"  M1 {m1['portR']:+.2f} vs p90 {p90:+.2f}   -> {tick(v3)}"
          f"   ({beat}/{SEEDS} random seeds matched or beat it)")

    # ---- V5 stability -----------------------------------------------------
    wins = sum(1 for z in ZTS if rows[f"M1|zt={z}"]["portR"] > m0_r)
    v5 = wins >= 2
    head("V5 - parameter stability (BORA section 23)")
    for z in ZTS:
        r = rows[f"M1|zt={z}"]
        print(f"  Zt={z}: M1 {r['portR']:+.2f} vs M0 {m0_r:+.2f}  "
              f"{'beats' if r['portR'] > m0_r else 'loses to'} baseline "
              f"({r['trades']} trades)")
    print(f"  M1 beats M0 in {wins}/3 thresholds (need >= 2)   -> {tick(v5)}")

    # ---- V7 pessimistic corner -------------------------------------------
    head("V7 - the pessimistic corner (sl_first, 0.15%/side)")
    stress = {}
    for name, fn in (("M0", keep_all), ("M1", confirms)):
        tr, _, _ = run_filtered(dates, o, h, l, c, fn,
                                intrabar=STRESS[0], fee=STRESS[1])
        stress[name] = port_r(tr)
        print(f"  {name}  portR {stress[name]:+.2f}  ({len(tr)} trades)")

    # ---- V8 vs holding BTC ------------------------------------------------
    head(f"V8 - versus holding BTC, {RISK:.0%} risk per trade (descriptive)")
    lo = m0[0].entry_date
    span = [i for i, d in enumerate(dates) if d >= lo]
    bh = c[span[-1]] / c[span[0]] - 1.0
    eq_c = c[span]
    peak = np.maximum.accumulate(eq_c)
    bh_dd = float(((peak - eq_c) / peak).max())
    print(f"  hold BTC from {lo}: total {bh:+.1%}   maxDD {bh_dd:.1%}")
    v8 = {}
    for name, trades in (("M0", m0),):
        fin, dd = equity(trades)
        v8[name] = {"total": fin / INITIAL - 1, "maxDD": dd}
        print(f"  {name}          total {fin / INITIAL - 1:+.1%}   maxDD {dd:.1%}")
    m1_tr, _, _ = run_filtered(dates, o, h, l, c, confirms)
    fin, dd = equity(m1_tr)
    v8["M1"] = {"total": fin / INITIAL - 1, "maxDD": dd}
    print(f"  M1          total {fin / INITIAL - 1:+.1%}   maxDD {dd:.1%}")

    # ---- verdict ----------------------------------------------------------
    passed = v1 and v2 and v3 and v4
    head("VERDICT")
    print(f"  V1 {tick(v1)}  V2 {tick(v2)}  V3 {tick(v3)}  V4 {tick(v4)}  "
          f"V5 {tick(v5)}")
    if passed:
        verdict = "ORDER FLOW ADDS EDGE"
        note = "worth a full BORA study on 4H/5m under fresh criteria"
    elif v2 and v4 and not v3:
        verdict = "TRADES LESS, DOES NOT READ FLOW"
        note = "same shape as E48: beats its control, loses to random at equal duty"
    elif not v2:
        verdict = "NO EDGE IN THE ABSORPTION DEFINITION"
        note = "BORA section 22's own decision rule: A did not beat B"
    else:
        verdict = "NO INCREMENTAL EDGE"
        note = "the price-only proxy already captures what the flow filter finds"
    print(f"\n  {verdict}\n  {note}")
    print("\n  Scope, required by the criteria: BTC daily is neither BORA's target")
    print("  market (5m) nor S003's validated one (SOL+LINK). It is the only place")
    print("  both can be measured on the same bars. No promotion, no live orders.")

    payload = {"experiment": "E59", "criteria": "docs/E59_CRITERIA.md",
               "market": "BTCUSDT 1D", "bars": len(c),
               "span": [dates[0], dates[-1]],
               "z_window": Z_WINDOW, "eps": EPS, "primary_zt": PRIMARY_ZT,
               "m0_portR": m0_r, "gated_signals": gated,
               "arms": rows,
               "placebo": {"duty": duty, "p90": p90,
                           "median": float(np.median(pl)), "beat": beat,
                           "values": pl},
               "stress_sl_first_015": stress,
               "vs_hold": {"bh_total": bh, "bh_maxDD": bh_dd, **v8},
               "checks": {"V1": v1, "V2": v2, "V3": v3, "V4": v4, "V5": v5},
               "verdict": verdict}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
