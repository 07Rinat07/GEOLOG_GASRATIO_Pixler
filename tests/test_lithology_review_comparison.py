"""Regression contract for comparing unverified archival lithology records."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from geoworkbench.services.lithology_review_comparison import (
    compare_lithology_review_records,
)
from geoworkbench.services.lithology_review_reader import load_lithology_review
from test_lithology_review_history import _history_files


def test_comparison_is_explicit_immutable_and_project_independent(tmp_path):
    session, first_file, second_file = _history_files(tmp_path)
    session.dirty = False
    before = repr(session.project)
    first = load_lithology_review(first_file)
    second = load_lithology_review(second_file)

    result = compare_lithology_review_records(first, second)
    assert result.first is first and result.second is second
    assert [(item.field_name, item.first_value, item.second_value)
            for item in result.differences] == [("mapping_id", "review-1", "review-2")]
    with pytest.raises(FrozenInstanceError):
        result.differences[0].first_value = "tampered"
    assert not session.dirty and repr(session.project) == before


def test_all_recorded_changes_are_visible_without_geological_inference(tmp_path):
    _session, first_file, second_file = _history_files(tmp_path)
    payload = json.loads(second_file.read_text(encoding="utf-8"))
    mapping = payload["mapping"]
    source = mapping["source"]
    mapping.update(
        mapping_id="changed", reviewer="<b>Unverified</b>",
        applicability_reference="Different evidence",
        rock_family="carbonate", quality="suspect",
    )
    source.update(lithotype_id="other", top_md_m=20, bottom_md_m=25,
                  source_sha256="a" * 64, axis_sha256="b" * 64)
    second_file.write_text(json.dumps(payload), encoding="utf-8")
    # The archive loader also checks the numeric and axis contract.
    first = load_lithology_review(first_file)
    second = load_lithology_review(second_file)
    result = compare_lithology_review_records(first, second)
    assert {change.field_name for change in result.differences} == {
        "mapping_id", "reviewer", "applicability_reference", "rock_family", "quality",
        "lithotype_id", "top_md_m", "bottom_md_m", "source_sha256", "axis_sha256",
    }
    assert next(item for item in result.differences
                if item.field_name == "reviewer").second_value == "<b>Unverified</b>"


def test_matching_assertions_do_not_imply_an_approved_revision(tmp_path):
    _session, first_file, _second_file = _history_files(tmp_path)
    record = load_lithology_review(first_file)
    other_time = replace(record, recorded_at_utc="2026-10-22T20:00:00Z")
    assert compare_lithology_review_records(record, other_time).differences == ()
    assert compare_lithology_review_records(record, record).differences == ()


@pytest.mark.parametrize("field", [
    "project_id", "well_id", "dataset_id", "depth_axis_id", "interval_id",
])
def test_comparison_rejects_mixed_source_scopes(tmp_path, field):
    _session, first_file, _second_file = _history_files(tmp_path)
    first = load_lithology_review(first_file)
    if field == "project_id":
        second = replace(first, project_id="other")
    else:
        second = replace(first, source=replace(first.source, **{field: "other"}))
    with pytest.raises(ValueError, match="one project"):
        compare_lithology_review_records(first, second)


def test_comparison_requires_two_loaded_archival_records(tmp_path):
    _session, first_file, _second_file = _history_files(tmp_path)
    record = load_lithology_review(first_file)
    with pytest.raises(TypeError, match="Two archival"):
        compare_lithology_review_records(record, object())  # type: ignore[arg-type]
