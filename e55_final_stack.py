"""E55 - closing the four gaps between the locked `final_logic.md` and the code.

Criteria declared in `docs/E55_CRITERIA.md` BEFORE this file existed. Run:

    python e55_final_stack.py

The spec arrived locked, with performance numbers attached. None of those
numbers are used here as a target or as evidence - only the *rules* are taken,
and each is tested like any other newcomer. Four questions, in order:

  A  does the S017 portfolio cooldown have a mechanism, or does it just trade
     less? (E48 taught us the difference is a placebo away)
  B  what drawdown does the spec's 4%-of-shared-equity actually buy
  C  does the overlay written in the spec - clamp 4.0, expanding sigma_ref -
     beat flat sizing at the same drawdown budget
  D  how much does the undocumented break-even-bar rule move the result

E47/E48/E49 are not touched: E48 and E49 import harness constants from E47, so
editing it retroactively would void three logged results. The spec-faithful
overlay is therefore rebuilt here rather than patched into E47.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load, ASSETS, INITIAL
from e47_sizing_overlay import cagr, DD_TARGET, VOL_LOOKBACK
from e48_v4_adversarial import run as e48_run

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "final-stack-e55.json")
E45 = os.path.join(ROOT, "docs", "s003-full-e45.json")

IS_FROM, SPLIT, OOS_TO = "2017-11-09", "2022-08-01", "2026-08-13"
FOLD_START, FOLD_MONTHS = "2018-02-01", 6

SEEDS = 20
LEVELS = (0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10)
SPEC_RISK = 0.04
BLOCK, RESAMPLES = 10, 500          # identical to E49
TOLERANCES = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70)
RUIN_DD = 0.80

STREAKS, SKIPS = (3, 4, 5), (1, 2, 3)
GAMMAS, CLAMP_HI = (-1.0, -0.5, 0.0), (2.0, 4.0)
SPEC_GAMMA, SPEC_CLAMP = -0.5, 4.0
CLAMP_LO = 0.25


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

_FEEDS, _VOL = {}, {}


def feeds():
    """SOL + LINK daily bars, plus each bar's realised vol and expanding median.

    `sigma_ref` is the expanding median the spec asks for: at bar i it is the
    median of every sigma observed up to and including i, so it uses no future
    data. E47 used a single constant instead - that is the difference C exists
    to measure.
    """
    if _FEEDS:
        return _FEEDS
    for symbol in ASSETS:
        dates, o, h, l, c, _ = load(symbol)
        _FEEDS[symbol] = (dates, o, h, l, c)
        with np.errstate(invalid="ignore", divide="ignore"):
            rets = np.concatenate([[np.nan], np.diff(np.log(c))])
        vol = np.full(len(c), np.nan)
        for i in range(VOL_LOOKBACK, len(c)):
            w = rets[i - VOL_LOOKBACK + 1:i + 1]
            if not np.isnan(w).any():
                vol[i] = float(np.std(w, ddof=1) * np.sqrt(365))
        ref = np.full(len(c), np.nan)
        seen = []
        for i in range(len(c)):
            if np.isfinite(vol[i]):
                seen.append(vol[i])
            if seen:
                ref[i] = float(np.median(seen))
        _VOL[symbol] = (vol, ref)
    return _FEEDS


def book(**kw):
    """One portfolio run, with vol context attached to every trade."""
    res = st.run_portfolio(feeds(), **kw)
    for t in res.closed:
        vol, ref = _VOL[t.symbol]
        t.entry_vol = float(vol[t.entry_bar])
        t.vol_ref = float(ref[t.entry_bar])
    return res


def window(trades, lo=IS_FROM, hi=OOS_TO):
    return [t for t in trades if lo <= t.entry_date < hi]


def port_r(trades):
    return float(sum(t.pnl_r_net for t in trades))


def fold_bounds():
    out, y, m = [], *[int(x) for x in FOLD_START.split("-")[:2]]
    while f"{y}-{m:02d}-01" <= OOS_TO:
        out.append(f"{y}-{m:02d}-01")
        m += FOLD_MONTHS
        if m > 12:
            m -= 12
            y += 1
    return out


def exit_folds(trades):
    """Half-year folds keyed on EXIT date - the spec's own accounting for S017."""
    b = fold_bounds()
    out = []
    for k in range(len(b) - 1):
        rs = [t.pnl_r_net for t in trades if b[k] <= t.exit_date < b[k + 1]]
        if rs:
            out.append({"from": b[k], "to": b[k + 1], "n": len(rs),
                        "R": float(sum(rs))})
    return out


# --------------------------------------------------------------------------
# equity paths
# --------------------------------------------------------------------------

def path(trades, risk, lo, hi, *, scale_of=None, order=None):
    """Equity path, risk fixed at entry. `scale_of(t)` multiplies that risk.

    With `scale_of=None` and `order=None` this is E48's `run(..., "flat")`; a
    harness check below pins that, because B has to be comparable to E49.
    """
    sel = window(trades, lo, hi)
    if not sel:
        return INITIAL, 0.0, 0
    if order is not None:
        sel = [sel[i] for i in order if i < len(sel)]
        events = []
        for k, t in enumerate(sel):
            events += [(k, 0, t), (k, 1, t)]
        events.sort(key=lambda x: (x[0], x[1]))
    else:
        events = sorted([(t.entry_date, 0, t) for t in sel]
                        + [(t.exit_date, 1, t) for t in sel],
                        key=lambda x: (x[0], x[1]))

    cash, risked, curve = INITIAL, {}, [INITIAL]
    for _, kind, t in events:
        if kind == 0:
            s = 1.0 if scale_of is None else scale_of(t)
            risked[id(t)] = cash * risk * s
        else:
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0, len(sel)
    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return cash, float(((peak - arr) / peak).max()), len(sel)


def block_orders(n, rng):
    out = []
    while len(out) < n:
        s = rng.integers(0, max(1, n - BLOCK + 1))
        out.extend(range(s, min(s + BLOCK, n)))
    return np.array(out[:n])


def calibrate(trades, target, lo, hi, scale_of=None):
    lo_r, hi_r = 0.001, 0.40
    for _ in range(60):
        mid = (lo_r + hi_r) / 2
        _, dd, _ = path(trades, mid, lo, hi, scale_of=scale_of)
        if dd < target:
            lo_r = mid
        else:
            hi_r = mid
    return (lo_r + hi_r) / 2


def overlay_scale(gamma, clamp_hi):
    def scale_of(t):
        if not np.isfinite(t.entry_vol) or t.entry_vol <= 0 or t.vol_ref <= 0:
            return 1.0
        return float(np.clip((t.entry_vol / t.vol_ref) ** gamma, CLAMP_LO, clamp_hi))
    return scale_of


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    head("E55 - the locked stack, measured | criteria docs/E55_CRITERIA.md")
    print("  spec: S003 trap core + S017 portfolio cooldown 4/2 + 4% of shared equity")
    print("  the spec's own performance numbers are used NOWHERE in this file")

    s003 = book()
    s017 = book(cooldown=st.S017)
    base, cool = s003.closed, s017.closed

    # ---- H1 / H2 harness --------------------------------------------------
    h1 = True
    for symbol in ASSETS:
        dates, o, h, l, c = feeds()[symbol]
        solo = st.run_symbol(symbol, dates, o, h, l, c).closed
        mine = s003.per_symbol[symbol].closed
        same = len(solo) == len(mine) and all(
            a.entry_date == b.entry_date and a.exit_date == b.exit_date
            and abs(a.pnl_r_net - b.pnl_r_net) < 1e-12
            for a, b in zip(solo, mine))
        h1 &= same
        print(f"  H1 {symbol:<10}{len(mine):>4} trades, identical to run_symbol"
              f" -> {tick(same)}")
    with open(E45, encoding="utf-8") as fh:
        e45_r = json.load(fh)["total_portR"]
    h2 = abs(port_r(base) - e45_r) <= 0.01
    print(f"  H2 portR {port_r(base):+.2f} vs E45 {e45_r:+.2f}   -> {tick(h2)}")

    # the local path model must equal E49's, or B is not comparable to E49
    a, b_, _ = path(base, 0.06, IS_FROM, OOS_TO)
    c_, d_, _ = e48_run(base, 0.06, "flat", IS_FROM, OOS_TO)
    h3 = abs(a - c_) < 1e-6 and abs(b_ - d_) < 1e-9
    print(f"  H3 local path model == E48/E49 path model   -> {tick(h3)}")
    if not (h1 and h2 and h3):
        print("\n  STOP per criteria section 2.")
        return 1

    res = {}

    # ======================================================================
    # A - does S017 have a mechanism
    # ======================================================================
    head("A - S017 portfolio cooldown (streak 4 -> skip 2)")
    r003, r017 = port_r(base), port_r(cool)
    a1 = r017 > r003
    print(f"  trades      S003 {len(base):>4}   S017 {len(cool):>4}"
          f"   ({len(s017.skipped)} signals skipped of {s017.signals} gated,"
          f" duty {s017.duty:.1%})")
    print(f"  portR       S003 {r003:>+8.2f}   S017 {r017:>+8.2f}   -> A1 {tick(a1)}")

    f003, f017 = exit_folds(base), exit_folds(cool)
    m003 = min(f["R"] for f in f003)
    m017 = min(f["R"] for f in f017)
    a2 = m017 >= m003
    print(f"  min fold    S003 {m003:>+8.2f}   S017 {m017:>+8.2f}   -> A2 {tick(a2)}")
    print(f"  pos folds   S003 {sum(1 for f in f003 if f['R'] > 0)}/{len(f003)}"
          f"        S017 {sum(1 for f in f017 if f['R'] > 0)}/{len(f017)}")

    # ---- A3 placebo -------------------------------------------------------
    duty = s017.duty
    pl = []
    for s in range(SEEDS):
        rng = np.random.default_rng(7000 + s)
        pl.append(port_r(book(skip_decider=lambda _s, _d: rng.random() < duty).closed))
    p90 = float(np.percentile(pl, 90))
    a3 = r017 > p90
    beat = sum(1 for x in pl if x >= r017)
    head("A3 - placebo: skip the same share of signals at random, 20 seeds")
    print(f"  placebo portR  min {min(pl):+.2f}  median {np.median(pl):+.2f}"
          f"  p90 {p90:+.2f}  max {max(pl):+.2f}")
    print(f"  S017 {r017:+.2f} vs p90 {p90:+.2f}   -> {tick(a3)}"
          f"   ({beat}/{SEEDS} random seeds matched or beat it)")
    print(f"  S003 (skip nothing) {r003:+.2f} sits at percentile "
          f"{(np.array(pl) < r003).mean() * 100:.0f} of the placebo")

    # ---- A4 neighbourhood -------------------------------------------------
    head("A4 - parameter neighbourhood: streak x skip")
    grid, survive = [], 0
    print(f"  {'streak':>7}" + "".join(f"{f'skip {k}':>12}" for k in SKIPS))
    for s_ in STREAKS:
        cells = []
        for k in SKIPS:
            r = port_r(book(cooldown=st.Cooldown(streak=s_, skip=k)).closed)
            ok = r > r003
            survive += ok
            grid.append({"streak": s_, "skip": k, "portR": r, "beats_s003": ok})
            cells.append(f"{r:+.2f}{'*' if ok else ' '}")
        print(f"  {s_:>7}" + "".join(f"{c:>12}" for c in cells))
    a4 = survive >= 5
    print(f"  * = beats S003 ({r003:+.2f}) | {survive}/9   -> {tick(a4)}")

    # ---- A5 per asset -----------------------------------------------------
    head("A5 - each asset on its own")
    per, a5 = {}, True
    for symbol in ASSETS:
        x, y = port_r(s003.per_symbol[symbol].closed), port_r(s017.per_symbol[symbol].closed)
        ok = y > x
        a5 &= ok
        per[symbol] = {"s003": x, "s017": y, "s017_wins": ok}
        print(f"  {symbol:<10}S003 {x:>+8.2f}   S017 {y:>+8.2f}   -> "
              f"{'S017' if ok else 'S003'}")
    print(f"  S017 must win both   -> {tick(a5)}")

    # ---- A6 pessimistic intrabar -----------------------------------------
    sl003 = port_r(book(intrabar="sl_first").closed)
    sl017 = port_r(book(cooldown=st.S017, intrabar="sl_first").closed)
    a6 = sl017 > sl003
    head("A6 - the pessimistic intrabar model")
    print(f"  sl_first    S003 {sl003:>+8.2f}   S017 {sl017:>+8.2f}   -> {tick(a6)}")

    # ---- the variants the spec says failed --------------------------------
    head("Variants the spec rules out - reported whether they help or not")
    v_split = port_r(book(cooldown=st.Cooldown(4, 2, per_symbol=True)).closed)
    v_two = port_r(book(cooldown=st.Cooldown(2, 2)).closed)
    print(f"  per-coin streak 4/2   {v_split:>+8.2f}"
          f"   {'BETTER than 4/2 shared' if v_split > r017 else 'worse than 4/2 shared'}")
    print(f"  pause after 2 losses  {v_two:>+8.2f}"
          f"   {'BETTER than 4/2 shared' if v_two > r017 else 'worse than 4/2 shared'}")

    res["A"] = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "A6": a6,
                "s003_portR": r003, "s017_portR": r017,
                "s003_trades": len(base), "s017_trades": len(cool),
                "skipped": len(s017.skipped), "gated_signals": s017.signals,
                "duty": duty, "placebo": {"p90": p90, "median": float(np.median(pl)),
                                          "beat": beat, "all": pl},
                "min_fold": {"s003": m003, "s017": m017},
                "folds": {"s003": f003, "s017": f017},
                "grid": grid, "per_asset": per,
                "sl_first": {"s003": sl003, "s017": sl017},
                "ruled_out": {"per_symbol_4_2": v_split, "pause_after_2": v_two}}

    a_pass = all([a1, a2, a3, a4, a5, a6])
    print(f"\n  A verdict: {'S017 has a mechanism' if a_pass else 'S017 NOT SUPPORTED'}"
          f"   (promotion forbidden either way)")

    # ======================================================================
    # B - what 4% of shared equity actually costs
    # ======================================================================
    head("B - risk per trade, drawdown as a distribution (E49 method, E55 book)")
    stacks = {"S003": base, "S017": cool}
    b_rows = {}
    for name, tr in stacks.items():
        n = len(window(tr))
        rows = {}
        for risk in LEVELS:
            fi, ddi, _ = path(tr, risk, IS_FROM, SPLIT)
            fo, ddo, _ = path(tr, risk, SPLIT, OOS_TO)
            ff, ddf, _ = path(tr, risk, IS_FROM, OOS_TO)
            sf, sdd, _ = path(tr, risk, IS_FROM, OOS_TO, order=np.arange(n))
            dds = []
            for s in range(RESAMPLES):
                rng = np.random.default_rng(5000 + s)
                _, dd, _ = path(tr, risk, IS_FROM, OOS_TO,
                                order=block_orders(n, rng))
                dds.append(dd)
            dds = np.array(dds)
            rows[f"{risk:.3f}"] = {
                "risk": risk,
                "IS": {"cagr": cagr(fi, tr, IS_FROM, SPLIT), "maxDD": ddi},
                "OOS": {"cagr": cagr(fo, tr, SPLIT, OOS_TO), "maxDD": ddo},
                "full": {"cagr": cagr(ff, tr, IS_FROM, OOS_TO), "maxDD": ddf,
                         "final": ff},
                "sequential_ref": {"maxDD": sdd, "final": sf},
                "bootstrap": {"dd_median": float(np.median(dds)),
                              "dd_p90": float(np.percentile(dds, 90)),
                              "dd_p95": float(np.percentile(dds, 95)),
                              "dd_max": float(dds.max()),
                              "ruin_share": float((dds > RUIN_DD).mean())}}
        b_rows[name] = rows

        print(f"\n  {name} ({n} trades)")
        print(f"  {'risk':>6}{'IS CAGR':>10}{'IS DD':>8}{'OOS CAGR':>11}{'OOS DD':>9}"
              f"{'full CAGR':>11}{'full DD':>9}{'boot p90':>10}{'boot p95':>10}"
              f"{'DD>80%':>9}")
        for r in rows.values():
            mark = "  <- spec" if abs(r["risk"] - SPEC_RISK) < 1e-9 else ""
            bt = r["bootstrap"]
            print(f"  {r['risk'] * 100:>5.1f}%{r['IS']['cagr']:>+10.1%}"
                  f"{r['IS']['maxDD']:>8.1%}{r['OOS']['cagr']:>+11.1%}"
                  f"{r['OOS']['maxDD']:>9.1%}{r['full']['cagr']:>+11.1%}"
                  f"{r['full']['maxDD']:>9.1%}{bt['dd_p90']:>10.1%}"
                  f"{bt['dd_p95']:>10.1%}{bt['ruin_share']:>9.1%}{mark}")

    head("B3 - the drawdown tolerance the spec's 4% actually demands")
    demand = {}
    for name, rows in b_rows.items():
        r = rows[f"{SPEC_RISK:.3f}"]
        bt = r["bootstrap"]
        need = float(np.ceil(bt["dd_p90"] * 20) / 20)     # round up to 5%
        demand[name] = need
        print(f"  {name}: 4%/trade -> full-history CAGR {r['full']['cagr']:+.1%}, "
              f"realised DD {r['full']['maxDD']:.1%}")
        print(f"        bootstrap p90 {bt['dd_p90']:.1%} | p95 {bt['dd_p95']:.1%} | "
              f"worst {bt['dd_max']:.1%} | paths ruined {bt['ruin_share']:.1%}")
        print(f"        => demands a drawdown tolerance of at least "
              f"**{need:.0%}**"
              f"{'   <-- above 50%: most people cannot hold this' if need > 0.50 else ''}")

    head("B4 - tolerance -> risk, by E49's declared rule (highest risk with p90 DD <= tol)")
    mapping = {}
    print(f"  {'tolerance':>10}" + "".join(f"{n:>12}" for n in stacks))
    for tol in TOLERANCES:
        cells = []
        for name, rows in b_rows.items():
            ok = [r for r in rows.values() if r["bootstrap"]["dd_p90"] <= tol]
            pick = max(ok, key=lambda r: r["risk"])["risk"] if ok else None
            mapping.setdefault(f"{tol:.2f}", {})[name] = pick
            cells.append(f"{pick * 100:.1f}%" if pick else "none")
        print(f"  {tol:>9.0%}" + "".join(f"{c:>12}" for c in cells))

    res["B"] = {"levels": b_rows, "spec_risk": SPEC_RISK,
                "tolerance_demanded": demand, "tolerance_to_risk": mapping,
                "block": BLOCK, "resamples": RESAMPLES}

    # ======================================================================
    # C - the overlay as the spec actually writes it
    # ======================================================================
    head("C - vol overlay, spec-faithful (gamma -0.5, clamp [0.25, 4.0], expanding ref)")
    trades = cool if a_pass else base
    label = "S017" if a_pass else "S003"
    print(f"  measured on the {label} book (A "
          f"{'passed' if a_pass else 'failed, so the overlay is judged on S003'})")

    spec_scale = overlay_scale(SPEC_GAMMA, SPEC_CLAMP)
    sc = np.array([spec_scale(t) for t in window(trades)])
    print(f"  scale applied: min {sc.min():.2f}  median {np.median(sc):.2f}  "
          f"max {sc.max():.2f}  (clipped at the ceiling {np.mean(sc >= SPEC_CLAMP - 1e-9):.0%}"
          f" of the time)")

    r_flat = calibrate(trades, DD_TARGET, IS_FROM, SPLIT)
    r_ovl = calibrate(trades, DD_TARGET, IS_FROM, SPLIT, scale_of=spec_scale)
    fi0, di0, _ = path(trades, r_flat, IS_FROM, SPLIT)
    fo0, do0, _ = path(trades, r_flat, SPLIT, OOS_TO)
    fi1, di1, _ = path(trades, r_ovl, IS_FROM, SPLIT, scale_of=spec_scale)
    fo1, do1, _ = path(trades, r_ovl, SPLIT, OOS_TO, scale_of=spec_scale)
    c0, c1 = cagr(fo0, trades, SPLIT, OOS_TO), cagr(fo1, trades, SPLIT, OOS_TO)
    c1_ok, c2_ok = c1 > c0, do1 <= do0
    print(f"  both calibrated to IS maxDD {DD_TARGET:.0%}: "
          f"flat risk {r_flat * 100:.2f}%  overlay risk {r_ovl * 100:.2f}%")
    print(f"  IS   flat {cagr(fi0, trades, IS_FROM, SPLIT):+.1%}/{di0:.1%}"
          f"   overlay {cagr(fi1, trades, IS_FROM, SPLIT):+.1%}/{di1:.1%}")
    print(f"  OOS  flat {c0:+.1%}/{do0:.1%}   overlay {c1:+.1%}/{do1:.1%}")
    print(f"  C1 OOS CAGR overlay > flat   -> {tick(c1_ok)}")
    print(f"  C2 OOS maxDD overlay <= flat -> {tick(c2_ok)}")

    sel = window(trades)
    pl_c = []
    for s in range(SEEDS):
        perm = np.random.default_rng(8000 + s).permutation(len(sel))
        shuffled = {id(t): float(sc[perm[k]]) for k, t in enumerate(sel)}
        f, _, _ = path(trades, r_ovl, SPLIT, OOS_TO,
                       scale_of=lambda t: shuffled.get(id(t), 1.0))
        pl_c.append(cagr(f, trades, SPLIT, OOS_TO))
    p90_c = float(np.percentile(pl_c, 90))
    c3_ok = c1 > p90_c
    print(f"\n  C3 placebo: same scales, shuffled onto the wrong trades, 20 seeds")
    print(f"     placebo OOS CAGR  median {np.median(pl_c):+.1%}  p90 {p90_c:+.1%}"
          f"  max {max(pl_c):+.1%}")
    print(f"     overlay {c1:+.1%} vs p90 {p90_c:+.1%}   -> {tick(c3_ok)}")

    head("C4 - exponent x clamp neighbourhood (all calibrated to the same IS DD)")
    print(f"  {'gamma':>7}" + "".join(f"{f'clamp {h:g}':>14}" for h in CLAMP_HI))
    cgrid = []
    for g in GAMMAS:
        cells = []
        for hi_ in CLAMP_HI:
            sfn = overlay_scale(g, hi_)
            rr = calibrate(trades, DD_TARGET, IS_FROM, SPLIT, scale_of=sfn)
            f, dd, _ = path(trades, rr, SPLIT, OOS_TO, scale_of=sfn)
            cg = cagr(f, trades, SPLIT, OOS_TO)
            spec = abs(g - SPEC_GAMMA) < 1e-9 and abs(hi_ - SPEC_CLAMP) < 1e-9
            cgrid.append({"gamma": g, "clamp": hi_, "oos_cagr": cg, "oos_dd": dd,
                          "risk": rr, "is_spec": spec})
            cells.append(f"{cg:+.1%}{'*' if cg > c0 else ' '}{'S' if spec else ' '}")
        print(f"  {g:>7.1f}" + "".join(f"{c:>14}" for c in cells))
    print(f"  * = beats flat OOS ({c0:+.1%})  |  S = the spec's own cell  |  "
          f"gamma 0 IS flat (sanity)")

    res["C"] = {"book": label, "C1": c1_ok, "C2": c2_ok, "C3": c3_ok,
                "flat": {"risk": r_flat, "oos_cagr": c0, "oos_dd": do0},
                "overlay": {"risk": r_ovl, "oos_cagr": c1, "oos_dd": do1},
                "placebo": {"p90": p90_c, "median": float(np.median(pl_c))},
                "grid": cgrid,
                "scale": {"min": float(sc.min()), "max": float(sc.max()),
                          "median": float(np.median(sc))}}

    # ======================================================================
    # D - the break-even-bar rule
    # ======================================================================
    head("D - the BE-arming-bar rule the locked spec never states")
    d_rows = {}
    for name, kw in (("S003", {}), ("S017", {"cooldown": st.S017})):
        coded = port_r(book(**kw).closed)
        literal = port_r(book(be_on_arming_bar=True, **kw).closed)
        gap = abs(literal - coded) / abs(coded) if coded else float("inf")
        d_rows[name] = {"coded": coded, "literal": literal, "gap": gap}
        print(f"  {name}  coded (survives the arming bar) {coded:>+8.2f}"
              f"   literal (can stop at BE) {literal:>+8.2f}"
              f"   gap {gap:.1%}")
    d_gap = max(r["gap"] for r in d_rows.values())
    material = d_gap > 0.05
    print(f"\n  D2 largest gap {d_gap:.1%} -> the rule is "
          f"{'MATERIAL' if material else 'immaterial'} by the declared 5% line")
    if material:
        print("  Per the decision table: keep the coded rule (every result from E44 on")
        print("  depends on it), write it into final_logic.md section 4, and report the")
        print("  literal reading as a permanent error bar alongside sl_first.")
    else:
        print("  Per the decision table: keep the coded rule and add one sentence to")
        print("  final_logic.md section 4 so the spec stops being silent about it.")
    res["D"] = {"rows": d_rows, "gap": d_gap, "material": material}

    # ======================================================================
    head("VERDICT")
    print(f"  A  S017 cooldown        {'SUPPORTED' if a_pass else 'NOT SUPPORTED'}"
          f"   (A1 {tick(a1)} A2 {tick(a2)} A3 {tick(a3)} A4 {tick(a4)}"
          f" A5 {tick(a5)} A6 {tick(a6)})")
    print(f"  B  4% shared equity     demands a DD tolerance of "
          f"{max(demand.values()):.0%} on the {label} book")
    print(f"  C  spec overlay         C1 {tick(c1_ok)} C2 {tick(c2_ok)} "
          f"C3 {tick(c3_ok)} -> "
          f"{'worth it' if (c1_ok and c2_ok and c3_ok) else 'stays OPTIONAL, unsupported'}")
    print(f"  D  BE-arming-bar rule   gap {d_gap:.1%} -> "
          f"{'must be documented AND reported as an error bar' if material else 'document it'}")
    print("\n  No promotion. No live orders. Research artifact only.")

    payload = {"experiment": "E55", "criteria": "docs/E55_CRITERIA.md",
               "harness": {"H1": h1, "H2": h2, "H3": h3},
               "windows": {"IS_FROM": IS_FROM, "SPLIT": SPLIT, "OOS_TO": OOS_TO},
               **res,
               "verdict": {"A_supported": a_pass,
                           "B_tolerance_demanded": demand,
                           "C_worth_it": bool(c1_ok and c2_ok and c3_ok),
                           "D_material": bool(material)},
               "note": "measurement only - no tuning, no selection, no promotion"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
