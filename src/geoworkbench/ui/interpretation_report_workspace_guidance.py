from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QToolButton, QToolTip, QVBoxLayout, QWidget

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.help_content import interpretation_guide_html
from geoworkbench.ui.interpretation_report_workspace_layout import (
    InterpretationReportWorkspace as _LayoutWorkspace,
)
from geoworkbench.ui.navigation_organization import open_help_for_widget


class _TopToolTipButton(QToolButton):
    """Tool button whose delayed tooltip is anchored above the control."""

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and self.toolTip():
            anchor = self.mapToGlobal(QPoint(0, -84))
            QToolTip.showText(anchor, self.toolTip(), self, self.rect(), 12_000)
            event.accept()
            return True
        return super().event(event)


def _printer_icon(palette: QPalette) -> QIcon:
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ink = palette.color(QPalette.ColorRole.ButtonText)
        paper = palette.color(QPalette.ColorRole.Base)
        accent = palette.color(QPalette.ColorRole.Highlight)
        muted = palette.color(QPalette.ColorRole.Mid)

        painter.setPen(QPen(ink, 2.2))
        painter.setBrush(paper)
        painter.drawRoundedRect(QRectF(12.0, 2.0, 24.0, 21.0), 2.0, 2.0)

        painter.setBrush(ink)
        painter.drawRoundedRect(QRectF(5.0, 15.0, 38.0, 24.0), 4.0, 4.0)

        painter.setPen(QPen(ink, 2.0))
        painter.setBrush(paper)
        painter.drawRoundedRect(QRectF(10.0, 26.0, 28.0, 18.0), 2.0, 2.0)
        painter.setPen(QPen(muted, 1.4))
        painter.drawLine(15, 32, 33, 32)
        painter.drawLine(15, 36, 30, 36)
        painter.drawLine(15, 40, 27, 40)

        painter.setPen(QPen(accent, 1.0))
        painter.setBrush(QColor(accent))
        painter.drawEllipse(QRectF(33.0, 20.0, 4.5, 4.5))
    finally:
        painter.end()
    return QIcon(pixmap)


class InterpretationReportWorkspace(_LayoutWorkspace):
    """Interpretation workspace linked to the central three-language help centre."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self.workflow_help_button: QToolButton | None = None
        super().__init__(controller, parent, language=language)
        self._build_workflow_help_button()
        self._retranslate_workflow_help()
        self._apply_prospective_ui_terms()

    def refresh(self) -> None:
        super().refresh()
        self._apply_prospective_ui_terms()

    def _build_workflow_help_button(self) -> None:
        sidebar_layout = self.preview_sidebar.layout()
        if not isinstance(sidebar_layout, QVBoxLayout):
            raise RuntimeError("Не найден layout боковой панели предпросмотра")
        button = _TopToolTipButton()
        button.setObjectName("interpretation-workflow-help")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(_printer_icon(button.palette()))
        button.setIconSize(QSize(34, 34))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(58)
        button.setProperty("toolTipPlacement", "above")
        button.clicked.connect(self._show_workflow_help)
        sidebar_layout.insertWidget(1, button)
        self.workflow_help_button = button
        self.setStyleSheet(
            self.styleSheet()
            + """
            QToolButton#interpretation-workflow-help {
                border: 1px solid palette(mid);
                border-left: 4px solid palette(highlight);
                border-radius: 6px;
                padding: 7px 10px;
                color: palette(button-text);
                background: palette(button);
                font-weight: 600;
                text-align: left;
            }
            QToolButton#interpretation-workflow-help:hover {
                border-color: palette(highlight);
                background: palette(alternate-base);
            }
            """
        )

    def _retranslate_responsive_controls(self) -> None:
        super()._retranslate_responsive_controls()
        if self.workflow_help_button is not None:
            self._retranslate_workflow_help()
        self._apply_prospective_ui_terms()

    def _retranslate_workflow_help(self) -> None:
        button = self.workflow_help_button
        if button is None:
            return
        button.setText(
            self._text(
                "Настройка и печать",
                "Баптау және басып шығару",
                "Setup and printing",
            )
        )
        tooltip = self._text(
            "Пошаговая инструкция находится в разделе «Справка → Документация и инструкции».",
            "Қадамдық нұсқаулық «Анықтама → Құжаттама және нұсқаулықтар» бөлімінде.",
            "The step-by-step guide is in Help → Documentation and instructions.",
        )
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setAccessibleName(button.text())
        button.setAccessibleDescription(tooltip)

    def _show_workflow_help(self) -> None:
        open_help_for_widget(self, "interpretation")

    def _workflow_help_html(self) -> str:
        """Compatibility accessor backed by the same content as the Help menu."""

        return interpretation_guide_html(self.language)

    def _apply_prospective_ui_terms(self) -> None:
        replacements = {
            AppLanguage.RU: (
                ("Кандидаты не заменяют", "Перспективные интервалы не заменяют"),
                ("Кандидатных интервалов:", "Перспективных интервалов:"),
            ),
            AppLanguage.KK: (
                ("Кандидаттар геолог", "Перспективалы аралықтар геолог"),
                ("Кандидат аралықтар:", "Перспективалы аралықтар:"),
            ),
            AppLanguage.EN: (
                ("Candidates do not replace", "Prospective intervals do not replace"),
                ("Candidate intervals:", "Prospective intervals:"),
            ),
        }[self.language]
        for widget in (self.explanation, self.status):
            text = widget.text()
            for old, new in replacements:
                text = text.replace(old, new)
            widget.setText(text)
