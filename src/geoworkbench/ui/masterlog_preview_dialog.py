from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QToolTip, QVBoxLayout, QWidget

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_renderer import paint_masterlog
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_inspection import (
    MasterlogInspection,
    inspect_masterlog_point,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogPreviewWidget(QWidget):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        settings: MasterlogOutputSettings | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.template = template
        self.session = session
        self.settings = settings
        self.last_inspection: MasterlogInspection | None = None
        self.setMinimumSize(640, 480)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        paint_masterlog(
            painter,
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
            depth_range=self.settings.depth_range if self.settings is not None else None,
            language=(self.settings.language if self.settings is not None else AppLanguage.RU),
        )
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        language = self.settings.language if self.settings is not None else AppLanguage.RU
        self.last_inspection = inspect_masterlog_point(
            event.position(),
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
            depth_range=self.settings.depth_range if self.settings is not None else None,
            language=language,
        )
        if self.last_inspection is not None:
            QToolTip.showText(
                event.globalPosition().toPoint(),
                self.last_inspection.display_text(language),
                self,
            )
        super().mousePressEvent(event)


class MasterlogPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        settings: MasterlogOutputSettings | None = None,
    ) -> None:
        super().__init__(parent)
        localizer = Localizer.create(language)
        self.setWindowTitle(localizer.text("masterlog_preview.title", name=template.name))
        self.preview = MasterlogPreviewWidget(template, session, settings, self)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        self.resize(760, 600)
