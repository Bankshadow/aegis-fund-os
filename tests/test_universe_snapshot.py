"""Invariants for point-in-time universe snapshots.

The module's only real promise is that research cannot see a universe recorded
after the bars it selects. These tests pin that promise, plus the two things
that would silently corrupt the archive: an overwritten date and a partial
write. Nothing here touches the network.
"""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from dynamic_grid import universe_snapshot as us


def fake_transport(total, rows_by_page):
    """Record every payload and reply with canned pages."""
    seen = []

    def transport(url, body):
        seen.append((url, body))
        start, end = body["range"]
        page = [{"s": f"X:{i}", "d": [f"n{i}", float(i)]}
                for i in range(start, min(end, total))]
        return {"totalCount": total, "data": page}

    transport.seen = seen
    transport.rows_by_page = rows_by_page
    return transport


PROFILE = us.Profile(
    name="test-profile",
    market="thailand",
    columns=("name", "close"),
    filters=({"left": "type", "operation": "equal", "right": "stock"},),
    sort_by="close",
    max_rows=1000,
)


class FetchTests(unittest.TestCase):

    def test_market_must_be_allowlisted(self):
        rogue = us.Profile(name="x", market="mars", columns=("name",))
        with self.assertRaises(ValueError):
            us.fetch(rogue, transport=fake_transport(1, None))

    def test_paging_stops_once_every_row_is_collected(self):
        transport = fake_transport(700, None)
        snapshot = us.fetch(PROFILE, transport=transport, page_size=500, pause=0)
        self.assertEqual(snapshot["row_count"], 700)
        self.assertEqual(snapshot["total_count"], 700)
        self.assertFalse(snapshot["truncated"])
        self.assertEqual([b["range"] for _, b in transport.seen], [[0, 500], [500, 1000]])

    def test_max_rows_caps_the_fetch_and_is_reported_as_truncated(self):
        capped = us.Profile(name="c", market="thailand", columns=("name",), max_rows=100)
        snapshot = us.fetch(capped, transport=fake_transport(5000, None), pause=0)
        self.assertEqual(snapshot["row_count"], 100)
        self.assertEqual(snapshot["total_count"], 5000)
        self.assertTrue(snapshot["truncated"])

    def test_the_filters_and_sort_travel_with_the_snapshot(self):
        # A universe rule is only auditable later if it is stored next to the
        # timestamp — otherwise nobody can tell a point-in-time liquidity screen
        # from one applied with hindsight.
        snapshot = us.fetch(PROFILE, transport=fake_transport(3, None), pause=0)
        self.assertEqual(snapshot["filters"], [dict(PROFILE.filters[0])])
        self.assertEqual(snapshot["sort"], {"by": "close", "order": "desc"})
        self.assertEqual(snapshot["columns"], ["name", "close"])

    def test_the_payload_sent_matches_the_profile(self):
        transport = fake_transport(3, None)
        us.fetch(PROFILE, transport=transport, pause=0)
        _, body = transport.seen[0]
        self.assertEqual(body["filter"], [dict(PROFILE.filters[0])])
        self.assertEqual(body["sort"], {"sortBy": "close", "sortOrder": "desc"})
        self.assertEqual(body["columns"], ["name", "close"])


class SymbolsetTests(unittest.TestCase):
    """Index membership is an exogenous universe; we request it, we don't edit it."""

    def test_symbolset_is_sent_and_recorded(self):
        profile = us.Profile(name="idx", market="thailand", columns=("name", "close"),
                             symbolset=("SYML:SET;SET50",))
        transport = fake_transport(50, None)
        snapshot = us.fetch(profile, transport=transport, pause=0)
        _, body = transport.seen[0]
        self.assertEqual(body["symbols"], {"symbolset": ["SYML:SET;SET50"]})
        self.assertEqual(snapshot["symbolset"], ["SYML:SET;SET50"])

    def test_a_profile_without_a_symbolset_sends_no_symbols_key(self):
        transport = fake_transport(3, None)
        us.fetch(PROFILE, transport=transport, pause=0)
        self.assertNotIn("symbols", transport.seen[0][1])

    def test_index_profiles_add_no_filters_of_their_own(self):
        # Membership IS the definition. A filter of ours on top would be us
        # quietly editing SET's universe, which is the thing that makes an index
        # immune to the E33 objection in the first place.
        for name in us.INDEX_UNIVERSES:
            profile = us.PROFILES[name]
            self.assertEqual(profile.filters, (), f"{name} must not filter membership")
            self.assertTrue(profile.symbolset, f"{name} must be defined by symbolset")


class DeadColumnTests(unittest.TestCase):

    def transport_with_nulls(self, null_index, total=4):
        def transport(url, body):
            start, end = body["range"]
            rows = []
            for i in range(start, min(end, total)):
                values = [f"n{i}", float(i)]
                values[null_index] = None
                rows.append({"s": f"X:{i}", "d": values})
            return {"totalCount": total, "data": rows}
        return transport

    def test_an_all_empty_column_is_recorded_not_hidden(self):
        profile = us.Profile(name="p", market="thailand", columns=("name", "close"))
        snapshot = us.fetch(profile, transport=self.transport_with_nulls(1), pause=0)
        self.assertEqual(snapshot["empty_columns"], ["close"])

    def test_sorting_on_a_dead_column_refuses_to_produce_a_snapshot(self):
        # Measured live: `Value.Traded` is empty on `crypto` and populated on
        # `thailand`, and the endpoint answers 200 for both. Truncating a fetch
        # ordered by the dead one records an arbitrary subset.
        profile = us.Profile(name="p", market="crypto", columns=("name", "close"),
                             sort_by="close")
        with self.assertRaises(us.DeadSortColumn):
            us.fetch(profile, transport=self.transport_with_nulls(1), pause=0)

    def test_a_live_sort_column_passes_even_when_another_column_is_dead(self):
        profile = us.Profile(name="p", market="thailand", columns=("name", "close"),
                             sort_by="name")
        snapshot = us.fetch(profile, transport=self.transport_with_nulls(1), pause=0)
        self.assertEqual(snapshot["empty_columns"], ["close"])

    def test_no_rows_means_no_empty_column_claim(self):
        profile = us.Profile(name="p", market="thailand", columns=("name", "close"),
                             sort_by="close")
        snapshot = us.fetch(profile, transport=fake_transport(0, None), pause=0)
        self.assertEqual(snapshot["empty_columns"], [])
        self.assertEqual(snapshot["row_count"], 0)


class MetainfoTests(unittest.TestCase):

    CATALOGUE = {"fields": [{"n": "close", "t": "price"},
                            {"n": "dividend_yield_recent", "t": "number"},
                            {"n": "market_cap_basic", "t": "fundamental_price"}]}

    def test_metainfo_is_normalised_to_name_and_type(self):
        entries = us.metainfo("thailand", transport=lambda url: self.CATALOGUE)
        self.assertEqual(entries[0], {"name": "close", "type": "price"})

    def test_search_is_case_insensitive_substring(self):
        hits = us.search_fields("thailand", "DIVIDEND", transport=lambda url: self.CATALOGUE)
        self.assertEqual([h["name"] for h in hits], ["dividend_yield_recent"])

    def test_metainfo_respects_the_market_allowlist(self):
        with self.assertRaises(ValueError):
            us.metainfo("mars", transport=lambda url: self.CATALOGUE)

    def test_the_catalogue_is_a_discovery_aid_not_an_allowlist(self):
        # `Value.Traded` is in no market's metainfo yet returns real numbers on
        # `thailand`. Nothing in this module may reject a column for being
        # absent from the catalogue.
        profile = us.Profile(name="p", market="thailand", columns=("Value.Traded",),
                             sort_by="Value.Traded")

        def transport(url, body):
            return {"totalCount": 1, "data": [{"s": "SET:PTT", "d": [5019506515]}]}

        snapshot = us.fetch(profile, transport=transport, pause=0)
        self.assertEqual(snapshot["row_count"], 1)
        self.assertEqual(snapshot["empty_columns"], [])


class ArchiveTests(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def write(self, profile_name, as_of, rows=1):
        snapshot = {
            "schema": 1, "profile": profile_name, "market": "thailand",
            "as_of": as_of, "fetched_at": as_of + "T00:00:00+00:00",
            "columns": ["name", "close"],
            "rows": [{"symbol": f"SET:S{i}", "values": [f"S{i}", 1.0 + i]}
                     for i in range(rows)],
        }
        return us.save(snapshot, root=self.root)

    def test_a_recorded_date_cannot_be_overwritten(self):
        self.write("p", "2026-08-09")
        with self.assertRaises(FileExistsError):
            self.write("p", "2026-08-09", rows=2)

    def test_a_failed_write_leaves_no_partial_file(self):
        # json.dump raises on the unserialisable value; the real path must not
        # exist afterwards, or a half-written universe becomes "evidence".
        bad = {"profile": "p", "as_of": "2026-08-10", "rows": {object()}}
        with self.assertRaises(TypeError):
            us.save(bad, root=self.root)
        self.assertFalse(os.path.exists(us.snapshot_path("p", "2026-08-10", self.root)))

    def test_load_as_of_returns_the_newest_snapshot_not_after_the_date(self):
        self.write("p", "2026-01-01", rows=1)
        self.write("p", "2026-06-01", rows=2)
        self.write("p", "2026-12-01", rows=3)
        self.assertEqual(len(us.load_as_of("p", "2026-08-09", self.root)["rows"]), 2)
        self.assertEqual(len(us.load_as_of("p", "2026-06-01", self.root)["rows"]), 2)
        self.assertEqual(len(us.load_as_of("p", "2026-05-31", self.root)["rows"]), 1)

    def test_a_future_snapshot_is_never_handed_to_a_past_backtest(self):
        # The whole reason this module exists: E31's survivorship residual is
        # exactly "universe drawn from today's listings".
        self.write("p", "2026-08-09")
        with self.assertRaises(us.NoPointInTimeUniverse):
            us.load_as_of("p", "2020-01-01", self.root)

    def test_an_empty_archive_raises_rather_than_returning_nothing_quietly(self):
        with self.assertRaises(us.NoPointInTimeUniverse):
            us.load_as_of("never-recorded", "2026-08-09", self.root)
        self.assertEqual(us.snapshot_dates("never-recorded", self.root), [])

    def test_symbols_as_of_respects_the_same_cutoff(self):
        self.write("p", "2026-01-01", rows=1)
        self.write("p", "2026-06-01", rows=4)
        self.assertEqual(us.symbols_as_of("p", "2026-03-01", self.root), ["SET:S0"])
        self.assertEqual(len(us.symbols_as_of("p", "2026-07-01", self.root)), 4)
        self.assertEqual(len(us.symbols_as_of("p", "2026-07-01", self.root, limit=2)), 2)

    def test_to_records_pairs_columns_with_values(self):
        self.write("p", "2026-06-01", rows=2)
        records = us.to_records(us.load_as_of("p", "2026-06-01", self.root))
        self.assertEqual(records[1], {"name": "S1", "close": 2.0, "symbol": "SET:S1"})


class DailyRunTests(unittest.TestCase):
    """What the scheduled task depends on: partial failure must not lose the rest."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        # Capture the originals BEFORE patching, or the cleanup restores the stub.
        self.addCleanup(setattr, us, "SNAPSHOT_DIR", us.SNAPSHOT_DIR)
        self.addCleanup(setattr, us, "PROFILES", us.PROFILES)
        self.addCleanup(setattr, us, "_post", us._post)
        us.SNAPSHOT_DIR = self.root

    def stub(self, transport, with_bad_profile=False):
        """Install stub profiles and a stub transport, and silence CLI output."""
        good = us.Profile(name="good", market="thailand", columns=("name", "close"))
        bad = us.Profile(name="bad", market="crypto", columns=("name", "close"),
                         sort_by="close")
        us.PROFILES = {"good": good, "bad": bad} if with_bad_profile else {"good": good}
        us._post = transport

    def run_cli(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return us.main(argv)

    def test_a_failing_profile_does_not_cost_us_the_healthy_ones(self):
        # `bad` sorts on a column that comes back dead, so `fetch` raises. The
        # daily task must still record `good` and report the failure.
        def transport(url, body):
            dead = "crypto" in url
            return {"totalCount": 1, "data": [{"s": "X:1", "d": ["n1", None if dead else 1.0]}]}

        self.stub(transport, with_bad_profile=True)
        results = us.record_all()
        self.assertEqual(results["good"][0], "recorded")
        self.assertEqual(results["bad"][0], "failed")
        self.assertIn("DeadSortColumn", results["bad"][1])
        self.assertEqual(len(us.snapshot_dates("good", self.root)), 1)
        self.assertEqual(us.snapshot_dates("bad", self.root), [])

    def test_the_cli_exits_non_zero_when_a_profile_fails(self):
        self.stub(lambda url, body: {"totalCount": 1, "data": [{"s": "X:1", "d": ["n1", None]}]},
                  with_bad_profile=True)
        self.assertEqual(self.run_cli(["--all"]), 1)

    def test_the_cli_exits_zero_when_every_profile_is_recorded(self):
        self.stub(lambda url, body: {"totalCount": 1, "data": [{"s": "X:1", "d": ["n1", 1.0]}]})
        self.assertEqual(self.run_cli(["--all"]), 0)
        self.assertEqual(self.run_cli(["--all"]), 0, "a same-day re-run still succeeds")

    def test_a_second_run_on_the_same_day_skips_without_a_request(self):
        # The task may fire twice (catch-up after a missed 18:00); the archive is
        # append-only, so the re-run must be a no-op that spends nothing.
        calls = []

        def transport(url, body):
            calls.append(url)
            return {"totalCount": 1, "data": [{"s": "X:1", "d": ["n1", 1.0]}]}

        self.stub(transport)
        self.assertEqual(us.record_all()["good"][0], "recorded")
        self.assertEqual(len(calls), 1)
        self.assertEqual(us.record_all()["good"][0], "skipped")
        self.assertEqual(len(calls), 1, "a skipped profile must not hit the network")

    def test_a_network_error_is_reported_not_raised(self):
        def transport(url, body):
            raise OSError("connection reset")

        self.stub(transport)
        status, message = us.record(us.PROFILES["good"])
        self.assertEqual(status, "failed")
        self.assertIn("connection reset", message)
        self.assertEqual(us.snapshot_dates("good", self.root), [])

    def test_earlier_tests_restored_the_real_transport(self):
        # Cheap guard against the patching mistake that leaks a stub into the
        # rest of the suite: by the time this runs, several tests have swapped
        # `_post` out and the cleanup must have put the real one back.
        self.assertEqual(us._post.__name__, "_post")
        self.assertEqual(us._post.__module__, us.__name__)


class ShippedProfileTests(unittest.TestCase):
    """The shipped profiles encode measured findings; a silent edit breaks them."""

    def test_set_profile_excludes_derivative_warrants(self):
        # Unfiltered `thailand` returns 2,250 rows in which warrants inherit the
        # underlying's market cap (NVDA01 outranked DELTA at 179tn THB).
        profile = us.PROFILES["set-stocks"]
        filters = {(f["left"], json.dumps(f["right"])) for f in profile.filters}
        self.assertIn(("type", '"stock"'), filters)
        self.assertIn(("is_primary", "true"), filters)

    def test_crypto_profile_is_spot_only(self):
        # Perpetuals (`.P`) are a different instrument with funding attached;
        # E31 models funding explicitly and must not be fed mixed rows.
        profile = us.PROFILES["binance-spot-usdt"]
        filters = {f["left"]: f["right"] for f in profile.filters}
        self.assertEqual(filters["type"], "spot")
        self.assertEqual(filters["currency"], "USDT")

    def test_every_profile_targets_an_allowlisted_market(self):
        for profile in us.PROFILES.values():
            self.assertIn(profile.market, us.MARKETS)


if __name__ == "__main__":
    unittest.main()
