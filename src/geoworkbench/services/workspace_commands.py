from __future__ import annotations

from typing import Protocol

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.session import ProjectSession


class WorkspaceCommandPort(Protocol):
    """UI reactions requested after a workspace command resolves its project context."""

    def show_dataset(self, dataset: Dataset) -> None: ...

    def show_curve(self, dataset: Dataset, curve: CurveData) -> None: ...

    def show_track(self, track_id: str) -> None: ...

    def show_lithology(self) -> None: ...

    def show_stratigraphy(self) -> None: ...

    def show_interpretations(self, interpretation_id: str | None) -> None: ...

    def show_interpretation_interval(
        self,
        interpretation_id: str,
        interval_id: str,
    ) -> None: ...

    def show_annotations(self) -> None: ...

    def show_description_templates(self) -> None: ...


class WorkspaceCommandController:
    """Resolve project-tree commands without exposing session mutation to Qt handlers."""

    def __init__(self, session: ProjectSession, port: WorkspaceCommandPort) -> None:
        self.session = session
        self._port = port

    def activate(self, payload: object) -> bool:
        if not isinstance(payload, tuple) or not payload or not isinstance(payload[0], str):
            return False
        kind = payload[0]
        try:
            if kind == "dataset" and len(payload) == 3:
                dataset = self._select_dataset(payload[1], payload[2])
                self._port.show_dataset(dataset)
                return True
            if kind == "curve" and len(payload) == 4:
                well_id, dataset = self._resolve_dataset(payload[1], payload[2])
                curve = dataset.curves.get(self._text(payload[3]))
                if curve is None:
                    return False
                self._commit_dataset_selection(well_id, dataset.dataset_id)
                self._port.show_curve(dataset, curve)
                return True
            if kind == "track" and len(payload) == 4:
                self._select_dataset(payload[1], payload[2])
                self._port.show_track(self._text(payload[3]))
                return True
            if kind in {"lithology", "lithology_interval"} and len(payload) >= 2:
                self._select_well(payload[1])
                self._port.show_lithology()
                return True
            if kind in {"stratigraphy", "stratigraphy_interval"} and len(payload) >= 2:
                self._select_well(payload[1])
                self._port.show_stratigraphy()
                return True
            if kind == "interpretations" and len(payload) == 2:
                self._select_well(payload[1])
                self._port.show_interpretations(None)
                return True
            if kind == "interpretation" and len(payload) == 3:
                self._select_well(payload[1])
                self._port.show_interpretations(self._text(payload[2]))
                return True
            if kind == "interpretation_interval" and len(payload) == 4:
                self._select_well(payload[1])
                self._port.show_interpretation_interval(
                    self._text(payload[2]),
                    self._text(payload[3]),
                )
                return True
            if kind in {"annotations", "annotation"} and len(payload) >= 2:
                self._select_well(payload[1])
                self._port.show_annotations()
                return True
            if kind == "description_templates" and len(payload) == 1:
                self._port.show_description_templates()
                return True
        except (KeyError, TypeError, ValueError):
            return False
        return False

    def _select_well(self, value: object) -> str:
        well_id = self._text(value)
        if well_id not in self.session.project.wells:
            raise KeyError(well_id)
        self.session.current_well_id = well_id
        return well_id

    def _select_dataset(self, well_value: object, dataset_value: object) -> Dataset:
        well_id, dataset = self._resolve_dataset(well_value, dataset_value)
        self._commit_dataset_selection(well_id, dataset.dataset_id)
        return dataset

    def _resolve_dataset(
        self,
        well_value: object,
        dataset_value: object,
    ) -> tuple[str, Dataset]:
        well_id = self._text(well_value)
        well = self.session.project.wells.get(well_id)
        if well is None:
            raise KeyError(well_id)
        dataset_id = self._text(dataset_value)
        dataset = well.datasets.get(dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        return well_id, dataset

    def _commit_dataset_selection(self, well_id: str, dataset_id: str) -> None:
        self.session.current_well_id = well_id
        self.session.current_dataset_id = dataset_id

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("Workspace identifier must be a non-empty string")
        return value
