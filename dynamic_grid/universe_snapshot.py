"""Point-in-time universe snapshots from TradingView's public scanner.

Adapted from `deepentropy/tvscreener` (Apache-2.0) — the *endpoint contract*
only, not the package. See `docs/TVSCREENER_ADOPTION.md` for what was rejected
and why; `integrations/tvscreener-source.lock.json` pins the reviewed revision.

    POST https://scanner.tradingview.com/{market}/scan
    {"columns": [...], "filter": [...], "symbols": {...}, "range": [0, n], "sort": {...}}
    GET  https://scanner.tradingview.com/{market}/metainfo

No API key, no auth, JSON in / JSON out — the same shape as the Binance klines
and Yahoo chart loaders already in this package.

Why this module exists, and what it deliberately refuses to do
--------------------------------------------------------------
The scanner returns **today's** market and nothing else. That makes it useless
as backtest data and dangerous as a selection layer:

* E31 recorded a residual survivorship bias — "universe drawn from today's
  listings". Screening today and backtesting yesterday *is* that bias.
* E33 measured what an asset screen costs: the trend screen dropped 54% of the
  names whose trend was positive, and the dropped names beat the kept names at
  every horizon (90d +26.5% vs +16.3%). A prettier screener API does not change
  that result.

So a snapshot here is **evidence with a date on it**, not a filter. The one
guarantee this module provides is `load_as_of`: research may only see a
universe that was recorded *on or before* the first bar it trades. When no such
snapshot exists — which is the case for every experiment before today — it
raises instead of quietly handing back the present. The survivorship problem
becomes loud rather than silent.

The exception that proves the rule is `INDEX_UNIVERSES`: SET50 membership is
decided by SET, not by us, so it is a universe definition rather than a screen
of ours. That is why index profiles carry no filters at all.

CLI:

    python -m dynamic_grid.universe_snapshot --list
    python -m dynamic_grid.universe_snapshot --profile set50
    python -m dynamic_grid.universe_snapshot --profile binance-spot-usdt
    python -m dynamic_grid.universe_snapshot --fields dividend --market thailand
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

SCANNER_URL = "https://scanner.tradingview.com/{market}/scan"
METAINFO_URL = "https://scanner.tradingview.com/{market}/metainfo"
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "universe", "snapshots")

#: Markets this module is allowed to touch. Anything else must be added
#: deliberately, with a profile, so an accidental typo cannot widen the scope.
MARKETS = ("thailand", "america", "crypto")

PAGE_SIZE = 500
PAUSE_SECONDS = 1.0


class DeadSortColumn(ValueError):
    """The column the universe was ordered by came back entirely empty.

    Measured hazard: `Value.Traded` returns real numbers on `thailand` and
    nothing at all on `crypto`, and the endpoint answers 200 either way. Sorting
    on the dead column leaves an arbitrary — though stable — server-side order,
    so a truncated fetch silently records an arbitrary subset of the universe
    while looking perfectly healthy.
    """


class NoPointInTimeUniverse(LookupError):
    """No snapshot was recorded on or before the requested date.

    Raised rather than returning the newest available snapshot: handing back a
    universe recorded *after* the bars it will select is exactly the lookahead
    this module exists to prevent.
    """


@dataclass(frozen=True)
class Profile:
    """A named, frozen recipe for one universe.

    The filters are part of the record. A liquidity or listing rule applied at
    time T is legitimate; the same rule applied with hindsight is not, and the
    only way to tell the two apart later is to have written the rule down next
    to the timestamp.
    """

    name: str
    market: str
    columns: tuple
    filters: tuple = ()
    #: TradingView symbolset(s), e.g. `SYML:SET;SET50`. When set, membership —
    #: not our filters — defines the universe. That distinction is the whole
    #: reason these profiles exist; see `INDEX_UNIVERSES` below.
    symbolset: tuple = ()
    sort_by: str = ""
    sort_order: str = "desc"
    max_rows: int = 1000
    note: str = ""

    def payload(self, start: int, end: int) -> dict:
        body = {
            "columns": list(self.columns),
            "range": [start, end],
            "options": {"lang": "en"},
        }
        if self.symbolset:
            body["symbols"] = {"symbolset": list(self.symbolset)}
        if self.filters:
            body["filter"] = [dict(f) for f in self.filters]
        if self.sort_by:
            body["sort"] = {"sortBy": self.sort_by, "sortOrder": self.sort_order}
        return body


PROFILES = {
    # 2,250 rows come back unfiltered, but most are derivative warrants that
    # inherit the underlying's market cap (NVDA01 reported 179 trillion THB and
    # outranked DELTA). `type == stock` + `is_primary` leaves 880 real listings.
    "set-stocks": Profile(
        name="set-stocks",
        market="thailand",
        columns=("name", "description", "close", "volume", "market_cap_basic",
                 "sector", "industry", "type", "typespecs", "currency"),
        filters=({"left": "type", "operation": "equal", "right": "stock"},
                 {"left": "is_primary", "operation": "equal", "right": True}),
        sort_by="market_cap_basic",
        max_rows=1000,
        note="SET/mai primary common listings. Warrants and DRs excluded by filter.",
    ),
    # 57,074 crypto rows across every venue; pinning exchange + quote + spot
    # leaves 489. Perpetuals (`.P` suffix) are a different instrument and are
    # excluded by `type == spot`. Stablecoin pairs are NOT excluded — the raw
    # snapshot stays raw, and a consumer that wants coins filters them itself.
    "binance-spot-usdt": Profile(
        name="binance-spot-usdt",
        market="crypto",
        columns=("base_currency", "base_currency_desc", "currency", "exchange",
                 "type", "close", "24h_vol|5", "market_cap_calc"),
        filters=({"left": "exchange", "operation": "in_range", "right": ["BINANCE"]},
                 {"left": "currency", "operation": "equal", "right": "USDT"},
                 {"left": "type", "operation": "equal", "right": "spot"}),
        sort_by="24h_vol|5",
        max_rows=1000,
        note="Binance spot USDT pairs ranked by 24h quote volume at fetch time.",
    ),
}

# Index constituents, requested by symbolset rather than by filter.
#
# These matter more than the filtered profiles above, and for one reason: the
# membership rule is **exogenous**. SET decides who is in SET50; we do not, we
# cannot tune it, and we cannot fit it to a backtest. E33's failure was a screen
# *we* invented selecting assets on their own past statistics — an index
# constituent list is not that, which is why it is the standard universe
# definition in equity research and why it is worth recording daily.
#
# No `type`/`is_primary` filter is applied: membership is the definition, and a
# filter of ours on top would be us quietly editing someone else's universe.
INDEX_UNIVERSES = {
    "set50": ("SYML:SET;SET50", "SET50 constituents: the liquid Thai large-cap universe. AOT is a member."),
    "set100": ("SYML:SET;SET100", "SET100 constituents: SET50 plus the next tier."),
}

for _name, (_symbolset, _note) in INDEX_UNIVERSES.items():
    PROFILES[_name] = Profile(
        name=_name,
        market="thailand",
        columns=("name", "description", "close", "volume", "market_cap_basic",
                 "sector", "industry", "type", "typespecs", "currency"),
        symbolset=(_symbolset,),
        sort_by="market_cap_basic",
        max_rows=500,
        note=_note,
    )


def _get(url: str, timeout: int = 30) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _post(url: str, body: dict, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def empty_columns(columns, rows) -> list:
    """Columns whose value is missing on every row."""
    if not rows:
        return []
    return [name for index, name in enumerate(columns)
            if all(row["values"][index] is None for row in rows)]


def metainfo(market: str, transport=None) -> list:
    """The market's advertised field catalogue: `[{name, type}, ...]`.

    A **discovery aid, not an allowlist.** Measured: `Value.Traded` is absent
    from every market's metainfo yet returns real numbers on `thailand`, so
    rejecting unlisted columns would reject working ones. The reliable check on
    a column is empirical — fetch it and see whether anything came back.
    """
    if market not in MARKETS:
        raise ValueError(f"market not allowlisted: {market!r}")
    transport = transport or _get
    payload = transport(METAINFO_URL.format(market=market))
    return [{"name": f["n"], "type": f.get("t")} for f in payload.get("fields", [])]


def search_fields(market: str, keyword: str, transport=None) -> list:
    """Catalogue entries whose name contains `keyword` (case-insensitive)."""
    needle = keyword.lower()
    return [f for f in metainfo(market, transport) if needle in f["name"].lower()]


def fetch(profile: Profile, *, transport=None, now=None,
          page_size: int = PAGE_SIZE, pause: float = PAUSE_SECONDS) -> dict:
    """Fetch one snapshot. `transport(url, body) -> dict` is injectable for tests.

    Pages at `page_size` with a pause between requests — the endpoint publishes
    no rate limit, so the client is the only thing keeping this polite.
    """
    if profile.market not in MARKETS:
        raise ValueError(f"market not allowlisted: {profile.market!r}")
    transport = transport or _post
    url = SCANNER_URL.format(market=profile.market)
    stamp = now or datetime.now(timezone.utc)

    rows, total = [], 0
    start = 0
    while start < profile.max_rows:
        end = min(start + page_size, profile.max_rows)
        page = transport(url, profile.payload(start, end))
        total = page.get("totalCount", 0)
        batch = page.get("data") or []
        rows.extend({"symbol": r["s"], "values": r["d"]} for r in batch)
        if len(batch) < end - start or len(rows) >= total:
            break
        start = end
        if pause:
            time.sleep(pause)

    empty = empty_columns(profile.columns, rows)
    if profile.sort_by and profile.sort_by in empty:
        raise DeadSortColumn(
            f"{profile.name}: sort column {profile.sort_by!r} is empty for every "
            f"row on {profile.market}; the recorded order, and therefore any "
            f"truncation, would be arbitrary"
        )

    return {
        "schema": 1,
        "profile": profile.name,
        "market": profile.market,
        "as_of": stamp.date().isoformat(),
        "fetched_at": stamp.isoformat(),
        "source": url,
        "columns": list(profile.columns),
        "filters": [dict(f) for f in profile.filters],
        "symbolset": list(profile.symbolset),
        "sort": {"by": profile.sort_by, "order": profile.sort_order},
        "note": profile.note,
        # Columns that came back empty for every row. Recorded rather than
        # dropped: a field that goes dark upstream should be visible in the
        # archive, not silently absent from it.
        "empty_columns": empty,
        "total_count": total,
        "row_count": len(rows),
        "truncated": len(rows) < total,
        "rows": rows,
    }


def snapshot_path(profile_name: str, as_of: str, root: str = None) -> str:
    root = root or SNAPSHOT_DIR
    return os.path.join(root, profile_name, f"{as_of}.json")


def save(snapshot: dict, root: str = None) -> str:
    """Write a snapshot append-only. Refuses to overwrite an existing date.

    Immutability is the whole point: a universe file that can be rewritten
    later is not evidence of what the market looked like on that date.
    """
    path = snapshot_path(snapshot["profile"], snapshot["as_of"], root)
    if os.path.exists(path):
        raise FileExistsError(f"snapshot already recorded, refusing to overwrite: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=1, sort_keys=False)
    os.replace(tmp, path)
    return path


def snapshot_dates(profile_name: str, root: str = None) -> list:
    """Every recorded date for a profile, oldest first."""
    directory = os.path.join(root or SNAPSHOT_DIR, profile_name)
    if not os.path.isdir(directory):
        return []
    return sorted(f[:-5] for f in os.listdir(directory) if f.endswith(".json"))


def load_as_of(profile_name: str, as_of: str, root: str = None) -> dict:
    """The newest snapshot recorded **on or before** `as_of` (YYYY-MM-DD).

    Raises `NoPointInTimeUniverse` when none exists. That is the honest answer
    for any backtest starting before this archive did.
    """
    dates = [d for d in snapshot_dates(profile_name, root) if d <= as_of]
    if not dates:
        raise NoPointInTimeUniverse(
            f"no {profile_name} snapshot on or before {as_of}; "
            f"recorded dates: {snapshot_dates(profile_name, root) or 'none'}"
        )
    with open(snapshot_path(profile_name, dates[-1], root), encoding="utf-8") as handle:
        return json.load(handle)


def to_records(snapshot: dict) -> list:
    """Rows as dicts keyed by column name, with the symbol attached."""
    columns = snapshot["columns"]
    return [dict(zip(columns, row["values"]), symbol=row["symbol"])
            for row in snapshot["rows"]]


def symbols_as_of(profile_name: str, as_of: str, root: str = None,
                  limit: int = None) -> list:
    """Ticker list for the universe as it stood on or before `as_of`."""
    snapshot = load_as_of(profile_name, as_of, root)
    symbols = [row["symbol"] for row in snapshot["rows"]]
    return symbols[:limit] if limit else symbols


def record(profile: Profile, *, dry_run: bool = False, now=None) -> tuple:
    """Record one profile for today. Returns `(status, message)`.

    `status` is "recorded", "skipped" (today is already in the archive) or
    "failed". Nothing here raises: the daily task must be able to report a bad
    profile without abandoning the good ones.
    """
    today = (now or datetime.now(timezone.utc)).date().isoformat()
    if not dry_run and os.path.exists(snapshot_path(profile.name, today)):
        # Checked before the fetch, not after: a re-run should not spend a
        # request only to refuse the write.
        return "skipped", f"{today} already recorded"
    try:
        snapshot = fetch(profile, now=now)
    except Exception as error:                       # noqa: BLE001 - reported, not swallowed
        return "failed", f"{type(error).__name__}: {error}"

    detail = (f"{snapshot['row_count']} of {snapshot['total_count']} rows"
              + (" [TRUNCATED]" if snapshot["truncated"] else "")
              + (f" [empty: {','.join(snapshot['empty_columns'])}]"
                 if snapshot["empty_columns"] else ""))
    if dry_run:
        return "recorded", detail + " (dry run, not written)"
    try:
        save(snapshot)
    except Exception as error:                       # noqa: BLE001
        return "failed", f"{type(error).__name__}: {error}"
    return "recorded", detail


def record_all(dry_run: bool = False, now=None) -> dict:
    """Record every profile. Missing one profile must not cost us the others."""
    return {name: record(profile, dry_run=dry_run, now=now)
            for name, profile in sorted(PROFILES.items())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument("--all", action="store_true",
                        help="record every profile; exit 1 if any failed")
    parser.add_argument("--list", action="store_true", help="show profiles and recorded dates")
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    parser.add_argument("--fields", metavar="KEYWORD",
                        help="search the market's field catalogue (discovery aid; incomplete)")
    parser.add_argument("--market", choices=MARKETS, default="thailand",
                        help="market for --fields")
    args = parser.parse_args(argv)

    if args.fields:
        hits = search_fields(args.market, args.fields)
        print(f"{len(hits)} field(s) matching {args.fields!r} on {args.market} "
              f"(catalogue is incomplete; absence does not mean unavailable)")
        for entry in hits[:60]:
            print(f"  {entry['name']:<48} {entry['type']}")
        return 0

    if args.all:
        stamp = datetime.now(timezone.utc)
        results = record_all(dry_run=args.dry_run, now=stamp)
        for name, (status, message) in results.items():
            print(f"[{status:<8}] {name:<20} {message}")
        failed = [n for n, (status, _) in results.items() if status == "failed"]
        recorded = sum(1 for status, _ in results.values() if status == "recorded")
        print(f"{stamp.date().isoformat()}: {recorded} recorded, "
              f"{len(results) - recorded - len(failed)} skipped, {len(failed)} failed")
        return 1 if failed else 0

    if args.list or not args.profile:
        for name, profile in sorted(PROFILES.items()):
            dates = snapshot_dates(name)
            # ASCII only: the Windows console here is cp874 and dies on arrows.
            span = f"{dates[0]}..{dates[-1]} ({len(dates)})" if dates else "no snapshots yet"
            print(f"{name:<20} {profile.market:<10} {span}")
            print(f"{'':<20} {profile.note}")
        return 0

    status, message = record(PROFILES[args.profile], dry_run=args.dry_run)
    print(f"[{status:<8}] {args.profile:<20} {message}")
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
