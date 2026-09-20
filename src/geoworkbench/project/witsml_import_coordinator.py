from __future__ import annotations

from dataclasses import dataclass, field

from geoworkbench.project.session import ProjectSession
from geoworkbench.project.witsml_import_controller import (
    WitsmlProjectImportController,
    WitsmlProjectImportResult,
)
from geoworkbench.services.witsml_import_review import WitsmlImportCommit


@dataclass(slots=True)
class WitsmlImportCoordinator:
    """Own WITSML project-registration decisions outside the Qt shell.

    The UI is responsible for source selection, review dialogs and presentation.
    Registration policy and project mutation stay behind the application boundary.
    """

    session: ProjectSession
    controller: WitsmlProjectImportController = field(init=False)

    def __post_init__(self) -> None:
        self.controller = WitsmlProjectImportController(self.session)

    def register_reviewed_commit(
        self,
        commit: WitsmlImportCommit,
    ) -> WitsmlProjectImportResult:
        return self.controller.register(
            commit,
            create_new_well=self.session.current_well is None,
        )


__all__ = ["WitsmlImportCoordinator"]
