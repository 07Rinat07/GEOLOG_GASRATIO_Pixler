from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pytest

from geoworkbench.domain.gas_conditioning_qc import (
    GasComponentConditioningQc,
    GasConditioningQcInterval,
    GasConditioningQcSummary,
)
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)
from geoworkbench.storage.project_migrations import migrate_project_payload


def _summary() -> GasConditioningQcSummary:
    return GasConditioningQcSummary(
        nominal_depth_step=0.5,
        affected_depth_row_count=3,
        interpolated_component_sample_count=4,
        components=(
            GasComponentConditioningQc(
                mnemonic="C1",
                interpolated_sample_count=1,
                interpolated_intervals=(
                    GasConditioningQcInterval(1000.5, 1000.5, 1),
                ),
                max_gap=1.0,
            ),
            GasComponentConditioningQc(
                mnemonic="C2",
                interpolated_sample_count=3,
                interpolated_intervals=(
                    GasConditioningQcInterval(1001.0, 1002.0, 3),
                ),
                max_gap=1.5,
            ),
        ),
    )


def _project_with_qc() -> Project:
    dataset = Dataset(
        dataset_id="gas",
        name="Gas",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1000.5, 1001.0, 1001.5, 1002.0]),
        gas_conditioning_qc=_summary(),
    )
    well = Well("well", "Well", datasets={dataset.dataset_id: dataset})
    return Project("project", "Project", wells={well.well_id: well})


def test_project_round_trip_preserves_gas_conditioning_qc(tmp_path) -> None:
    target = tmp_path / "gas-qc.geolog.json"
    save_project(_project_with_qc(), target)

    restored = load_project(target)
    dataset = restored.wells["well"].datasets["gas"]

    assert dataset.gas_conditioning_qc == _summary()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION == 24
    raw_qc = payload["project"]["wells"]["well"]["datasets"]["gas"][
        "gas_conditioning_qc"
    ]
    assert raw_qc["affected_depth_row_count"] == 3
    assert raw_qc["components"][1]["interpolated_intervals"][0] == {
        "minimum_depth": 1001.0,
        "maximum_depth": 1002.0,
        "sample_count": 3,
    }


def test_v23_migration_adds_empty_gas_conditioning_qc_without_mutating_source() -> None:
    payload = {
        "format_version": 23,
        "project": {
            "wells": {
                "well": {
                    "datasets": {
                        "gas": {"dataset_id": "gas"},
                    }
                }
            }
        },
    }

    migrated = migrate_project_payload(payload, 24)

    assert migrated["format_version"] == 24
    assert migrated["project"]["wells"]["well"]["datasets"]["gas"][
        "gas_conditioning_qc"
    ] is None
    assert "gas_conditioning_qc" not in payload["project"]["wells"]["well"]["datasets"][
        "gas"
    ]


def test_current_project_rejects_invalid_gas_conditioning_qc_payload() -> None:
    payload = {
        "format_version": PROJECT_FORMAT_VERSION,
        "project": asdict(_project_with_qc()),
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "image_assets": {},
        "import_reports": {},
    }
    qc = payload["project"]["wells"]["well"]["datasets"]["gas"]["gas_conditioning_qc"]
    assert isinstance(qc, dict)
    qc["affected_depth_row_count"] = -1

    with pytest.raises(ProjectFormatError, match="gas conditioning QC summary"):
        project_document_from_dict(payload)
