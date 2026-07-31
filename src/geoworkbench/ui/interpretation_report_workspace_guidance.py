from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_layout import (
    InterpretationReportWorkspace as _LayoutWorkspace,
)


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
    """Interpretation workspace with a visible setup and printing guide."""

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
            "Пошаговая инструкция: входные данные, расчёт, проверка DEXP, "
            "предпросмотр, сохранение и печать отчёта.",
            "Кіріс деректері, есептеу, DEXP тексеру, алдын ала қарау, сақтау "
            "және басып шығару бойынша нұсқаулық.",
            "Step-by-step guide for inputs, calculation, DEXP review, preview, "
            "saving, and printing.",
        )
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setAccessibleName(button.text())
        button.setAccessibleDescription(tooltip)

    def _show_workflow_help(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._text(
                "Как настроить и напечатать отчёт",
                "Есепті баптау және басып шығару",
                "How to set up and print the report",
            )
        )
        dialog.setModal(True)
        dialog.resize(760, 640)
        layout = QVBoxLayout(dialog)
        guide = QTextBrowser(dialog)
        guide.setObjectName("interpretation-workflow-help-text")
        guide.setHtml(self._workflow_help_html())
        layout.addWidget(guide, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText(self._text("Закрыть", "Жабу", "Close"))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _workflow_help_html(self) -> str:
        if self.language is AppLanguage.EN:
            return _english_guide()
        if self.language is AppLanguage.KK:
            return _kazakh_guide()
        return _russian_guide()

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


def _russian_guide() -> str:
    return """
    <h2>Порядок подготовки отчёта</h2>
    <ol>
      <li><b>Выберите скважину и набор данных.</b> Проверьте C1–C5, ROP,
          RPM, WOB, BIT/BS и FLOW. Для SLIDE желательно иметь забойный RPM.</li>
      <li><b>Выберите источник нормализованного газа:</b> сервер, локальный
          расчёт или сопоставление обеих кривых.</li>
      <li><b>Откройте «Настроить BIT и входные данные».</b> Заполните интервалы
          диаметров долота, проверьте единицы и отсутствие пропусков.</li>
      <li><b>Проверьте ROP_REF, BIT_REF, FLOW_REF и эффективность газовой
          системы.</b> Значения должны соответствовать методике заказчика.</li>
      <li><b>Нажмите «Пересчитать все доступные кривые»</b> и дождитесь
          завершения расчёта.</li>
      <li><b>Проверьте качество DEXP.</b> Откройте причины разрывов. SLIDE без
          забойного RPM оставляет обоснованный разрыв.</li>
      <li><b>Нажмите «Обновить отчёт с графиками»</b>, затем откройте слева
          «Предпросмотр отчёта».</li>
      <li><b>Проверьте графики, шкалы, единицы, абсолютные C1–C5 и
          перспективные интервалы.</b> Подтверждённые геологом интервалы
          заполняются вручную.</li>
      <li><b>Выберите Excel, Word или PDF.</b> Укажите папку и имя файла и не
          прерывайте операцию, пока индикатор подготовки не завершится.</li>
      <li><b>Для печати нажмите «Печать…»</b> либо откройте готовый PDF.
          Проверьте принтер, бумагу, ориентацию, поля и масштаб.</li>
    </ol>
    <p><b>Важно:</b> перспективные интервалы не заменяют заключение геолога.</p>
    """


def _kazakh_guide() -> str:
    return """
    <h2>Есепті дайындау тәртібі</h2>
    <ol>
      <li>Ұңғыманы таңдап, C1–C5, ROP, RPM, WOB, BIT/BS және FLOW тексеріңіз.</li>
      <li>Нормаланған газ көзін таңдаңыз және BIT/DEXP кірістерін баптаңыз.</li>
      <li>Эталондық мәндерді тексеріп, барлық қисықтарды қайта есептеңіз.</li>
      <li>DEXP сапасы мен SLIDE аралықтарындағы түптік RPM-ді тексеріңіз.</li>
      <li>Графиктері бар есепті жаңартып, алдын ала көріністі ашыңыз.</li>
      <li>Excel, Word немесе PDF сақтап, индикатор аяқталғанша күтіңіз.</li>
      <li>«Басып шығару…» түймесін немесе дайын PDF файлын пайдаланыңыз.</li>
    </ol>
    <p><b>Маңызды:</b> перспективалы аралықтар геолог қорытындысын алмастырмайды.</p>
    """


def _english_guide() -> str:
    return """
    <h2>Report preparation workflow</h2>
    <ol>
      <li>Select the well and check C1–C5, ROP, RPM, WOB, BIT/BS, and FLOW.</li>
      <li>Select the normalized-gas source and configure BIT/DEXP inputs.</li>
      <li>Verify reference values and recalculate all available curves.</li>
      <li>Review DEXP quality and downhole RPM availability during SLIDE.</li>
      <li>Refresh the report with charts and open the report preview.</li>
      <li>Save Excel, Word, or PDF and wait for the progress indicator.</li>
      <li>Use Print or open the completed PDF and verify print settings.</li>
    </ol>
    <p><b>Important:</b> prospective intervals do not replace a geologist's conclusion.</p>
    """


__all__ = ["InterpretationReportWorkspace"]
