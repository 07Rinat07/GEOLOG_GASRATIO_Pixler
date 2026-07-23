import json

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.domain.operational_events import (
    CasingEventPayload,
    FormationTopEventPayload,
    OperationalEvent,
    OperationalEventKind,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
    project_document_from_dict,
)


def make_project() -> Project:
    dataset = Dataset(
        "dataset-1",
        "Depth",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    well = Well("well-1", "Well 1", datasets={dataset.dataset_id: dataset})
    well.operational_events = {
        "casing-1": OperationalEvent(
            "casing-1",
            well.well_id,
            OperationalEventKind.CASING,
            CasingEventPayload("production", 177.8, shoe_depth_m=100.0),
            depth_m=100.0,
            source="manual",
        ),
        "top-1": OperationalEvent(
            "top-1",
            well.well_id,
            OperationalEventKind.FORMATION_TOP,
            FormationTopEventPayload("K1a", "Albian", 0.95),
            depth_m=101.0,
            source="interpreter",
        ),
    }
    return Project("project-1", "Project", wells={well.well_id: well})


def test_project_v18_round_trip_preserves_typed_events(tmp_path) -> None:
    target = tmp_path / "events.geolog.json"
    save_project(make_project(), target)

    loaded = load_project(target)
    events = loaded.wells["well-1"].operational_events

    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == 20
    assert PROJECT_FORMAT_VERSION == 20
    assert isinstance(events["casing-1"].payload, CasingEventPayload)
    assert events["casing-1"].payload.outer_diameter_mm == 177.8
    assert isinstance(events["top-1"].payload, FormationTopEventPayload)
    assert events["top-1"].payload.formation_code == "K1a"


def test_codec_rejects_kind_payload_mismatch() -> None:
    payload = {
        "format_version": 17,
        "project": {
            "project_id": "project-1",
            "name": "Project",
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "operational_events": {
                        "event-1": {
                            "event_id": "event-1",
                            "well_id": "well-1",
                            "kind": "gas",
                            "payload": {
                                "show_type": "oil",
                                "intensity": 3,
                                "fluorescence_color": None,
                                "description": None,
                            },
                            "depth_m": 100.0,
                            "elapsed_time_s": None,
                            "measured_at": None,
                            "received_at": None,
                            "source": "manual",
                            "revision": 1,
                            "calibration_id": None,
                            "calibrated_at": None,
                            "qc_flags": [],
                        }
                    },
                }
            },
        },
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "image_assets": {},
        "import_reports": {},
    }

    with pytest.raises(ProjectFormatError, match="payload события gas"):
        project_document_from_dict(payload)


def test_codec_rejects_unknown_event_fields() -> None:
    project = make_project()
    event = project.wells["well-1"].operational_events["casing-1"]
    payload = {
        "format_version": 17,
        "project": {
            "project_id": project.project_id,
            "name": project.name,
            "wells": {
                "well-1": {
                    "well_id": "well-1",
                    "name": "Well 1",
                    "datasets": {},
                    "operational_events": {
                        event.event_id: {
                            "event_id": event.event_id,
                            "well_id": event.well_id,
                            "kind": event.kind.value,
                            "payload": {
                                "casing_type": "production",
                                "outer_diameter_mm": 177.8,
                                "shoe_depth_m": 100.0,
                                "status": None,
                            },
                            "depth_m": 100.0,
                            "elapsed_time_s": None,
                            "measured_at": None,
                            "received_at": None,
                            "source": "manual",
                            "revision": 1,
                            "calibration_id": None,
                            "calibrated_at": None,
                            "qc_flags": [],
                            "unexpected": True,
                        }
                    },
                }
            },
        },
        "tablet_layouts": {},
        "tablet_presets": {},
        "source_artifacts": {},
        "image_assets": {},
        "import_reports": {},
    }

    with pytest.raises(ProjectFormatError, match="неизвестные поля"):
        project_document_from_dict(payload)
