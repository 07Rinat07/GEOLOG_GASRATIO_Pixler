"""Read detached review records without activating or trusting their assertions."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
import json
from pathlib import Path
import re
from typing import Any

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_gti_lithology_screening import (
    LithologyObservation, ObservationQuality, RockFamily, review_gis_gti_lithology_intervals,
)
from geoworkbench.services.lithology_source_mapping import LithologySource, review_lithology_source


MAX_REVIEW_BYTES = 1_048_576


class ReviewSourceStatus(StrEnum):
    MATCHING = "matching"
    DIFFERENT = "different"
    UNAVAILABLE = "unavailable"
    OTHER_PROJECT = "other_project"


@dataclass(frozen=True, slots=True)
class SavedLithologyReview:
    project_id: str
    recorded_at_utc: str
    source: LithologySource
    mapping_id: str
    reviewer: str
    applicability_reference: str
    rock_family: RockFamily
    quality: ObservationQuality


def load_lithology_review(path: str | Path) -> SavedLithologyReview:
    """Validate schema v1 and return archival data, never an active mapping."""
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_REVIEW_BYTES + 1)
    if len(content) > MAX_REVIEW_BYTES:
        raise ValueError("Review record exceeds the supported size")
    try:
        payload = json.loads(
            content.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid review JSON") from exc
    root = _object(payload, {
        "schema_version", "artifact_kind", "review_status", "recorded_at_utc",
        "project_id", "mapping",
    })
    if (type(root["schema_version"]) is not int or root["schema_version"] != 1
            or root["artifact_kind"] != "lithology_mapping_review"
            or root["review_status"] != "operator_review_not_geological_approval"):
        raise ValueError("Unsupported review record schema or status")
    recorded = _text(root["recorded_at_utc"])
    instant = datetime.fromisoformat(recorded)
    if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
        raise ValueError("Review recording time must include UTC")
    mapping = _object(root["mapping"], {
        "source", "mapping_id", "reviewer", "applicability_reference", "rock_family", "quality",
    })
    raw_source = _object(mapping["source"], {field.name for field in fields(LithologySource)})
    for name in ("well_id", "dataset_id", "depth_axis_id", "interval_id", "lithotype_id"):
        _text(raw_source[name])
    for name in ("source_sha256", "axis_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", _text(raw_source[name])):
            raise ValueError("Invalid source fingerprint")
    family = RockFamily(_text(mapping["rock_family"]))
    quality = ObservationQuality(_text(mapping["quality"]))
    source = LithologySource(**raw_source)
    observation = LithologyObservation(
        source.interval_id, source.depth_axis_id, source.top_md_m, source.bottom_md_m,
        family, quality,
    )
    # Reuse the strict numeric/axis contract; do not normalize reversed bounds.
    review_gis_gti_lithology_intervals(
        top_md_m=source.top_md_m, bottom_md_m=source.bottom_md_m,
        depth_axis_id=source.depth_axis_id, observations=(), lithology=(observation,),
    )
    return SavedLithologyReview(
        _text(root["project_id"]), recorded, source, _text(mapping["mapping_id"]),
        _text(mapping["reviewer"]), _text(mapping["applicability_reference"]), family, quality,
    )


def compare_review_source(
    session: ProjectSession, record: SavedLithologyReview,
) -> ReviewSourceStatus:
    """Compare only current source identity; matching is not authentication."""
    if record.project_id != session.project.project_id:
        return ReviewSourceStatus.OTHER_PROJECT
    try:
        current = review_lithology_source(session, interval_id=record.source.interval_id)
    except (ValueError, TypeError, OverflowError):
        return ReviewSourceStatus.UNAVAILABLE
    return ReviewSourceStatus.MATCHING if current == record.source else ReviewSourceStatus.DIFFERENT


def _object(value: Any, names: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("Unexpected review record fields")
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Review record requires explicit text")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate review record key")
        result[name] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON values are not supported")
