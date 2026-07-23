from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.workspace_commands import WorkspaceCommandController


@dataclass
class FakePort:
    events: list[tuple[object, ...]] = field(default_factory=list)

    def show_dataset(self, dataset: Dataset) -> None:
        self.events.append(("dataset", dataset.dataset_id))

    def show_curve(self, dataset: Dataset, curve: CurveData) -> None:
        self.events.append(("curve", dataset.dataset_id, curve.metadata.curve_id))

    def show_track(self, track_id: str) -> None:
        self.events.append(("track", track_id))

    def show_lithology(self) -> None:
        self.events.append(("lithology",))

    def show_stratigraphy(self) -> None:
        self.events.append(("stratigraphy",))

    def show_interpretations(self, interpretation_id: str | None) -> None:
        self.events.append(("interpretations", interpretation_id))

    def show_interpretation_interval(self, interpretation_id: str, interval_id: str) -> None:
        self.events.append(("interpretation_interval", interpretation_id, interval_id))

    def show_annotations(self) -> None:
        self.events.append(("annotations",))

    def show_description_templates(self) -> None:
        self.events.append(("description_templates",))


def make_controller() -> tuple[ProjectSession, FakePort, WorkspaceCommandController]:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    curve = CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.array([1.0, 2.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    session = ProjectSession(project=Project("project", "Project", wells={well.well_id: well}))
    port = FakePort()
    return session, port, WorkspaceCommandController(session, port)


def test_dataset_curve_and_track_commands_select_context_before_rendering() -> None:
    session, port, controller = make_controller()

    assert controller.activate(("dataset", "well-1", "dataset-1")) is True
    assert controller.activate(("curve", "well-1", "dataset-1", "curve-1")) is True
    assert controller.activate(("track", "well-1", "dataset-1", "track-1")) is True

    assert session.current_well_id == "well-1"
    assert session.current_dataset_id == "dataset-1"
    assert port.events == [
        ("dataset", "dataset-1"),
        ("curve", "dataset-1", "curve-1"),
        ("track", "track-1"),
    ]


def test_well_scoped_commands_route_without_touching_serialized_model() -> None:
    session, port, controller = make_controller()
    session.dirty = False

    commands = (
        ("lithology_interval", "well-1", "lith-1"),
        ("stratigraphy", "well-1"),
        ("interpretation", "well-1", "interpretation-1"),
        ("interpretation_interval", "well-1", "interpretation-1", "interval-1"),
        ("annotations", "well-1"),
        ("description_templates",),
    )
    for command in commands:
        assert controller.activate(command) is True

    assert session.current_well_id == "well-1"
    assert session.dirty is False
    assert port.events == [
        ("lithology",),
        ("stratigraphy",),
        ("interpretations", "interpretation-1"),
        ("interpretation_interval", "interpretation-1", "interval-1"),
        ("annotations",),
        ("description_templates",),
    ]


def test_invalid_or_stale_tree_payload_is_ignored() -> None:
    session, port, controller = make_controller()

    assert controller.activate(None) is False
    assert controller.activate(("curve", "well-1", "dataset-1", "missing")) is False
    assert controller.activate(("dataset", "missing", "dataset-1")) is False
    assert controller.activate(("unknown",)) is False

    assert port.events == []
    assert session.current_dataset_id is None
