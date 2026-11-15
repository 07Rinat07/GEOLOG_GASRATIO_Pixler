"""Qt ownership adapter for pyqtgraph's Plot Options menu.

pyqtgraph 0.14 creates PlotItem.ctrlMenu as a parentless QMenu even when
the menu is disabled. Its QWidgetActions belong to the PlotItem, but the
menu itself is not part of the native plot tree. Windows diagnostics
showed the menu surviving destruction of its PlotItem and main window.
Keep the actual upstream menu and its controls; only establish ownership.
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6.QtWidgets import QMenu
from shiboken6 import isValid


class OwnedPlotWidget(pg.PlotWidget):
    """Keep Plot Options alive exactly as long as the owning plot widget."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        menu = self.getPlotItem().ctrlMenu
        if isinstance(menu, QMenu):
            # Preserve the Popup window type and all upstream actions.
            menu.setParent(self, menu.windowFlags())

    def close(self) -> None:
        item = self.getPlotItem()
        menu = item.ctrlMenu if item is not None else None
        flags = menu.windowFlags() if isinstance(menu, QMenu) and isValid(menu) else None
        if item is None:
            return
        try:
            # PlotItem.close() deliberately detaches the menu before clearing
            # the graphics scene. Do not interfere with its teardown order.
            super().close()
        finally:
            # The menu is no longer reachable through PlotItem.ctrlMenu.
            # Restore native ownership so deleting the plot also deletes it.
            # The caller may still hold a Python reference to the menu.
            if (
                isinstance(menu, QMenu)
                and flags is not None
                and isValid(menu)
                and isValid(self)
            ):
                menu.setParent(self, flags)
