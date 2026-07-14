import json

import pytest

from geoworkbench.domain.models import Project
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
