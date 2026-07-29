from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoworkbench.ui.file_workspace_v2 import FileWorkspaceWidget as _V2FileWorkspaceWidget


class FileWorkspaceWidget(_V2FileWorkspaceWidget):
    def __init__(
        self,
        parent: QWidget | None = ...,
        *,
        language: str = ...,
    ) -> None: ...
