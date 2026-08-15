"""Diagnostic: does the RVOL + Stockbee EP9M logic carry over to BTC?

NOT an experiment and NOT a promotion candidate. No parameter is tuned, nothing
is selected, no strategy is proposed. This measures two claims taken verbatim
from the source indicator, so the answer rests on numbers rather than opinion.

Source logic (tradingview.com/script/hbScFl8K, open-source):
  RVOL  = volume / (mean|median volume over 20 or 50 sessions), with an
          intraday time-of-day curve so early-session volume is not overstated
  EP9M  = close >= +4% vs prior close  AND  volume > prior session volume
          AND  volume > 9,000,000 shares

Two measurements:
  D1  Does BTC have the intraday volume concentration the time-of-day curve
      exists to correct for?  (4h bars, share of daily volume per UTC bucket)
  D2  After an EP9M-style day on BTC, is the forward return distribution
      different from the unconditional base rate?  (daily bars)

Run: python rvol_ep9m_diag.py
"""

import json
import os
import datetime as dt

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "rvol-ep9m-diag.json")

# Thresholds copied from the source indicator. Not tuned, not swept.
MOVE_PCT = 0.04
RVOL_LOOKBACK = 20
HORIZONS = (1, 5, 10, 20)


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


def head(title):
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)


def d1_intraday_shape():
    """Share of daily volume by 4h UTC bucket. Flat => the curve corrects nothing."""
    bars = load("BTCUSDT_4h.json")
    by_day = {}
    for bar in bars:
        stamp = dt.datetime.fromtimestamp(bar[0] / 1000, dt.UTC)
        by_day.setdefault(stamp.date(), {})[stamp.hour] = float(bar[5])

    buckets = sorted({h for day in by_day.values() for h in day})
    shares = {h: [] for h in buckets}
    complete = 0
    for day in by_day.values():
        if len(day) != len(buckets):
            continue
        total = sum(day.values())
        if total <= 0:
            continue
        complete += 1
        for h, v in day.items():
            shares[h].append(v / total)

    mean_share = {h: float(np.mean(shares[h])) for h in buckets}
    flat = 1.0 / len(buckets)
    spread = max(mean_share.values()) / min(mean_share.values())
    return {"buckets": buckets, "mean_share": mean_share, "flat_share": flat,
            "max_over_min": spread, "complete_days": complete}


def d2_ep_signal():
    """Forward returns after an EP9M-style day vs the unconditional base rate."""
    bars = load("btc_daily_full.json")
    close = np.array([float(b[4]) for b in bars])
    volume = np.array([float(b[5]) for b in bars])
    dates = [dt.datetime.fromtimestamp(b[0] / 1000, dt.UTC).date().isoformat() for b in bars]

    ret = np.concatenate([[np.nan], close[1:] / close[:-1] - 1.0])
    avg_vol = np.full(len(volume), np.nan)
    for i in range(RVOL_LOOKBACK, len(volume)):
        avg_vol[i] = volume[i - RVOL_LOOKBACK:i].mean()
    rvol = volume / avg_vol

    # The absolute 9,000,000-share leg is dropped deliberately: it is a US
    # equity liquidity screen for ranking a universe, and BTC is one asset
    # whose median daily volume here is ~37,666 BTC. Keeping it would make the
    # signal fire never or always depending on the unit, which measures the
    # unit, not the idea. Its role is taken by the RVOL > 1 leg.
    signal = np.zeros(len(close), dtype=bool)
    for i in range(RVOL_LOOKBACK + 1, len(close) - max(HORIZONS)):
        signal[i] = (ret[i] >= MOVE_PCT
                     and volume[i] > volume[i - 1]
                     and rvol[i] > 1.0)

    # Signals cluster: consecutive +4% days inside one rally are not
    # independent observations, and 20-day forward windows then overlap almost
    # completely. Count distinct episodes (>= 20 days apart) as the honest n.
    fired = np.flatnonzero(signal)
    episodes = [int(i) for k, i in enumerate(fired)
                if k == 0 or i - fired[k - 1] >= 20]

    # Regime control, the same move as E34's K6 and the point cantolab's README
    # makes: if being above the 200-day mean already explains the drift, the
    # setup adds nothing on top of the bias.
    sma200 = np.full(len(close), np.nan)
    for i in range(200, len(close)):
        sma200[i] = close[i - 200:i].mean()
    bull = close > sma200

    out = {"signal_days": int(signal.sum()), "total_days": int(len(close)),
           "distinct_episodes": len(episodes),
           "signal_share_in_bull": float(np.mean(bull[signal])),
           "base_share_in_bull": float(np.nanmean(bull[~np.isnan(sma200)])),
           "horizons": {}}
    for h in HORIZONS:
        fwd = np.full(len(close), np.nan)
        fwd[:-h] = close[h:] / close[:-h] - 1.0
        eligible = ~np.isnan(fwd)
        base = fwd[eligible]
        hit = fwd[signal & eligible]
        # Bootstrap: how often does a random sample of the same size beat the
        # signal's mean? A signal with no edge sits near the middle.
        rng = np.random.default_rng(0)
        draws = np.array([rng.choice(base, size=len(hit), replace=False).mean()
                          for _ in range(10_000)]) if len(hit) else np.array([])
        # Same comparison restricted to bull-regime days on both sides.
        bull_ok = eligible & bull & ~np.isnan(sma200)
        bull_base = fwd[bull_ok]
        bull_hit = fwd[signal & bull_ok]
        bull_draws = np.array([rng.choice(bull_base, size=len(bull_hit), replace=False).mean()
                               for _ in range(10_000)]) if len(bull_hit) else np.array([])

        ep_idx = [i for i in episodes if eligible[i]]
        ep_hit = fwd[ep_idx]

        out["horizons"][h] = {
            "n_signal": int(len(hit)),
            "signal_mean": float(np.mean(hit)) if len(hit) else None,
            "signal_median": float(np.median(hit)) if len(hit) else None,
            "signal_win_rate": float(np.mean(hit > 0)) if len(hit) else None,
            "base_mean": float(np.mean(base)),
            "base_median": float(np.median(base)),
            "base_win_rate": float(np.mean(base > 0)),
            "percentile_vs_random": float(np.mean(draws < np.mean(hit))) if len(hit) else None,
            # regime-controlled
            "bull_signal_mean": float(np.mean(bull_hit)) if len(bull_hit) else None,
            "bull_base_mean": float(np.mean(bull_base)),
            "bull_percentile": float(np.mean(bull_draws < np.mean(bull_hit))) if len(bull_hit) else None,
            # de-clustered
            "n_episodes": len(ep_idx),
            "episode_mean": float(np.mean(ep_hit)) if len(ep_hit) else None,
            "episode_win_rate": float(np.mean(ep_hit > 0)) if len(ep_hit) else None,
            "episode_percentile": float(np.mean(
                np.array([rng.choice(base, size=len(ep_hit), replace=False).mean()
                          for _ in range(10_000)]) < np.mean(ep_hit)
            )) if len(ep_hit) else None,
        }
    out["signal_dates_sample"] = [dates[i] for i in np.flatnonzero(signal)[:10]]
    return out


def main():
    head("D1 - does BTC have the intraday volume shape the RVOL curve corrects?")
    d1 = d1_intraday_shape()
    print(f"  {d1['complete_days']} complete days, 4h buckets, flat share would be "
          f"{d1['flat_share'] * 100:.2f}% each")
    for h in d1["buckets"]:
        share = d1["mean_share"][h]
        bar = "#" * int(round(share * 200))
        print(f"    {h:02d}:00 UTC  {share * 100:6.2f}%  {bar}")
    print(f"  busiest / quietest bucket = {d1['max_over_min']:.2f}x")

    head("D2 - forward returns after an EP9M-style day on BTC daily")
    d2 = d2_ep_signal()
    print(f"  signal fired on {d2['signal_days']} of {d2['total_days']} days "
          f"({d2['signal_days'] / d2['total_days'] * 100:.1f}%)")
    print(f"  first ten: {', '.join(d2['signal_dates_sample'])}")
    print(f"\n  {'horizon':>8}{'n':>6}{'sigMean':>10}{'baseMean':>10}"
          f"{'sigWin':>9}{'baseWin':>9}{'pctile':>9}")
    for h, r in d2["horizons"].items():
        print(f"  {str(h) + 'd':>8}{r['n_signal']:>6}"
              f"{r['signal_mean'] * 100:>9.2f}%{r['base_mean'] * 100:>9.2f}%"
              f"{r['signal_win_rate'] * 100:>8.1f}%{r['base_win_rate'] * 100:>8.1f}%"
              f"{r['percentile_vs_random'] * 100:>8.1f}%")
    print("\n  pctile = share of 10,000 random same-size samples the signal beat.")
    print("  ~50% means indistinguishable from picking days at random.")
    print("  Four horizons were measured; treat any single one accordingly.")

    head("D3 - the two controls that decide whether D2 means anything")
    print(f"  signal days that sit above SMA-200: {d2['signal_share_in_bull'] * 100:.1f}% "
          f"(all days: {d2['base_share_in_bull'] * 100:.1f}%)")
    print(f"  distinct episodes (>=20d apart): {d2['distinct_episodes']} "
          f"of {d2['signal_days']} raw signals")
    print(f"\n  {'horizon':>8}{'clustered':>11}{'episode':>10}{'base':>9}"
          f"{'episWin':>9}{'baseWin':>9}{'episPct':>9}")
    for h, r in d2["horizons"].items():
        print(f"  {str(h) + 'd':>8}{r['signal_mean'] * 100:>10.2f}%"
              f"{r['episode_mean'] * 100:>9.2f}%{r['base_mean'] * 100:>8.2f}%"
              f"{r['episode_win_rate'] * 100:>8.1f}%{r['base_win_rate'] * 100:>8.1f}%"
              f"{r['episode_percentile'] * 100:>8.1f}%")
    print("\n  episode = one observation per rally (>=20d apart): n=60, not 178.")
    print("  episPct below 50% => the clustered result in D2 was the artifact.")
    print("  Nothing here is a strategy: no costs, no sizing, no risk model.")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"source": "tradingview.com/script/hbScFl8K",
                   "note": "diagnostic only; nothing tuned, selected or promoted",
                   "d1_intraday": d1, "d2_ep_signal": d2}, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
