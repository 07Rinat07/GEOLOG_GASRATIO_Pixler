from PySide6.QtWidgets import QWidget

from geoworkbench.ui.file_workspace_v3 import FileWorkspaceWidget as _LocalizedWorkspace


class FileWorkspaceWidget(_LocalizedWorkspace):
    def __init__(
        self,
        parent: QWidget | None = ...,
        *,
        language: str = ...,
    ) -> None: ...
