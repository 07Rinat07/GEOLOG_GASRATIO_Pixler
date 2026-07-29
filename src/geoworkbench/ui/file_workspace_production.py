from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget

from geoworkbench.ui.file_workspace_shell import (
    FileWorkspaceWidget as _FileWorkspaceShell,
)


class FileWorkspaceWidget(_FileWorkspaceShell):
    """Final Files workspace presentation used by the application."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self.sections.setTabPosition(QTabWidget.TabPosition.North)
        self.sections.tabBar().setExpanding(False)
