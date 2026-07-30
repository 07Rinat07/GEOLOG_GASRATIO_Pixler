from PySide6.QtWidgets import QWidget

from geoworkbench.ui.file_workspace_release import FileWorkspaceWidget as _ReleaseWorkspace


class FileWorkspaceWidget(_ReleaseWorkspace):
    def __init__(
        self,
        parent: QWidget | None = ...,
        *,
        language: str = ...,
    ) -> None: ...


def runtime_catalogs_have_same_keys() -> bool: ...
