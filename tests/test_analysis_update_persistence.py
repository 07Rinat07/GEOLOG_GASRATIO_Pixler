from __future__ import annotations

from copy import deepcopy
import json

import pytest

from geoworkbench.domain.analysis_update import (
    AnalysisCellChange,
    AnalysisField,
    AnalysisUpdateRecord,
)
from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)
from geoworkbench.storage.project_migrations import migrate_project_payload


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _record() -> AnalysisUpdateRecord:
    return AnalysisUpdateRecord(
        update_id="analysis-update-1",
        well_id="well-1",
        source_name="late-analysis.csv",
        source_sha256=_SHA_A,
        imported_at="2026-09-11T04:30:00+00:00",
        selected_fields=(AnalysisField.CALCITE_PERCENT,),
        changes=(
            AnalysisCellChange(
                sample_id="sample-1",
                top_depth=100.0,
                bottom_depth=101.0,
                field=AnalysisField.CALCITE_PERCENT,
                old_value=None,
                new_value=37.5,
            ),
        ),
        well_sha256_before=_SHA_B,
        well_sha256_after=_SHA_C,
    )


def _current_payload(record: AnalysisUpdateRecord | None = None) -> dict[str, object]:
    history: list[object] = []
    if record is not None:
        history = [
            {
                "update_id": record.update_id,
                "well_id": record.well_id,
                "source_name": record.source_name,
                "source_sha256": record.source_sha256,
                "imported_at": record.imported_at,
                "selected_fields": [item.value for item in record.selected_fields],
                "changes": [
                    {
                        "sample_id": change.sample_id,
                        "top_depth": change.top_depth,
                        "bottom_depth": change.bottom_depth,
                        "field": change.field.value,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                    }
                    for change in record.changes
                ],
                "well_sha256_before": record.well_sha256_before,
                "well_sha256_after": record.well_sha256_after,
            }
        ]
    return {
        "format_version": 28,
        "project": {
            "project_id": "project-1",
            "name": "Project",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "analysis_update_history": history,
                }
            },
        },
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "image_assets": {},
        "import_reports": {},
    }


def test_project_v28_round_trip_preserves_well_analysis_history(tmp_path) -> None:
    record = _record()
    well = Well(
        well_id="well-1",
        name="Well 1",
        cuttings=[CuttingsSample("sample-1", 100.0, 101.0, calcite_percent=37.5)],
        analysis_update_history=[record],
    )
    project = Project(project_id="project-1", name="Project", wells={well.well_id: well})
    target = tmp_path / "analysis-history.geolog"

    save_project(project, target)
    restored = load_project(target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert PROJECT_FORMAT_VERSION == 29
    assert payload["format_version"] == 29
    assert restored.wells["well-1"].analysis_update_history == [record]


def test_v27_migration_adds_empty_well_analysis_history_without_mutation() -> None:
    source = {
        "format_version": 27,
        "project": {
            "project_id": "project-1",
            "name": "Project",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                }
            },
        },
    }
    before = deepcopy(source)

    migrated = migrate_project_payload(source, 28)

    assert migrated["format_version"] == 28
    assert migrated["project"]["wells"]["well-1"]["analysis_update_history"] == []
    assert source == before


def test_project_v28_rejects_unknown_analysis_field() -> None:
    payload = _current_payload(_record())
    history = payload["project"]["wells"]["well-1"]["analysis_update_history"]
    history[0]["selected_fields"] = ["not_supported"]

    with pytest.raises(ProjectFormatError, match="(?i)истори"):
        project_document_from_dict(payload)


def test_project_v28_rejects_non_fill_only_analysis_history() -> None:
    payload = _current_payload(_record())
    history = payload["project"]["wells"]["well-1"]["analysis_update_history"]
    history[0]["changes"][0]["old_value"] = 12.0

    with pytest.raises(ProjectFormatError, match="(?i)истори"):
        project_document_from_dict(payload)


def test_project_v28_rejects_non_list_analysis_history() -> None:
    payload = _current_payload()
    payload["project"]["wells"]["well-1"]["analysis_update_history"] = {}

    with pytest.raises(ProjectFormatError, match="(?i)истори"):
        project_document_from_dict(payload)
