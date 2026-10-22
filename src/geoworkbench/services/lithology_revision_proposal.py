"""Explicit, non-activating proposals between two archived lithology reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from geoworkbench.services.lithology_review_comparison import (
    LithologyReviewComparison,
    compare_lithology_review_records,
)
from geoworkbench.services.lithology_review_reader import SavedLithologyReview


MAX_PROPOSAL_ID_LENGTH = 128
MAX_PROPOSAL_TEXT_LENGTH = 4096


@dataclass(frozen=True, slots=True)
class LithologyRevisionProposal:
    """An operator's suggested change, not an authoritative revision or signature."""

    proposal_id: str
    proposed_by: str
    justification: str
    comparison: LithologyReviewComparison

    @property
    def review_state(self) -> Literal["proposal_not_geological_approval"]:
        """This data-only object can never express geological approval."""
        return "proposal_not_geological_approval"


def prepare_lithology_revision_proposal(
    baseline: SavedLithologyReview,
    candidate: SavedLithologyReview,
    *,
    proposal_id: str,
    proposed_by: str,
    justification: str,
) -> LithologyRevisionProposal:
    """Prepare an explicit proposal without reading or modifying any project.

    The caller chooses which archival record is baseline and which is candidate.
    Archived timestamps are not treated as proof of revision order. The proposal
    is not persisted, activated, approved or linked to a verified identity.
    Separate geological sign-off and source-freshness checks remain necessary.
    """
    _required_text(proposal_id, "proposal_id", MAX_PROPOSAL_ID_LENGTH)
    _required_text(proposed_by, "proposed_by", MAX_PROPOSAL_ID_LENGTH)
    _required_text(justification, "justification", MAX_PROPOSAL_TEXT_LENGTH)
    comparison = compare_lithology_review_records(baseline, candidate)
    if not comparison.differences:
        raise ValueError("A revision proposal requires a changed archival assertion")
    return LithologyRevisionProposal(
        proposal_id=proposal_id,
        proposed_by=proposed_by,
        justification=justification,
        comparison=comparison,
    )


def _required_text(value: str, field: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} requires non-empty text of at most {maximum} characters")
