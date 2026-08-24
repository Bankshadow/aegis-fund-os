import tempfile
import unittest
from pathlib import Path

from agent.lanes import (
    APPROVAL_ACTIONS,
    FORBIDDEN_ACTIONS,
    LANES_ARE_SECURITY_BOUNDARIES,
    NATIVE_STABLE,
    SOURCE_URL,
    Autonomy,
    Disposition,
    activate,
    allowed_roster,
    assert_autonomy,
    claim_done,
    get_lane,
    permit_action,
    require_vault,
    roster,
)


class GrokBotLaneFiltrationTests(unittest.TestCase):
    def test_source_is_the_exm7777_article(self):
        self.assertIn("2091905664704745583", SOURCE_URL)
        self.assertIn("EXM7777", SOURCE_URL)

    def test_lanes_are_not_security_boundaries(self):
        self.assertFalse(LANES_ARE_SECURITY_BOUNDARIES)

    def test_native_keep_lanes_are_already_stable(self):
        for lane_id in NATIVE_STABLE:
            lane = get_lane(lane_id)
            self.assertEqual(lane.disposition, Disposition.KEEP)
            self.assertFalse(lane.money)

    def test_article_money_workflows_are_rejected(self):
        for lane_id in (
            "ugc_higgsfield",
            "email_outbound",
            "linkedin_campaigns",
            "paid_media",
            "ghostwriting",
            "seo_aeo",
            "video_clipping",
        ):
            self.assertEqual(get_lane(lane_id).disposition, Disposition.REJECT)
            with self.assertRaisesRegex(PermissionError, "rejected"):
                activate(lane_id)

    def test_adapt_lanes_are_read_or_review_only(self):
        for lane in allowed_roster():
            if lane.disposition is Disposition.ADAPT:
                self.assertIn(
                    lane.max_autonomy,
                    (Autonomy.READ_PREPARE, Autonomy.HUMAN_REVIEW),
                )
                self.assertFalse(lane.money)

    def test_activate_allows_one_specialist_on_native_set(self):
        lane = activate("x_research", active=NATIVE_STABLE)
        self.assertEqual(lane.lane_id, "x_research")

    def test_activate_blocks_a_second_specialist(self):
        with self.assertRaisesRegex(PermissionError, "one specialist"):
            activate("social_drafts", active=(*NATIVE_STABLE, "x_research"))

    def test_unknown_lane_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown lane"):
            get_lane("meta_ads_intern")

    def test_constitution_forbids_money_even_when_approved(self):
        for action in (
            "place_order",
            "transfer",
            "withdraw",
            "publish_ad",
            "reallocate_budget",
            "send_live_email",
        ):
            self.assertIn(action, FORBIDDEN_ACTIONS)
            with self.assertRaisesRegex(PermissionError, "constitution forbids"):
                permit_action(action, allow=True, require_approval=True, approved=True)

    def test_approval_wins_over_allow(self):
        self.assertIn("publish_social", APPROVAL_ACTIONS)
        with self.assertRaisesRegex(PermissionError, "approval required"):
            permit_action("publish_social", allow=True, approved=False)
        permit_action("publish_social", allow=True, approved=True)

    def test_explicit_approval_rule_beats_matching_allow(self):
        with self.assertRaisesRegex(PermissionError, "approval required"):
            permit_action(
                "file_vault_note",
                allow=True,
                require_approval=True,
                approved=False,
            )
        permit_action(
            "file_vault_note",
            allow=True,
            require_approval=True,
            approved=True,
        )

    def test_denied_action_without_approval_rule_stays_denied(self):
        with self.assertRaisesRegex(PermissionError, "not allowed"):
            permit_action("scratch_note", allow=False)

    def test_claim_done_rejects_self_report(self):
        self.assertFalse(claim_done(gate_ok=False, self_report_only=True))
        self.assertFalse(claim_done(gate_ok=False, declared_check_ok=False))
        self.assertTrue(claim_done(gate_ok=True))
        self.assertTrue(claim_done(gate_ok=False, declared_check_ok=True))

    def test_adapt_lane_cannot_jump_to_routine(self):
        with self.assertRaisesRegex(PermissionError, "max autonomy"):
            assert_autonomy("x_research", Autonomy.ROUTINE)
        assert_autonomy("x_research", Autonomy.READ_PREPARE)

    def test_roster_covers_article_plus_native(self):
        ids = {lane.lane_id for lane in roster()}
        self.assertTrue(NATIVE_STABLE.issubset(ids))
        self.assertEqual(len(ids), len(roster()))

    def test_vault_is_required_source_of_truth(self):
        require_vault()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                require_vault(Path(tmp))

    def test_offer_is_education_not_live(self):
        offer = Path("docs/vault/offer.md").read_text(encoding="utf-8").lower()
        self.assertIn("education", offer)
        self.assertIn("not a live trading bot", offer)
        self.assertIn("not live-trading ready", offer)

    def test_refuse_repeats_live_order_ban(self):
        refuse = Path("docs/vault/refuse.md").read_text(encoding="utf-8").lower()
        self.assertIn("never send live orders", refuse)
        self.assertIn("swarm", refuse)
        self.assertIn("money moves", refuse)


if __name__ == "__main__":
    unittest.main()
