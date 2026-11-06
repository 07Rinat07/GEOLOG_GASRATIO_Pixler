from dataclasses import replace
import json

import numpy as np
import pytest

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services import gis_calibration_records as records
from geoworkbench.services.gis_reference_calibration import (
    evaluate_gis_reference_sample, validate_gis_reference_calibration,
)
from test_gis_reference_calibration import _calibration, _dataset


def _saved(tmp_path, *, density=False):
    dataset = _dataset(density)
    calibration = _calibration(dataset, density)
    target = tmp_path / "parameters.json"
    records.export_gis_calibration_record(dataset, calibration, target)
    return dataset, calibration, target


@pytest.mark.parametrize("density", [False, True])
@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_parameters_roundtrip_through_real_project_reopen_without_activation(
    tmp_path, monkeypatch, density, extension,
):
    dataset = _dataset(density)
    dataset.curves["selected"].version = 7
    calibration = _calibration(dataset, density)
    session = ProjectSession()
    session.add_dataset(dataset)
    project = tmp_path / ("source" + extension)
    ProjectController(session=session).save_project(project)
    original_project = project.read_bytes()
    target = tmp_path / "параметры.json"
    records.export_gis_calibration_record(dataset, calibration, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["review_status"] == "parameters_only_not_active_calibration"
    assert set(payload["source"]["values"]) == {"dtype", "shape", "sha256"}
    assert payload["source"]["values"]["shape"] == [3]
    assert payload["source"]["review"]["curve"]["version"] == 7
    reopened = ProjectController().open_project(project)
    restored = reopened.current_dataset
    assert restored is not None
    assert restored.curves["selected"].version == 7
    with pytest.raises(ValueError, match="stale|replaced"):
        validate_gis_reference_calibration(restored, calibration)

    import geoworkbench.services.gis_reference_calibration as calibrations

    def no_calculation(*args, **kwargs):
        raise AssertionError("Reading parameters must not activate or evaluate calibration")

    monkeypatch.setattr(calibrations, "create_gis_reference_calibration", no_calculation)
    monkeypatch.setattr(calibrations, "evaluate_gis_reference_sample", no_calculation)
    before = repr(reopened.project)
    depths, values = restored.active_index.values, restored.curves["selected"].values
    record = records.load_gis_calibration_record(target, dataset=restored)
    records.validate_gis_calibration_record_source(restored, record)
    assert record.method_id == calibration.source.method_id
    assert record.curve_key == "selected"
    assert record.parameters == calibration.parameters
    assert record.md_bounds == calibration.md_bounds
    assert record.calibration_id == calibration.calibration_id
    assert record.tool_id == calibration.tool_id
    assert record.reviewer == calibration.reviewer
    assert record.applicability_reference == calibration.applicability_reference
    assert not hasattr(record, "sample")
    assert restored.active_index.values is depths
    assert restored.curves["selected"].values is values
    assert repr(reopened.project) == before and not reopened.dirty
    np.testing.assert_array_equal(values, dataset.curves["selected"].values)
    np.testing.assert_array_equal(depths, dataset.active_index.values)
    assert project.read_bytes() == original_project


@pytest.mark.parametrize("change", [
    "dataset_id", "curve_id", "source_dataset_id", "axis_id", "curve_key", "unit",
    "description", "semantic_evidence", "axis_evidence", "axis_confidence", "axis_mnemonic",
    "axis_unit", "values", "depth", "dtype", "shape", "version",
])
def test_changed_or_foreign_sources_cannot_prefill_parameters(tmp_path, change):
    dataset, _, target = _saved(tmp_path)
    curve, axis = dataset.curves["selected"], dataset.active_index
    if change == "dataset_id":
        dataset.dataset_id = "foreign"
    elif change in {"curve_id", "source_dataset_id", "unit", "description"}:
        curve.metadata = replace(curve.metadata, **{change: "changed"})
    elif change == "semantic_evidence":
        curve.metadata = replace(curve.metadata, semantic=replace(
            curve.metadata.semantic, evidence=("different evidence",),
        ))
    elif change == "axis_id":
        old = dataset.active_index_id
        axis.index_id = "other-axis"
        dataset.indexes[axis.index_id] = dataset.indexes.pop(old)
        dataset.active_index_id = axis.index_id
    elif change == "curve_key":
        dataset.curves["other"] = dataset.curves.pop("selected")
    elif change == "axis_evidence":
        axis.evidence = ("different evidence",)
    elif change == "axis_confidence":
        axis.confidence = 0.75
    elif change == "axis_mnemonic":
        axis.mnemonic = "OTHER_MD"
    elif change == "axis_unit":
        axis.unit = "meter"
    elif change == "version":
        curve.version += 1
    elif change == "values":
        curve.values[2] = 150
    elif change == "depth":
        axis.values[1] = 101.5
    elif change == "dtype":
        curve.values = curve.values.astype(np.float32)
    else:
        curve.values.shape = (1, 3)
    before = repr(dataset)
    with pytest.raises(ValueError, match="source"):
        records.load_gis_calibration_record(target, dataset=dataset)
    assert repr(dataset) == before


def _write_payload(target, payload):
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("field", ["calibration_id", "reviewer", "applicability_reference"])
def test_escaped_invalid_unicode_is_rejected_before_editor_prefill(tmp_path, field):
    dataset, _, target = _saved(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload[field] = "invalid\ud800text"
    target.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(ValueError, match="Unicode"):
        records.load_gis_calibration_record(target, dataset=dataset)


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("artifact_kind", "other"),
    ("review_status", "approved"), ("recorded_at_utc", "2026-11-06T00:00:00"),
    ("calibration_id", "x" * 201), ("tool_id", "x" * 201), ("reviewer", "x" * 201),
    ("applicability_reference", "x" * 2001), ("calibration_id", " "),
    ("md_bounds", [True, 102]), ("md_bounds", [102, 100]), ("md_bounds", [99, 102]),
    ("md_bounds", [100]), ("md_bounds", [100, float("inf")]),
    ("parameters", {"clean_reference_api": True, "shale_reference_api": 125}),
    ("parameters", {"clean_reference_api": 25, "shale_reference_api": float("nan")}),
    ("parameters", {"clean_reference_api": 125, "shale_reference_api": 25}),
    ("parameters", {"clean_reference_api": 25}),
    ("parameters", {"clean_reference_api": "25", "shale_reference_api": 125}),
    ("parameters", {"clean_reference_api": 25, "shale_reference_api": 10**400}),
])
def test_malformed_fields_are_rejected_without_mutation(tmp_path, field, value):
    dataset, _, target = _saved(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload[field] = value
    _write_payload(target, payload)
    before = repr(dataset)
    with pytest.raises(ValueError):
        records.load_gis_calibration_record(target, dataset=dataset)
    assert repr(dataset) == before


@pytest.mark.parametrize("field,value", [
    ("dtype", "object"), ("dtype", "<c16"), ("dtype", "<f3"),
    ("shape", [True]), ("shape", [-1]), ("shape", [0]), ("shape", [3, 1]),
    ("shape", []), ("shape", [2**64]), ("shape", "3"),
    ("sha256", "not-a-digest"),
])
def test_malformed_fingerprints_are_rejected(tmp_path, field, value):
    dataset, _, target = _saved(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["source"]["values"][field] = value
    _write_payload(target, payload)
    with pytest.raises(ValueError):
        records.load_gis_calibration_record(target, dataset=dataset)


@pytest.mark.parametrize("corruption", ["unknown", "missing", "duplicate", "oversize", "unicode"])
def test_strict_bounded_json_reader(tmp_path, corruption):
    dataset, _, target = _saved(tmp_path)
    text = target.read_text(encoding="utf-8")
    if corruption in {"unknown", "missing"}:
        payload = json.loads(text)
        if corruption == "unknown":
            payload["source"]["unknown"] = 1
        else:
            del payload["source"]["review"]["curve"]["unit"]
        _write_payload(target, payload)
    elif corruption == "duplicate":
        target.write_text(text.replace('"calibration_id":', '"calibration_id":"other", "calibration_id":'),
                          encoding="utf-8")
    elif corruption == "oversize":
        target.write_bytes(b" " * (records.MAX_RECORD_BYTES + 1))
    else:
        target.write_bytes(b"\xff")
    with pytest.raises(ValueError):
        records.load_gis_calibration_record(target, dataset=dataset)


@pytest.mark.parametrize("when,change", [
    ("before", "values"), ("during", "values"), ("during", "metadata"),
    ("during", "axis_evidence"),
])
def test_failed_source_recheck_preserves_existing_output_and_cleans_stage(
    tmp_path, monkeypatch, when, change,
):
    dataset = _dataset()
    calibration = _calibration(dataset)
    target = tmp_path / "record.json"
    target.write_bytes(b"original record")

    def edit(*args):
        if change == "values":
            dataset.curves["selected"].values[0] = 70
        elif change == "metadata":
            curve = dataset.curves["selected"]
            curve.metadata = replace(curve.metadata, description="changed during write")
        else:
            dataset.active_index.evidence = ("changed during write",)

    if when == "before":
        edit()
    else:
        monkeypatch.setattr(records.os, "fsync", edit)
    with pytest.raises(ValueError):
        records.export_gis_calibration_record(dataset, calibration, target, overwrite=True)
    assert target.read_bytes() == b"original record"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("operation", ["replace", "fsync"])
def test_write_or_publish_failure_preserves_existing_output(tmp_path, monkeypatch, operation):
    dataset = _dataset()
    calibration = _calibration(dataset)
    target = tmp_path / "record.json"
    target.write_bytes(b"original record")

    def fail(*args):
        raise PermissionError("Synthetic failure")

    monkeypatch.setattr(records.os, operation, fail)
    with pytest.raises(PermissionError):
        records.export_gis_calibration_record(dataset, calibration, target, overwrite=True)
    assert target.read_bytes() == b"original record"
    assert list(tmp_path.iterdir()) == [target]


def test_overwrite_requires_explicit_choice_and_refuses_concurrent_destination(tmp_path, monkeypatch):
    dataset, calibration, target = _saved(tmp_path)
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        records.export_gis_calibration_record(dataset, calibration, target)
    assert target.read_bytes() == original
    records.export_gis_calibration_record(dataset, calibration, target, overwrite=True)
    assert records.load_gis_calibration_record(target, dataset=dataset).method_id == "igr-linear-1"
    concurrent = tmp_path / "concurrent.json"
    link = records.os.link

    def competing_writer(source, destination):
        concurrent.write_bytes(b"concurrent writer")
        return link(source, destination)

    monkeypatch.setattr(records.os, "link", competing_writer)
    with pytest.raises(FileExistsError):
        records.export_gis_calibration_record(dataset, calibration, concurrent)
    assert concurrent.read_bytes() == b"concurrent writer"
    assert not list(tmp_path.glob(".gis-calibration-*"))


@pytest.mark.parametrize("destination", ["source.las", "project.geolog.json", "source.json"])
def test_source_and_project_destinations_are_protected(tmp_path, destination):
    dataset = _dataset()
    target = tmp_path / destination
    target.write_bytes(b"source data")
    dataset.source_path = target
    with pytest.raises(ValueError):
        records.export_gis_calibration_record(dataset, _calibration(dataset), target, overwrite=True)
    assert target.read_bytes() == b"source data"
    assert list(tmp_path.iterdir()) == [target]


def test_source_alias_guard_rechecks_after_write(tmp_path, monkeypatch):
    dataset = _dataset()
    source = tmp_path / "source.las"
    source.write_bytes(b"source data")
    dataset.source_path = source
    target = tmp_path / "alias.json"
    monkeypatch.setattr(records.os, "fsync", lambda fd: records.os.link(source, target))
    with pytest.raises(ValueError, match="source file"):
        records.export_gis_calibration_record(dataset, _calibration(dataset), target, overwrite=True)
    assert source.read_bytes() == target.read_bytes() == b"source data"
    assert not list(tmp_path.glob(".gis-calibration-*"))


def test_text_limits_allow_ui_maxima_and_never_truncate(tmp_path):
    dataset = _dataset()
    calibration = _calibration(dataset, calibration_id="к" * 200, tool_id="t" * 200,
                               reviewer="r" * 200, applicability_reference="э" * 2000)
    target = tmp_path / "record.json"
    records.export_gis_calibration_record(dataset, calibration, target)
    record = records.load_gis_calibration_record(target, dataset=dataset)
    assert record.calibration_id == calibration.calibration_id
    assert record.applicability_reference == calibration.applicability_reference
    with pytest.raises(ValueError, match="limit"):
        records.export_gis_calibration_record(
            dataset, replace(calibration, reviewer="r" * 201), target, overwrite=True,
        )
    assert records.load_gis_calibration_record(target, dataset=dataset) == record


def test_live_runtime_validation_keeps_array_identity_guard(tmp_path):
    dataset, calibration, target = _saved(tmp_path)
    dataset.curves["selected"].values = dataset.curves["selected"].values.copy()
    assert records.load_gis_calibration_record(target, dataset=dataset).curve_key == "selected"
    with pytest.raises(ValueError, match="replaced"):
        validate_gis_reference_calibration(dataset, calibration)
    with pytest.raises(ValueError, match="replaced"):
        evaluate_gis_reference_sample(dataset, calibration, sample_index=0)
    with pytest.raises(ValueError, match="replaced"):
        records.export_gis_calibration_record(dataset, calibration, target, overwrite=True)
