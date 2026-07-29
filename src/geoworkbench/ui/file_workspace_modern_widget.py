from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.ui.file_workspace_redesign import (
    FileWorkspaceWidget as _RedesignedFileWorkspaceWidget,
)


class FileWorkspaceWidget(_RedesignedFileWorkspaceWidget):
    """Final modern Files workspace entry point.

    Kept as a thin entry class so the redesigned shell remains easy to replace
    or compare during acceptance testing without touching the service layer.
    """

    def _load_visible_page_icons(self) -> None:
        if self.document_service.kind is not DocumentKind.PDF:
            return
        count = self._page_list.count()
        if not count:
            return

        current = self.document_service.page_index
        indexes = {current}
        for offset in (1, 2):
            if current - offset >= 0:
                indexes.add(current - offset)
            if current + offset < count:
                indexes.add(current + offset)

        try:
            for page_index in sorted(indexes):
                self.document_service.set_page(page_index)
                rendered = self.document_service.render(0.18)
                pixmap = QPixmap()
                if not pixmap.loadFromData(rendered.payload):
                    continue
                thumbnail = pixmap.scaled(
                    QSize(72, 96),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item = self._page_list.item(page_index)
                if item is not None:
                    item.setIcon(QIcon(thumbnail))
        except DocumentError:
            pass
        finally:
            self.document_service.set_page(current)
