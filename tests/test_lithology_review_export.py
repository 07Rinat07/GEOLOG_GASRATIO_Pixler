from datetime import datetime
import json

import pytest

from geoworkbench.services.lithology_review_export import export_lithology_review
from test_lithology_source_mapping import _mapping
from test_report_geology_snapshot import _session


def test_export_retains_explicit_review_and_source_identity_without_project_changes(tmp_path):
    session = _session()
    session.dirty = False
    mapping = _mapping(session, reviewer="Геолог", applicability_reference="Тестовый эталон")
    before = repr(session.project)
    target = tmp_path / "Проверка.json"
    assert export_lithology_review(session, mapping, target) == target
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["artifact_kind"] == "lithology_mapping_review"
    assert payload["review_status"] == "operator_review_not_geological_approval"
    assert datetime.fromisoformat(payload["recorded_at_utc"]).utcoffset().total_seconds() == 0
    assert payload["project_id"] == session.project.project_id
    saved = payload["mapping"]
    assert saved["mapping_id"] == mapping.mapping_id and saved["reviewer"] == "Геолог"
    assert saved["applicability_reference"] == "Тестовый эталон"
    assert saved["rock_family"] == "halite" and saved["quality"] == "validated"
    assert saved["source"]["source_sha256"] == mapping.source.source_sha256
    assert saved["source"]["axis_sha256"] == mapping.source.axis_sha256
    assert saved["source"]["interval_id"] == "lith-in"
    assert saved["source"]["top_md_m"] == 1000 and saved["source"]["bottom_md_m"] == 1008
    assert not session.dirty and repr(session.project) == before
    assert list(tmp_path.iterdir()) == [target]


def test_existing_file_requires_explicit_overwrite(tmp_path):
    session = _session()
    target = tmp_path / "review.json"
    target.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        export_lithology_review(session, _mapping(session), target)
    assert target.read_bytes() == b"original"
    export_lithology_review(session, _mapping(session), target, overwrite=True)
    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == 1
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("stage", ["before", "during"])
def test_stale_source_never_replaces_existing_file(tmp_path, monkeypatch, stage):
    import geoworkbench.services.lithology_review_export as exporter

    session = _session()
    mapping = _mapping(session)
    target = tmp_path / "review.json"
    target.write_bytes(b"original")

    def change(*args):
        session.current_well.lithology[0].description = "Changed"

    if stage == "before":
        change()
    else:
        monkeypatch.setattr(exporter.os, "fsync", change)
    with pytest.raises(ValueError, match="changed"):
        export_lithology_review(session, mapping, target, overwrite=True)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_atomic_publication_preserves_original_and_cleans_stage(tmp_path, monkeypatch):
    import geoworkbench.services.lithology_review_export as exporter

    session = _session()
    target = tmp_path / "review.json"
    target.write_bytes(b"original")

    def fail(*args):
        raise PermissionError("Synthetic publication failure")

    monkeypatch.setattr(exporter.os, "replace", fail)
    with pytest.raises(PermissionError):
        export_lithology_review(session, _mapping(session), target, overwrite=True)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_concurrent_destination_creation_is_not_overwritten(tmp_path, monkeypatch):
    import geoworkbench.services.lithology_review_export as exporter

    session = _session()
    target = tmp_path / "review.json"
    link = exporter.os.link

    def competing_writer(source, destination):
        target.write_bytes(b"concurrent")
        return link(source, destination)

    monkeypatch.setattr(exporter.os, "link", competing_writer)
    with pytest.raises(FileExistsError):
        export_lithology_review(session, _mapping(session), target)
    assert target.read_bytes() == b"concurrent"
    assert list(tmp_path.iterdir()) == [target]


def test_project_package_is_not_an_export_destination(tmp_path):
    session = _session()
    target = tmp_path / "project.geologpkg"
    target.write_bytes(b"project")
    with pytest.raises(ValueError, match="JSON"):
        export_lithology_review(session, _mapping(session), target, overwrite=True)
    assert target.read_bytes() == b"project"
    assert list(tmp_path.iterdir()) == [target]
