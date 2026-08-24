"""Filtrate EXM7777's Grok Bot playbook onto this repo.

Source: https://x.com/EXM7777/status/2091905664704745583
(Machina, 2026-08-24, "How to make money with Grok Bot")

Adopt: one job per lane, vault over memory, read-and-prepare first,
approval wins over allow, verify before claiming done, expand one
specialist at a time.

Reject: a 10-bot revenue swarm, sponsored UGC/Higgsfield, outbound
and paid-media money moves, and any live-order path. This file is
not a BUILD 7 fan-out install — ROUTING.md triggers still apply.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://x.com/EXM7777/status/2091905664704745583"

VAULT_RELATIVE = (
    "docs/vault/README.md",
    "docs/vault/offer.md",
    "docs/vault/icp.md",
    "docs/vault/refuse.md",
    "docs/vault/rulings.md",
    "docs/vault/voice.md",
)


class Disposition(str, Enum):
    KEEP = "keep"
    ADAPT = "adapt"
    REJECT = "reject"


class Autonomy(str, Enum):
    READ_PREPARE = "read_prepare"
    HUMAN_REVIEW = "human_review"
    APPROVED_ACTION = "approved_action"
    ROUTINE = "routine"


# Native lanes already shipping. Specialists sit outside this set.
NATIVE_STABLE = frozenset(
    {"education_evidence", "research_loop", "runtime_watchdog"}
)

# Constitution: these never run here, even with an approval checkbox.
FORBIDDEN_ACTIONS = frozenset(
    {
        "place_order",
        "cancel_order",
        "transfer",
        "withdraw",
        "send_live_email",
        "publish_ad",
        "reallocate_budget",
        "charge_card",
        "submit_payment",
    }
)

# Human click required. Approval beats a matching allow rule.
APPROVAL_ACTIONS = frozenset(
    {
        "publish_social",
        "send_draft_queue",
        "open_specialist",
    }
)


@dataclass(frozen=True)
class Lane:
    lane_id: str
    name: str
    source: str
    disposition: Disposition
    max_autonomy: Autonomy
    money: bool
    reason: str


LANES: tuple[Lane, ...] = (
    Lane(
        "education_evidence",
        "Walk-Forward Lab evidence",
        "native",
        Disposition.KEEP,
        Autonomy.ROUTINE,
        False,
        "Already shipping: precomputed OOS views. Read-only research/education.",
    ),
    Lane(
        "research_loop",
        "Loop Engineering research",
        "native",
        Disposition.KEEP,
        Autonomy.HUMAN_REVIEW,
        False,
        "Existing experiment contract / ValidationGate / paper-review ledger.",
    ),
    Lane(
        "runtime_watchdog",
        "Read-only runtime watchdog",
        "native",
        Disposition.KEEP,
        Autonomy.ROUTINE,
        False,
        "Existing token-gated status poll. No cron/order/cancel/transfer path.",
    ),
    Lane(
        "x_research",
        "Daily X / niche research",
        "daily X research bot",
        Disposition.ADAPT,
        Autonomy.READ_PREPARE,
        False,
        "Read-only. File markdown in the vault. Never auto-post.",
    ),
    Lane(
        "social_drafts",
        "Education social drafts",
        "social content",
        Disposition.ADAPT,
        Autonomy.HUMAN_REVIEW,
        False,
        "Draft from walk-forward evidence. Human publishes. No invented metrics.",
    ),
    Lane(
        "competitor_watch",
        "Grid-education claim watch",
        "competitor intelligence",
        Disposition.ADAPT,
        Autonomy.READ_PREPARE,
        False,
        "Read-only. Compare public grid-bot claims to VALIDATION_LOG. No pricing moves.",
    ),
    Lane(
        "chief_of_staff",
        "Chief of staff readout",
        "monitor the team",
        Disposition.ADAPT,
        Autonomy.READ_PREPARE,
        False,
        "Scan STATE / vault / gate. Deliver a sourced readout. Never a placement middleman.",
    ),
    Lane(
        "ugc_higgsfield",
        "AI UGC ads (Higgsfield)",
        "AI UGC with Higgsfield",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        True,
        "Sponsored ad-production lane. Not this product. No ads account.",
    ),
    Lane(
        "seo_aeo",
        "SEO / AEO auditor",
        "SEO / AEO auditor",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        False,
        "Speculative unused surface. Slice 5 is student feedback, not a guessed auditor.",
    ),
    Lane(
        "email_outbound",
        "Email outbound",
        "email outbound",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        True,
        "No Smartlead / CRM path. Sending stays human even if later adapted.",
    ),
    Lane(
        "linkedin_campaigns",
        "LinkedIn campaigns",
        "LinkedIn campaigns",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        True,
        "Browser ads/forms/UTM ops. Not this product.",
    ),
    Lane(
        "paid_media",
        "Paid media reallocation",
        "paid media reallocation",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        True,
        "Money move. Constitution: never automate capital on day one — or here at all.",
    ),
    Lane(
        "video_clipping",
        "Clipping and long-form video",
        "clipping and long-form video",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        False,
        "Unused surface until students ask. Do not build a clip factory speculatively.",
    ),
    Lane(
        "ghostwriting",
        "Ghostwriting for clients",
        "ghostwriting for clients",
        Disposition.REJECT,
        Autonomy.READ_PREPARE,
        False,
        "This repo teaches from its own evidence ledger. It is not a client ghostwriting shop.",
    ),
)

_BY_ID = {lane.lane_id: lane for lane in LANES}

# Lanes are separate work surfaces on one shared computer, not security domains.
LANES_ARE_SECURITY_BOUNDARIES = False


def roster() -> tuple[Lane, ...]:
    return LANES


def get_lane(lane_id: str) -> Lane:
    try:
        return _BY_ID[lane_id]
    except KeyError as exc:
        raise ValueError(f"unknown lane: {lane_id}") from exc


def allowed_roster() -> tuple[Lane, ...]:
    return tuple(
        lane
        for lane in LANES
        if lane.disposition is not Disposition.REJECT
    )


def vault_paths(root: Path | None = None) -> tuple[Path, ...]:
    base = ROOT if root is None else root
    return tuple(base / rel for rel in VAULT_RELATIVE)


def require_vault(root: Path | None = None) -> None:
    missing = [str(path) for path in vault_paths(root) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "vault is the source of truth; missing: " + ", ".join(missing)
        )


def activate(
    lane_id: str,
    *,
    active: Iterable[str] = NATIVE_STABLE,
) -> Lane:
    """Open a KEEP/ADAPT lane. One new specialist at a time.

    Native stable lanes may already be running. A REJECT lane never opens.
    A second specialist while another un-natived lane is active fails closed.
    """
    lane = get_lane(lane_id)
    if lane.disposition is Disposition.REJECT:
        raise PermissionError(f"lane {lane_id} rejected: {lane.reason}")
    active_ids = tuple(active)
    if lane_id in active_ids:
        return lane
    specialists = [item for item in active_ids if item not in NATIVE_STABLE]
    if specialists:
        raise PermissionError(
            "one specialist at a time; stabilize "
            f"{specialists[0]} before opening {lane_id}"
        )
    return lane


def permit_action(
    action: str,
    *,
    allow: bool = True,
    require_approval: bool = False,
    approved: bool = False,
) -> None:
    """Fail closed before the action. Approval does not reverse completed work.

    When an allow rule and an approval rule both match, approval wins:
    the action still waits. Constitution forbids money/order paths even
    if approved.
    """
    if action in FORBIDDEN_ACTIONS:
        raise PermissionError(f"constitution forbids {action}")
    needs_approval = require_approval or action in APPROVAL_ACTIONS
    if needs_approval:
        if not approved:
            raise PermissionError(f"approval required for {action}")
        return
    if not allow:
        raise PermissionError(f"{action} is not allowed")


def claim_done(
    *,
    gate_ok: bool,
    declared_check_ok: bool = False,
    self_report_only: bool = False,
) -> bool:
    """A bot that says done without checking is worse than no bot."""
    if self_report_only:
        return False
    return bool(gate_ok or declared_check_ok)


def autonomy_rank(level: Autonomy) -> int:
    return list(Autonomy).index(level)


def assert_autonomy(lane_id: str, requested: Autonomy) -> None:
    lane = get_lane(lane_id)
    if lane.disposition is Disposition.REJECT:
        raise PermissionError(f"lane {lane_id} rejected: {lane.reason}")
    if autonomy_rank(requested) > autonomy_rank(lane.max_autonomy):
        raise PermissionError(
            f"{lane_id} max autonomy is {lane.max_autonomy.value}, "
            f"not {requested.value}"
        )
    if lane.money and requested is Autonomy.ROUTINE:
        raise PermissionError("money moves are never a routine")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the filtrated Grok Bot lane roster (no model calls)."
    )
    parser.add_argument(
        "--allowed",
        action="store_true",
        help="Only KEEP/ADAPT lanes",
    )
    args = parser.parse_args(argv)
    rows = allowed_roster() if args.allowed else roster()
    print(f"source: {SOURCE_URL}")
    print("policy: vault > memory; one job per lane; BUILD 7 still deferred")
    print(
        f"{'lane_id':22} {'disp':7} {'max_auto':16} {'money':5} name"
    )
    for lane in rows:
        print(
            f"{lane.lane_id:22} {lane.disposition.value:7} "
            f"{lane.max_autonomy.value:16} {str(lane.money):5} {lane.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
