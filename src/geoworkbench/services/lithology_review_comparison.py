"""Explicit, read-only comparison of two unverified archival lithology reviews."""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.lithology_review_reader import SavedLithologyReview


@dataclass(frozen=True, slots=True)
class LithologyReviewDifference:
    field_name: str
    first_value: str
    second_value: str


@dataclass(frozen=True, slots=True)
class LithologyReviewComparison:
    """Differences in recorded assertions, not a verified revision or approval."""

    first: SavedLithologyReview
    second: SavedLithologyReview
    differences: tuple[LithologyReviewDifference, ...]


def compare_lithology_review_records(
    first: SavedLithologyReview, second: SavedLithologyReview,
) -> LithologyReviewComparison:
    """Compare two explicitly chosen records within the same archival source scope.

    Source hashes and applicability text are untrusted recorded assertions.
    Timestamp order, equality and matching source identity cannot certify an author,
    a revision chain, geological correctness or approval. No project is accessed.
    """
    if not isinstance(first, SavedLithologyReview) or not isinstance(second, SavedLithologyReview):
        raise TypeError("Two archival review records are required")
    if _scope(first) != _scope(second):
        raise ValueError("Only records of one project, well, dataset, axis and interval may be compared")

    attributes = (
        ("mapping_id", first.mapping_id, second.mapping_id),
        ("reviewer", first.reviewer, second.reviewer),
        ("applicability_reference", first.applicability_reference, second.applicability_reference),
        ("rock_family", first.rock_family.value, second.rock_family.value),
        ("quality", first.quality.value, second.quality.value),
        ("lithotype_id", first.source.lithotype_id, second.source.lithotype_id),
        ("top_md_m", first.source.top_md_m, second.source.top_md_m),
        ("bottom_md_m", first.source.bottom_md_m, second.source.bottom_md_m),
        ("source_sha256", first.source.source_sha256, second.source.source_sha256),
        ("axis_sha256", first.source.axis_sha256, second.source.axis_sha256),
    )
    differences = tuple(
        LithologyReviewDifference(field, str(left), str(right))
        for field, left, right in attributes if left != right
    )
    return LithologyReviewComparison(first, second, differences)


def _scope(record: SavedLithologyReview) -> tuple[str, ...]:
    source = record.source
    return (record.project_id, source.well_id, source.dataset_id,
            source.depth_axis_id, source.interval_id)
