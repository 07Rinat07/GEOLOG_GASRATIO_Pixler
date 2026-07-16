from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_renderer import paint_masterlog
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogPreviewWidget(QWidget):
    def __init__(
        self, template: MasterlogTemplate, session: ProjectSession, parent=None
    ) -> None:
        super().__init__(parent)
        self.template = template
        self.session = session
        self.setMinimumSize(640, 480)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        paint_masterlog(
            painter,
            QRectF(10.0, 10.0, float(self.width() - 20), float(self.height() - 20)),
            self.template,
            self.session,
        )
        painter.end()


class MasterlogPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        localizer = Localizer.create(language)
        self.setWindowTitle(localizer.text("masterlog_preview.title", name=template.name))
        self.preview = MasterlogPreviewWidget(template, session, self)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        self.resize(760, 600)
