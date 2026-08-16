"""E60 - the patched BORA protocol, run on the pair S003 was validated on.

Criteria declared in `docs/E60_CRITERIA.md` BEFORE this file existed. Run:

    python e60_bora_sol_link.py

E59 ran BORA's validation protocol verbatim and watched sections 22, 23 and 25
all pass on a filter that lost to random 16 times out of 20.
`docs/BORA_V2_VALIDATION_PATCH.md` fixes three things: a Group C placebo, a
30-trade floor, and a final gate against doing nothing. This runs the patched
protocol on SOL + LINK.

One caveat governs every number here: the flow fields only exist in the Binance
files, and E44-E58 were computed from a different vendor. W2 measures that gap
first, because E51 already found S003's sign is not vendor-stable.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load as yahoo_load, INITIAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "bora-sol-link-e60.json")
PANEL = os.path.join(ROOT, "data", "universe", "spot_1d.json")

PAIRS = (("SOL", "SOL-USD"), ("LINK", "LINK-USD"))
Z_WINDOW, EPS = 100, 0.10
ZTS, PRIMARY_ZT, QS = (1.5, 2.0, 2.5), 2.0, (90, 95)
SEEDS = 20
TRADE_FLOOR = 30                    # PATCH 2, declared before any result
BLOCK, RESAMPLES, W8_BAR = 20, 500, 0.60   # PATCH 3
EXPECTED = {"SOL": 119, "LINK": 177}
STRESS = ("sl_first", 0.0015)


def head(t):
    print("\n" + "=" * 104)
    print(t)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


# --------------------------------------------------------------------------

def load_panel():
    with open(PANEL, encoding="utf-8") as fh:
        panel = json.load(fh)
    feeds, flow, quality = {}, {}, {}
    for sym, _ in PAIRS:
        raw = panel[sym]
        dates = [dt.datetime.fromtimestamp(r[0] / 1000, dt.UTC).strftime("%Y-%m-%d")
                 for r in raw]
        a = np.array([[float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                       float(r[7]), float(r[10])] for r in raw])
        o, h, l, c, qv, tbq = (a[:, i] for i in range(6))
        quality[sym] = {"bars": len(raw), "dup_ts": len(raw) - len({r[0] for r in raw}),
                        "zero_vol": int((qv <= 0).sum()),
                        "taker_le_quote": bool((tbq <= qv + 1e-6).all()),
                        "span": [dates[0], dates[-1]]}
        feeds[sym] = (dates, o, h, l, c)
        flow[sym] = features(o, h, l, c, qv, tbq)
    return feeds, flow, quality


def features(o, h, l, c, qv, tbq):
    delta = tbq - (qv - tbq)
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
        absorb = np.abs(dz) / (impact + EPS)
    pct = np.full(n, np.nan)
    for i in range(Z_WINDOW, n):
        w = absorb[i - Z_WINDOW + 1:i + 1]
        w = w[np.isfinite(w)]
        if len(w) >= 20 and np.isfinite(absorb[i]):
            pct[i] = (w < absorb[i]).mean() * 100.0
    return {"dz": dz, "pct": pct}


def run_book(feeds, keep, intrabar="tp_first", fee=0.0005):
    """S003 across both assets with a signal filter. Returns trades + duty."""
    params = st.Params(fee_side=fee)
    trades, gated, taken = [], 0, 0
    for sym, (dates, o, h, l, c) in feeds.items():
        atr = st.wilder_atr(h, l, c)
        strat = st.strat_type(h, l)
        open_trade = None
        for i in range(len(c)):
            if open_trade is not None and i > open_trade.entry_bar:
                if st.manage_bar(open_trade, i, dates, h, l, intrabar, params):
                    open_trade = None
            if open_trade is None and i >= st.WARMUP:
                side = st.signal_side(strat[i], o[i], c[i])
                if side:
                    gated += 1
                    if keep(sym, i, side):
                        taken += 1
                        p = st.plan_trade(sym, i, dates, o, h, l, c, atr, side, params)
                        if p is not None:
                            open_trade = p
                            trades.append(p)
        if open_trade is not None:
            st.close_trade(open_trade, len(c) - 1, dates, c[-1], "EOD", params.fee_side)
    trades.sort(key=lambda t: (t.exit_date, t.symbol))
    return trades, gated, taken


def port_r(trades):
    return float(sum(t.pnl_r_net for t in trades))


def daily_series(trades, risk, axis):
    at = {d: i for i, d in enumerate(axis)}
    sel = [t for t in trades if t.entry_date in at and t.exit_date in at]
    ev = sorted([(t.entry_date, 0, t) for t in sel] + [(t.exit_date, 1, t) for t in sel],
                key=lambda x: (x[0], x[1]))
    cash, risked, out = INITIAL, {}, np.zeros(len(axis))
    for _, kind, t in ev:
        if kind == 0:
            risked[id(t)] = cash * risk
        else:
            before = cash
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            if before > 0:
                out[at[t.exit_date]] += cash / before - 1.0
            if cash <= 0:
                break
    return out


def stats(rets):
    eq = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(eq)
    return float(eq[-1]), float(((peak - eq) / peak).max())


def main():
    head("E60 - patched BORA protocol x S003 on SOL + LINK | docs/E60_CRITERIA.md")
    feeds, flow, quality = load_panel()
    for sym, q in quality.items():
        ok = q["dup_ts"] == 0 and q["zero_vol"] == 0 and q["taker_le_quote"]
        print(f"  {sym:<5}{q['bars']:>5} bars  {q['span'][0]} -> {q['span'][1]}  "
              f"BORA section 4: {'VALID' if ok else 'INVALID'}")
        if not ok:
            print("  STOP - data quality gate")
            return 1

    keep_all = lambda s, i, side: True
    m0, gated, _ = run_book(feeds, keep_all)
    m0_r = port_r(m0)

    # ---- W1 harness -------------------------------------------------------
    w1 = True
    for sym, (dates, o, h, l, c) in feeds.items():
        solo = st.run_symbol(sym, dates, o, h, l, c).closed
        mine = [t for t in m0 if t.symbol == sym]
        w1 &= len(solo) == len(mine) == EXPECTED[sym]
        w1 &= all(a.entry_date == b.entry_date for a, b in zip(mine, solo))
        print(f"  W1 {sym}: {len(mine)} trades (expected {EXPECTED[sym]})")
    print(f"  W1 filtered engine == plain S003   -> {tick(w1)}")
    if not w1:
        print("  STOP per criteria section 4.")
        return 1

    # ---- W2 vendor gap ----------------------------------------------------
    head("W2 - the vendor gap, measured before anything is read into the result")
    vendor = {}
    for sym, ysym in PAIRS:
        b_dates = feeds[sym][0]
        lo, hi = b_dates[0], b_dates[-1]
        yd, yo, yh, yl, yc, _ = yahoo_load(ysym)
        y = st.run_symbol(ysym, yd, yo, yh, yl, yc).closed
        y_r = float(sum(t.pnl_r_net for t in y if lo <= t.entry_date <= hi))
        b_r = float(sum(t.pnl_r_net for t in m0 if t.symbol == sym))
        vendor[sym] = {"binance": b_r, "yahoo_same_window": y_r,
                       "window": [lo, hi],
                       "sign_flip": (b_r > 0) != (y_r > 0)}
        flag = "  <- SIGN FLIP" if vendor[sym]["sign_flip"] else ""
        print(f"  {sym:<5} Binance {b_r:>+8.2f}   Yahoo (same window) {y_r:>+8.2f}{flag}")
    any_flip = any(v["sign_flip"] for v in vendor.values())
    print(f"  Binance book total portR {m0_r:+.2f} over {gated} gated signals")
    print("  These numbers are NOT comparable to the +72.81 R of E44-E58.")

    # ---- the arms ---------------------------------------------------------
    def confirms(s, i, side):
        z = flow[s]["dz"][i]
        return np.isfinite(z) and (z >= zt if side < 0 else z <= -zt)

    def intensity(s, i, side):
        z = flow[s]["dz"][i]
        return np.isfinite(z) and abs(z) >= zt

    def absorbed(s, i, side):
        p = flow[s]["pct"][i]
        return np.isfinite(p) and p >= q

    def contradicts(s, i, side):
        return np.isfinite(flow[s]["dz"][i]) and not confirms(s, i, side)

    rows = {}
    head("W3/W6 - every arm, with the 30-trade floor applied before any verdict")
    print(f"  {'arm':<36}{'trades':>7}{'duty':>7}{'portR':>10}{'vs M0':>9}  eligible")
    print(f"  {'M0  no filter':<36}{len(m0):>7}{1.0:>7.0%}{m0_r:>10.2f}{'':>9}  yes")
    for zt in ZTS:
        for name, fn in (("M1 flow confirms", confirms),
                         ("M2 intensity only", intensity),
                         ("M4 flow contradicts (Group B)", contradicts)):
            tr, g, took = run_book(feeds, fn)
            r, n = port_r(tr), len(tr)
            el = n >= TRADE_FLOOR
            rows[f"{name.split()[0]}|zt={zt}"] = {
                "arm": name.split()[0], "param": f"zt={zt}", "trades": n,
                "duty": took / g if g else 0.0, "portR": r, "vs_m0": r - m0_r,
                "eligible": el}
            print(f"  {name + f'  Zt={zt}':<36}{n:>7}{took / g:>7.0%}{r:>10.2f}"
                  f"{r - m0_r:>+9.2f}  {'yes' if el else 'NO VERDICT'}")
    for q in QS:
        tr, g, took = run_book(feeds, absorbed)
        r, n = port_r(tr), len(tr)
        rows[f"M3|q={q}"] = {"arm": "M3", "param": f"q={q}", "trades": n,
                             "duty": took / g if g else 0.0, "portR": r,
                             "vs_m0": r - m0_r, "eligible": n >= TRADE_FLOOR}
        print(f"  {'M3 absorption pct  q=' + str(q):<36}{n:>7}{took / g:>7.0%}"
              f"{r:>10.2f}{r - m0_r:>+9.2f}  {'yes' if n >= TRADE_FLOOR else 'NO VERDICT'}")

    # ---- W4 / W5 / W6 at the primary threshold ---------------------------
    zt = PRIMARY_ZT
    m1, m4 = rows[f"M1|zt={zt}"], rows[f"M4|zt={zt}"]
    head(f"W4 - Group C placebo (PATCH 1), the decisive gate | Zt={zt}")
    if not m1["eligible"]:
        print(f"  M1 has {m1['trades']} trades, under the {TRADE_FLOOR} floor "
              f"-> NO VERDICT (PATCH 2). W4/W5/W6 cannot be read.")
        w4 = w5 = w6 = None
        placebo = None
    else:
        duty = m1["duty"]
        pl = []
        for s in range(SEEDS):
            rng = np.random.default_rng(9500 + s)
            tr, _, _ = run_book(feeds, lambda sy, i, side: rng.random() < duty)
            pl.append(port_r(tr))
        p90 = float(np.percentile(pl, 90))
        w4 = m1["portR"] > p90
        beat = sum(1 for x in pl if x >= m1["portR"])
        placebo = {"duty": duty, "p90": p90, "median": float(np.median(pl)),
                   "beat": beat, "values": pl}
        print(f"  M1 keeps {duty:.1%} of gated signals; Group C keeps the same "
              f"share at random, {SEEDS} seeds")
        print(f"  Group C portR  min {min(pl):+.2f}  median {np.median(pl):+.2f}  "
              f"p90 {p90:+.2f}  max {max(pl):+.2f}")
        print(f"  M1 {m1['portR']:+.2f} vs p90 {p90:+.2f}   -> {tick(w4)}"
              f"   ({beat}/{SEEDS} random seeds matched or beat it)")
        w5 = m1["portR"] > m4["portR"]
        w6 = m1["portR"] > m0_r
        head(f"W5 / W6 - BORA's original two tests | Zt={zt}")
        print(f"  W5 Group B control (section 22): M1 {m1['portR']:+.2f} vs "
              f"M4 {m4['portR']:+.2f}   -> {tick(w5)}")
        print(f"  W6 incremental edge (section 25): M1 {m1['portR']:+.2f} vs "
              f"M0 {m0_r:+.2f}   -> {tick(w6)}")

    # ---- W7 stability over eligible cells only ---------------------------
    elig = [z for z in ZTS if rows[f"M1|zt={z}"]["eligible"]]
    wins = sum(1 for z in elig if rows[f"M1|zt={z}"]["portR"] > m0_r)
    w7 = (wins / len(elig) >= 2 / 3) if elig else None
    head("W7 - stability, counting ONLY cells that clear the trade floor")
    if not elig:
        print(f"  no Zt value clears {TRADE_FLOOR} trades -> stability is undefined")
    else:
        for z in elig:
            r = rows[f"M1|zt={z}"]
            print(f"  Zt={z}: M1 {r['portR']:+.2f} vs M0 {m0_r:+.2f} "
                  f"({r['trades']} trades)")
        print(f"  {wins}/{len(elig)} eligible cells beat M0   -> {tick(w7)}")

    # ---- W9 pessimistic corner -------------------------------------------
    head("W9 - the pessimistic corner (sl_first, 0.15%/side)")
    stress = {}
    for name, fn in (("M0", keep_all), ("M1", confirms)):
        zt = PRIMARY_ZT
        tr, _, _ = run_book(feeds, fn, intrabar=STRESS[0], fee=STRESS[1])
        stress[name] = {"portR": port_r(tr), "trades": len(tr)}
        print(f"  {name}  portR {stress[name]['portR']:+.2f}  ({len(tr)} trades)")

    # ---- W8 versus doing nothing (PATCH 3) -------------------------------
    head("W8 - the gate PATCH 3 adds: beat holding, at matched drawdown, "
         "as a distribution")
    axis = sorted(set(feeds["SOL"][0]) & set(feeds["LINK"][0]))
    eq = np.zeros(len(axis))
    for sym in ("SOL", "LINK"):
        d, _, _, _, c = feeds[sym]
        m = {a: b for a, b in zip(d, c)}
        p = np.array([m[x] for x in axis])
        eq += 0.5 * p / p[0]
    bh = np.concatenate([[0.0], eq[1:] / eq[:-1] - 1.0])
    bh_f, bh_dd = stats(bh)
    print(f"  hold SOL+LINK 50/50 over {len(axis)} shared days "
          f"({axis[0]} -> {axis[-1]}): total {bh_f - 1:+.1%}  maxDD {bh_dd:.1%}")

    best = max((r for r in rows.values() if r["eligible"]),
               key=lambda r: r["portR"], default=None)
    cand = [("M0", m0)]
    if best is not None:
        zt = float(best["param"].split("=")[1]) if best["param"].startswith("zt") else None
        q = int(best["param"].split("=")[1]) if best["param"].startswith("q") else None
        fn = {"M1": confirms, "M2": intensity, "M3": absorbed,
              "M4": contradicts}[best["arm"]]
        tr, _, _ = run_book(feeds, fn)
        cand.append((f"{best['arm']} {best['param']}", tr))
        print(f"  best eligible filtered arm: {best['arm']} {best['param']} "
              f"({best['trades']} trades, portR {best['portR']:+.2f})")

    w8_rows = {}
    for label, trades in cand:
        lo_r, hi_r = 0.0005, 0.40
        for _ in range(60):
            mid = (lo_r + hi_r) / 2
            if stats(daily_series(trades, mid, axis))[1] < bh_dd:
                lo_r = mid
            else:
                hi_r = mid
        risk = (lo_r + hi_r) / 2
        ser = daily_series(trades, risk, axis)
        f_, d_ = stats(ser)
        wins_w = 0
        for i in range(RESAMPLES):
            rng = np.random.default_rng(6500 + i)
            order = []
            while len(order) < len(axis):
                s0 = rng.integers(0, max(1, len(axis) - BLOCK + 1))
                order.extend(range(s0, min(s0 + BLOCK, len(axis))))
            order = np.array(order[:len(axis)])
            wins_w += stats(ser[order])[0] > stats(bh[order])[0]
        rate = wins_w / RESAMPLES
        w8_rows[label] = {"matched_risk": risk, "total": f_ - 1, "maxDD": d_,
                          "wealth_win": rate}
        print(f"  {label:<18} risk {risk * 100:>5.2f}%  total {f_ - 1:>+8.1%}  "
              f"maxDD {d_:>6.1%}  beats holding in {rate:>6.1%} of paths "
              f"(need >= {W8_BAR:.0%})")
    w8 = any(v["wealth_win"] >= W8_BAR for v in w8_rows.values())
    print(f"  W8   -> {tick(w8)}")

    # ---- post-hoc, and labelled as such ----------------------------------
    # M3 was not the declared primary arm. Running Group C on it after seeing it
    # beat M0 is selection after the fact, so the result is admissible in ONE
    # direction only: a failure kills the candidate, a pass proves nothing and
    # has to be re-registered. Reported because a negative here is cheap and
    # final, and leaving it unrun would invite exactly the cherry-pick it rules out.
    posthoc = None
    if best is not None and best["arm"] != "M1":
        head(f"POST-HOC (not pre-registered): Group C on {best['arm']} "
             f"{best['param']}")
        duty = best["duty"]
        pl = []
        for s in range(SEEDS):
            rng = np.random.default_rng(9700 + s)
            tr, _, _ = run_book(feeds, lambda sy, i, side: rng.random() < duty)
            pl.append(port_r(tr))
        p90 = float(np.percentile(pl, 90))
        beat = sum(1 for x in pl if x >= best["portR"])
        posthoc = {"arm": f"{best['arm']} {best['param']}", "duty": duty,
                   "p90": p90, "median": float(np.median(pl)), "beat": beat,
                   "portR": best["portR"], "beats_p90": best["portR"] > p90}
        print(f"  Group C at duty {duty:.1%}: median {np.median(pl):+.2f}  "
              f"p90 {p90:+.2f}  |  arm {best['portR']:+.2f}")
        print(f"  {beat}/{SEEDS} random seeds matched or beat it")
        if best["portR"] > p90:
            print("  Clears the placebo -- but this arm was chosen AFTER seeing the")
            print("  table, so it proves nothing. It needs its own pre-registration.")
        else:
            print("  Loses to the placebo. That direction is conclusive: no")
            print("  pre-registration would have rescued it.")

    # ---- verdict ----------------------------------------------------------
    head("VERDICT")
    if w4 is None:
        verdict = "PRIMARY ARM UNANSWERABLE AT THIS SAMPLE SIZE"
        note = (f"M1, the pre-declared primary, is under the {TRADE_FLOOR}-trade "
                "floor at every threshold - that is not evidence of no edge")
    elif not w4:
        verdict = "TRADES LESS, DOES NOT READ FLOW"
        note = "loses to Group C at equal duty - the patch catches what BORA's own tests missed"
    elif w5 and w6 and w8:
        verdict = "ORDER FLOW ADDS EDGE AND IS WORTH IT"
        note = "clears every patched gate; worth a full BORA study under fresh criteria"
    elif w5 and w6:
        verdict = "EDGE REAL, NOT WORTH IT"
        note = "beats placebo and control but does not beat doing nothing"
    else:
        verdict = "NO INCREMENTAL EDGE"
        note = "the price-only proxy already captures it"
    for k, v in (("W1", w1), ("W4", w4), ("W5", w5), ("W6", w6), ("W7", w7),
                 ("W8", w8)):
        print(f"  {k} {tick(v) if v is not None else 'NO VERDICT'}")
    print(f"\n  {verdict}\n  {note}")
    if any_flip:
        print("\n  WARNING: S003's sign is not stable across data vendors on at least")
        print("  one asset here. Every number above sits on the Binance vendor.")
    print("  No promotion. No live orders. Research artifact only.")

    payload = {"experiment": "E60", "criteria": "docs/E60_CRITERIA.md",
               "patch": "docs/BORA_V2_VALIDATION_PATCH.md",
               "quality": quality, "vendor_gap": vendor, "any_sign_flip": any_flip,
               "trade_floor": TRADE_FLOOR, "m0_portR": m0_r,
               "gated_signals": gated, "arms": rows, "placebo": placebo,
               "stress_sl_first_015": stress, "w8": w8_rows, "posthoc_group_c": posthoc,
               "bh": {"total": bh_f - 1, "maxDD": bh_dd, "days": len(axis)},
               "checks": {"W1": w1, "W4": w4, "W5": w5, "W6": w6, "W7": w7,
                          "W8": w8},
               "verdict": verdict}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
