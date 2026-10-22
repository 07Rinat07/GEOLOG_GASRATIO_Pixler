from dataclasses import FrozenInstanceError
import json

import pytest

from geoworkbench.services.lithology_review_export import export_lithology_review
from geoworkbench.services.lithology_review_reader import (
    MAX_REVIEW_BYTES, ReviewSourceStatus, compare_review_source, load_lithology_review,
)
from test_lithology_source_mapping import _mapping
from test_report_geology_snapshot import _session


def _record(tmp_path):
    session = _session()
    path = tmp_path / "review.json"
    export_lithology_review(session, _mapping(session, reviewer="Геолог"), path)
    return session, path


def test_export_load_and_compare_preserves_archival_provenance_without_activation(tmp_path):
    session, path = _record(tmp_path)
    session.dirty = False
    before = repr(session.project)
    record = load_lithology_review(path)
    assert record.reviewer == "Геолог" and record.mapping_id == "review-1"
    assert record.source == _mapping(session).source
    assert compare_review_source(session, record) is ReviewSourceStatus.MATCHING
    assert repr(session.project) == before and not session.dirty
    with pytest.raises(FrozenInstanceError):
        record.reviewer = "changed"


@pytest.mark.parametrize("change,expected", [
    ("description", ReviewSourceStatus.DIFFERENT),
    ("axis", ReviewSourceStatus.DIFFERENT),
    ("deleted", ReviewSourceStatus.UNAVAILABLE),
    ("unit", ReviewSourceStatus.UNAVAILABLE),
    ("project", ReviewSourceStatus.OTHER_PROJECT),
])
def test_source_status_is_explicit_and_recomputed(tmp_path, change, expected):
    session, path = _record(tmp_path)
    record = load_lithology_review(path)
    if change == "description":
        session.current_well.lithology[0].description = "Changed"
    elif change == "axis":
        session.current_dataset.active_index.values[1] += 0.5
    elif change == "deleted":
        session.current_well.lithology.clear()
    elif change == "unit":
        session.current_dataset.active_index.unit = "ft"
    else:
        session.project.project_id = "other"
    assert compare_review_source(session, record) is expected


@pytest.mark.parametrize("key,value", [
    ("schema_version", True), ("schema_version", 2), ("schema_version", "1"),
    ("artifact_kind", "project"), ("review_status", "approved"),
    ("recorded_at_utc", "2026-10-22T12:00:00"),
    ("recorded_at_utc", "2026-10-22T12:00:00+05:00"),
    ("recorded_at_utc", "invalid"), ("project_id", " "), ("mapping", []),
])
def test_invalid_root_contract_is_rejected(tmp_path, key, value):
    _, path = _record(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[key] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lithology_review(path)


@pytest.mark.parametrize("key,value", [
    ("reviewer", None), ("mapping_id", ""), ("applicability_reference", 4),
    ("rock_family", "guessed"), ("quality", "approved"), ("source", []),
])
def test_invalid_mapping_fields_are_rejected(tmp_path, key, value):
    _, path = _record(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["mapping"][key] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lithology_review(path)


@pytest.mark.parametrize("key,value", [
    ("top_md_m", True), ("top_md_m", -1), ("top_md_m", "1000"),
    ("bottom_md_m", 999), ("bottom_md_m", float("nan")),
    ("axis_sha256", "not-a-hash"), ("source_sha256", "x" * 64),
    ("depth_axis_id", ""), ("well_id", {}),
])
def test_invalid_source_contract_is_rejected(tmp_path, key, value):
    _, path = _record(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["mapping"]["source"][key] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lithology_review(path)


@pytest.mark.parametrize("scope", ["root", "mapping", "source"])
@pytest.mark.parametrize("operation", ["add", "remove"])
def test_unknown_and_missing_fields_are_rejected(tmp_path, scope, operation):
    _, path = _record(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected = payload if scope == "root" else payload["mapping"]
    if scope == "source":
        selected = selected["source"]
    if operation == "add":
        selected["unexpected"] = 1
    else:
        selected.pop(next(iter(selected)))
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lithology_review(path)


@pytest.mark.parametrize("raw", [
    b'{"schema_version":1,"schema_version":1}', b'[]', b'null', b'NaN',
    b'Infinity', b'\xff', b'{invalid}', b'[' * 2000 + b']' * 2000,
])
def test_malformed_and_ambiguous_json_is_rejected(tmp_path, raw):
    path = tmp_path / "review.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        load_lithology_review(path)


def test_size_bound_is_enforced_before_parsing(tmp_path):
    path = tmp_path / "review.json"
    path.write_bytes(b" " * (MAX_REVIEW_BYTES + 1))
    with pytest.raises(ValueError, match="size"):
        load_lithology_review(path)
