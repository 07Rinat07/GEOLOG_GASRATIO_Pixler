import json
from pathlib import Path

import pytest

from geoworkbench.domain.models import Project
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.data.las_import_report import (
    LasImportReport,
    LasSourceSnapshot,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import PROJECT_FORMAT_VERSION


def test_atomic_save_creates_current_project_document(tmp_path) -> None:
    target = tmp_path / "nested" / "project.geolog.json"

    save_project(Project("project-1", "Project"), target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION
    assert payload["project"]["project_id"] == "project-1"
    assert payload["tablet_layouts"] == {}


def test_atomic_save_removes_temporary_file_after_replace_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "project.geolog.json"

    def fail_replace(source, destination) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("geoworkbench.storage.atomic_json.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save_project(Project("project-1", "Project"), target)

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_atomic_save_rejects_source_for_unknown_dataset(tmp_path) -> None:
    target = tmp_path / "project.geolog.json"

    with pytest.raises(ValueError, match="неизвестный набор"):
        save_project(
            Project("project-1", "Project"),
            target,
            source_documents={"missing": parse_lossless_las(b"~A\n1\n")},
        )

    assert not target.exists()


def test_atomic_save_rejects_report_for_unknown_dataset(tmp_path) -> None:
    target = tmp_path / "project.geolog.json"
    report = LasImportReport(
        LasSourceSnapshot(Path("source.las"), 0, "0" * 64, "utf-8", "none", (), None, None, None),
        DepthAxisReport(DepthDirection.UNKNOWN, None, None, None, False, 0, 0, 0),
        (),
    )

    with pytest.raises(ValueError, match="неизвестный набор"):
        save_project(
            Project("project-1", "Project"),
            target,
            import_reports={"missing": report},
        )

    assert not target.exists()


def test_streamed_json_matches_existing_format_for_arrays_and_unicode():
    from io import StringIO
    import json
    import numpy as np
    from geoworkbench.storage.atomic_json import _default, _write_json_stream
    payload = {"скважина": "М-1", "values": np.array([1.0, np.nan, 0.0]),
               "large": np.arange(100_000, dtype=float)}
    stream = StringIO()
    _write_json_stream(stream, payload)
    assert stream.getvalue() == json.dumps(payload, ensure_ascii=False, indent=2, default=_default)


def test_stream_encoding_error_preserves_existing_project(tmp_path, monkeypatch):
    from geoworkbench.domain.models import Project
    from geoworkbench.storage import atomic_json
    target = tmp_path / "project.geolog.json"
    target.write_text("previous version")

    def fail(stream, document):
        stream.write("partial")
        raise OSError("write failed")

    monkeypatch.setattr(atomic_json, "_write_json_stream", fail)
    with pytest.raises(OSError, match="write failed"):
        atomic_json.save_project(Project("stream-failure", "Project"), target)
    assert target.read_text() == "previous version"
    assert not list(tmp_path.glob("*.tmp"))
