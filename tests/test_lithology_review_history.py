from dataclasses import FrozenInstanceError
import json

import pytest

from geoworkbench.services.lithology_review_export import export_lithology_review
from geoworkbench.services.lithology_review_history import (
    MAX_HISTORY_RECORDS, load_lithology_review_history,
)
from geoworkbench.services.lithology_review_reader import ReviewSourceStatus
from test_lithology_source_mapping import _mapping
from test_report_geology_snapshot import _session


def _history_files(tmp_path):
    session = _session()
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    export_lithology_review(session, _mapping(session), first)
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["recorded_at_utc"] = "2026-10-22T08:00:00+00:00"
    first.write_text(json.dumps(payload), encoding="utf-8")
    payload["recorded_at_utc"] = "2026-10-22T10:00:00Z"
    payload["mapping"]["mapping_id"] = "review-2"
    second.write_text(json.dumps(payload), encoding="utf-8")
    return session, first, second


def test_history_orders_utc_records_without_mutation_or_activation(tmp_path):
    session, first, second = _history_files(tmp_path)
    session.dirty = False
    before = repr(session.project)
    entries = load_lithology_review_history(session, (second, first))
    assert isinstance(entries, tuple)
    assert [item.record.mapping_id for item in entries] == ["review-1", "review-2"]
    assert all(item.source_status is ReviewSourceStatus.MATCHING for item in entries)
    assert not session.dirty and repr(session.project) == before
    with pytest.raises(FrozenInstanceError):
        entries[0].source_status = ReviewSourceStatus.DIFFERENT


def test_equal_times_preserve_selection_order_without_selecting_latest(tmp_path):
    session, first, second = _history_files(tmp_path)
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["recorded_at_utc"] = "2026-10-22T08:00:00Z"
    second.write_text(json.dumps(payload), encoding="utf-8")
    entries = load_lithology_review_history(session, (second, first))
    assert [item.record.mapping_id for item in entries] == ["review-2", "review-1"]


@pytest.mark.parametrize("count", [0, MAX_HISTORY_RECORDS + 1])
def test_record_count_is_bounded_before_any_file_read(tmp_path, count):
    with pytest.raises(ValueError, match="sixteen"):
        load_lithology_review_history(_session(), tuple(tmp_path / str(i) for i in range(count)))


@pytest.mark.parametrize("duplicate", ["path", "record", "utc_variant"])
def test_duplicates_are_rejected(tmp_path, duplicate):
    session, first, second = _history_files(tmp_path)
    if duplicate == "path":
        second = first
    else:
        payload = json.loads(first.read_text(encoding="utf-8"))
        if duplicate == "utc_variant":
            payload["recorded_at_utc"] = "2026-10-22T08:00:00Z"
        second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_lithology_review_history(session, (first, second))


@pytest.mark.parametrize("field", ["project_id", "well_id", "dataset_id", "depth_axis_id", "interval_id"])
def test_different_source_scopes_are_not_presented_as_one_history(tmp_path, field):
    session, first, second = _history_files(tmp_path)
    payload = json.loads(second.read_text(encoding="utf-8"))
    selected = payload if field == "project_id" else payload["mapping"]["source"]
    selected[field] = "different"
    second.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="one project"):
        load_lithology_review_history(session, (first, second))


def test_changed_source_snapshots_remain_separate_archival_assertions(tmp_path):
    session, first, second = _history_files(tmp_path)
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["mapping"]["source"]["source_sha256"] = "0" * 64
    second.write_text(json.dumps(payload), encoding="utf-8")
    entries = load_lithology_review_history(session, (first, second))
    assert entries[0].source_status is ReviewSourceStatus.MATCHING
    assert entries[1].source_status is ReviewSourceStatus.DIFFERENT


@pytest.mark.parametrize("failure", ["malformed", "missing"])
def test_one_bad_file_rejects_entire_selection_without_mutating_session(tmp_path, failure):
    session, first, second = _history_files(tmp_path)
    before = repr(session.project)
    if failure == "malformed":
        second.write_text("null", encoding="utf-8")
    else:
        second.unlink()
    with pytest.raises((ValueError, OSError)):
        load_lithology_review_history(session, (first, second))
    assert repr(session.project) == before


def test_all_entries_compare_against_current_source(tmp_path):
    session, first, second = _history_files(tmp_path)
    session.current_well.lithology[0].description = "Changed"
    entries = load_lithology_review_history(session, (first, second))
    assert all(item.source_status is ReviewSourceStatus.DIFFERENT for item in entries)


def test_path_resolution_loop_becomes_validation_error(tmp_path, monkeypatch):
    from pathlib import Path

    def loop(*args, **kwargs):
        raise RuntimeError("Symlink loop")

    monkeypatch.setattr(Path, "resolve", loop)
    with pytest.raises(ValueError, match="Invalid review path"):
        load_lithology_review_history(_session(), (tmp_path / "review.json",))
