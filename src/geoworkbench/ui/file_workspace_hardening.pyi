from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoworkbench.ui.file_workspace_depth import FileWorkspaceWidget as _DepthWorkspace


class FileWorkspaceWidget(_DepthWorkspace):
    def __init__(self, parent: QWidget | None = ..., *, language: str = ...) -> None: ...
    def set_language(self, language: object) -> None: ...
