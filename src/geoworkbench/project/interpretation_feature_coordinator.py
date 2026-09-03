from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import WellInterpretation
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.controller import TabletController
from geoworkbench.tablet.models import TrackKind


@dataclass(frozen=True, slots=True)
class InterpretationFeatureState:
    """Headless snapshot consumed by the Qt interpretation presentation."""

    interpretations: tuple[WellInterpretation, ...]
    selected_interpretation_id: str | None
    selected_interval_id: str | None
    interpretation_track_created: bool = False


@dataclass(slots=True)
class InterpretationFeatureCoordinator:
    """Coordinate interpretation selection and tablet lifecycle outside Qt.

    Interpretation editing owns project mutations through ``InterpretationController``;
    ``TabletController`` owns layout mutation.  This coordinator is the application
    boundary that joins the two features so ``MainWindow`` only renders the resulting
    state and no longer edits controller selection or layout lifecycle directly.
    """

    session: ProjectSession
    interpretation: InterpretationController
    tablet: TabletController

    def clear_interval_selection(self) -> InterpretationFeatureState:
        self.interpretation.selected_interval_id = None
        return self._state()

    def sync_after_change(self) -> InterpretationFeatureState:
        self.interpretation.normalize_selection()
        well = self.session.current_well
        layout = self.session.current_tablet_layout
        created = False
        if (
            well is not None
            and well.interpretations
            and layout is not None
            and not any(track.kind is TrackKind.INTERPRETATION for track in layout.tracks)
        ):
            try:
                self.tablet.add_track(TrackKind.INTERPRETATION)
                created = True
            except (RuntimeError, ValueError):
                # A missing/temporarily invalid dataset must not make a presentation
                # refresh fail. The next synchronization retries the lifecycle rule.
                created = False
        return self._state(interpretation_track_created=created)

    def _state(self, *, interpretation_track_created: bool = False) -> InterpretationFeatureState:
        well = self.session.current_well
        interpretations = (
            tuple(well.interpretations.values()) if well is not None else ()
        )
        return InterpretationFeatureState(
            interpretations=interpretations,
            selected_interpretation_id=self.interpretation.selected_interpretation_id,
            selected_interval_id=self.interpretation.selected_interval_id,
            interpretation_track_created=interpretation_track_created,
        )


__all__ = ["InterpretationFeatureCoordinator", "InterpretationFeatureState"]
