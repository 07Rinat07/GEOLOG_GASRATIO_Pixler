"""Bounded chronological inspection of unverified review records for one source."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.lithology_review_reader import (
    ReviewSourceStatus, SavedLithologyReview, compare_review_source, load_lithology_review,
)


MAX_HISTORY_RECORDS = 16


@dataclass(frozen=True, slots=True)
class LithologyHistoryEntry:
    record: SavedLithologyReview
    source_status: ReviewSourceStatus


def load_lithology_review_history(
    session: ProjectSession, paths: tuple[str | Path, ...],
) -> tuple[LithologyHistoryEntry, ...]:
    """Load all or reject all; time order is not a verified revision lineage.

    Each record retains the v1 reader's 1 MiB limit. Equal recording times keep
    selection order. No latest record is selected, activated or approved.
    """
    if not isinstance(paths, tuple) or not 1 <= len(paths) <= MAX_HISTORY_RECORDS:
        raise ValueError("Choose between one and sixteen review records")
    try:
        selected = tuple(Path(path).resolve(strict=True) for path in paths)
    except RuntimeError as exc:
        raise ValueError("Invalid review path") from exc
    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate review paths are not supported")
    records = tuple(load_lithology_review(path) for path in selected)
    normalized = {
        replace(record, recorded_at_utc=datetime.fromisoformat(record.recorded_at_utc).isoformat())
        for record in records
    }
    if len(normalized) != len(records):
        raise ValueError("Duplicate review records are not supported")
    if len({_source_scope(record) for record in records}) != 1:
        raise ValueError("History requires one project, well, dataset, axis and interval")
    ordered = sorted(records, key=lambda record: datetime.fromisoformat(record.recorded_at_utc))
    return tuple(LithologyHistoryEntry(record, compare_review_source(session, record))
                 for record in ordered)


def _source_scope(record: SavedLithologyReview) -> tuple[str, ...]:
    source = record.source
    return (record.project_id, source.well_id, source.dataset_id,
            source.depth_axis_id, source.interval_id)
