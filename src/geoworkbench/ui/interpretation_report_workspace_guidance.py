from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.gas_context_event_editor import (
    GasContextEventEditorController,
    GasContextEventEditorError,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gas_context_event_dialog import GasContextEventDialog
from geoworkbench.ui.help_content import interpretation_guide_html
from geoworkbench.ui.help_pdf_layout_content import append_pdf_layout_help
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


def _interpretation_workspace_accessibility_stylesheet() -> str:
    """Final palette-aware readability layer for the interpretation workspace."""

    return """
    QWidget#interpretation-report-workspace {
        color: palette(window-text);
    }
    QWidget#interpretation-report-workspace QLabel {
        color: palette(window-text);
    }
    QWidget#interpretation-report-workspace QLabel#interpretation-section-heading,
    QWidget#interpretation-report-workspace QLabel#interpretation-page-subtitle,
    QWidget#interpretation-report-workspace QLabel#drilling-input-plan-status,
    QWidget#interpretation-report-workspace QLabel#dexp-quality-summary,
    QWidget#interpretation-report-workspace QLabel#dexp-quality-reasons,
    QWidget#interpretation-report-workspace QLabel#interpretation-export-label {
        color: palette(window-text);
    }

    QWidget#interpretation-report-workspace QPushButton {
        min-height: 36px;
        padding: 6px 12px;
        border: 1px solid palette(mid);
        border-radius: 8px;
        background: palette(button);
        color: palette(button-text);
        font-weight: 600;
    }
    QWidget#interpretation-report-workspace QPushButton:hover {
        background: palette(midlight);
        border-color: palette(highlight);
        color: palette(button-text);
    }
    QWidget#interpretation-report-workspace QPushButton:pressed,
    QWidget#interpretation-report-workspace QPushButton:checked {
        background: palette(highlight);
        border-color: palette(highlight);
        color: palette(highlighted-text);
    }
    QWidget#interpretation-report-workspace QPushButton:focus {
        border: 2px solid palette(highlight);
        padding: 5px 11px;
    }
    QWidget#interpretation-report-workspace QPushButton:disabled {
        background: palette(window);
        border-color: palette(mid);
        color: palette(mid);
    }
    QWidget#interpretation-report-workspace QPushButton[role="primary"],
    QWidget#interpretation-report-workspace QPushButton[uiRole="primary"] {
        min-height: 42px;
        background: palette(highlight);
        border-color: palette(highlight);
        color: palette(highlighted-text);
        font-weight: 700;
    }
    QWidget#interpretation-report-workspace QPushButton[role="secondary"],
    QWidget#interpretation-report-workspace QPushButton[uiRole="secondary"] {
        border-color: palette(highlight);
        background: palette(button);
        color: palette(button-text);
    }

    QPushButton#gas-context-event-editor-button {
        min-height: 52px;
        padding-left: 16px;
        padding-right: 12px;
        text-align: left;
        border-left: 4px solid palette(highlight);
        background: palette(button);
        color: palette(button-text);
        font-weight: 700;
    }
    QPushButton#gas-context-event-editor-button:hover {
        background: palette(midlight);
        border-color: palette(highlight);
        color: palette(button-text);
    }
    QPushButton#gas-context-event-editor-button:pressed {
        background: palette(highlight);
        color: palette(highlighted-text);
    }
    QPushButton#gas-context-event-editor-button:disabled {
        border-left-color: palette(mid);
    }

    QFrame#interpretation-workflow-card {
        border: 1px solid palette(mid);
        border-radius: 9px;
        background: palette(alternate-base);
    }
    QLabel#interpretation-workflow-title {
        border: none;
        background: transparent;
        color: palette(window-text);
        font-weight: 700;
    }
    QLabel#interpretation-workflow-steps {
        border: none;
        background: transparent;
        color: palette(window-text);
    }
    QToolButton#interpretation-workflow-help,
    QToolButton#interpretation-back-button,
    QToolButton#methodology-toggle,
    QToolButton#interpretation-log-toggle {
        min-height: 34px;
        padding: 6px 10px;
        border: 1px solid palette(mid);
        border-radius: 8px;
        background: palette(button);
        color: palette(button-text);
        font-weight: 600;
    }
    QToolButton#interpretation-workflow-help {
        min-height: 46px;
        border-left: 4px solid palette(highlight);
        text-align: left;
    }
    QToolButton#interpretation-workflow-help:hover,
    QToolButton#interpretation-back-button:hover,
    QToolButton#methodology-toggle:hover,
    QToolButton#interpretation-log-toggle:hover {
        background: palette(midlight);
        border-color: palette(highlight);
        color: palette(button-text);
    }
    QToolButton#interpretation-workflow-help:pressed,
    QToolButton#interpretation-back-button:pressed,
    QToolButton#methodology-toggle:pressed,
    QToolButton#interpretation-log-toggle:pressed,
    QToolButton#methodology-toggle:checked,
    QToolButton#interpretation-log-toggle:checked {
        background: palette(highlight);
        border-color: palette(highlight);
        color: palette(highlighted-text);
    }
    QToolButton#interpretation-workflow-guide {
        min-height: 32px;
        border: none;
        border-radius: 7px;
        padding: 4px 8px;
        color: palette(link);
        background: transparent;
        text-decoration: underline;
    }
    QToolButton#interpretation-workflow-guide:hover {
        background: palette(midlight);
        color: palette(window-text);
    }

    QWidget#interpretation-report-workspace QScrollBar:vertical {
        width: 14px;
        margin: 2px;
        border: none;
        background: transparent;
    }
    QWidget#interpretation-report-workspace QScrollBar::handle:vertical {
        min-height: 38px;
        margin: 1px;
        border: 1px solid palette(mid);
        border-radius: 6px;
        background: palette(mid);
    }
    QWidget#interpretation-report-workspace QScrollBar::handle:vertical:hover,
    QWidget#interpretation-report-workspace QScrollBar::handle:vertical:pressed {
        border-color: palette(highlight);
        background: palette(highlight);
    }
    QWidget#interpretation-report-workspace QScrollBar::add-line:vertical,
    QWidget#interpretation-report-workspace QScrollBar::sub-line:vertical {
        height: 0;
        border: none;
        background: transparent;
    }
    QWidget#interpretation-report-workspace QScrollBar::add-page:vertical,
    QWidget#interpretation-report-workspace QScrollBar::sub-page:vertical {
        background: transparent;
    }

    QWidget#interpretation-report-workspace QScrollBar:horizontal {
        height: 14px;
        margin: 2px;
        border: none;
        background: transparent;
    }
    QWidget#interpretation-report-workspace QScrollBar::handle:horizontal {
        min-width: 38px;
        margin: 1px;
        border: 1px solid palette(mid);
        border-radius: 6px;
        background: palette(mid);
    }
    QWidget#interpretation-report-workspace QScrollBar::handle:horizontal:hover,
    QWidget#interpretation-report-workspace QScrollBar::handle:horizontal:pressed {
        border-color: palette(highlight);
        background: palette(highlight);
    }
    QWidget#interpretation-report-workspace QScrollBar::add-line:horizontal,
    QWidget#interpretation-report-workspace QScrollBar::sub-line:horizontal {
        width: 0;
        border: none;
        background: transparent;
    }
    QWidget#interpretation-report-workspace QScrollBar::add-page:horizontal,
    QWidget#interpretation-report-workspace QScrollBar::sub-page:horizontal {
        background: transparent;
    }
    """


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
        self.workflow_guide_button: QToolButton | None = None
        self.workflow_title: QLabel | None = None
        self.workflow_steps: QLabel | None = None
        self.gas_context_button: QPushButton | None = None
        super().__init__(controller, parent, language=language)
        self._build_workflow_controls()
        self._retranslate_workflow_help()
        self._apply_prospective_ui_terms()

    def refresh(self) -> None:
        super().refresh()
        self._apply_prospective_ui_terms()

    def _build_workflow_controls(self) -> None:
        sidebar_layout = self.preview_sidebar.layout()
        if not isinstance(sidebar_layout, QVBoxLayout):
            raise RuntimeError("Не найден layout боковой панели предпросмотра")

        workflow_card = QFrame()
        workflow_card.setObjectName("interpretation-workflow-card")
        workflow_layout = QVBoxLayout(workflow_card)
        workflow_layout.setContentsMargins(10, 10, 10, 10)
        workflow_layout.setSpacing(6)
        self.workflow_title = QLabel()
        self.workflow_title.setObjectName("interpretation-workflow-title")
        self.workflow_steps = QLabel()
        self.workflow_steps.setObjectName("interpretation-workflow-steps")
        self.workflow_steps.setWordWrap(True)
        workflow_layout.addWidget(self.workflow_title)
        workflow_layout.addWidget(self.workflow_steps)
        sidebar_layout.insertWidget(0, workflow_card)

        button = _TopToolTipButton()
        button.setObjectName("interpretation-workflow-help")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(46)
        button.setProperty("toolTipPlacement", "above")
        button.clicked.connect(self._open_print_export)
        sidebar_layout.insertWidget(2, button)
        self.workflow_help_button = button

        guide = QToolButton()
        guide.setObjectName("interpretation-workflow-guide")
        guide.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        guide.setCursor(Qt.CursorShape.PointingHandCursor)
        guide.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        guide.setMinimumHeight(34)
        guide.clicked.connect(self._show_workflow_help)
        sidebar_layout.insertWidget(3, guide)
        self.workflow_guide_button = guide

        gas_context_button = QPushButton()
        gas_context_button.setObjectName("gas-context-event-editor-button")
        gas_context_button.clicked.connect(self._edit_gas_context_events)
        gas_context_button.setCursor(Qt.CursorShape.PointingHandCursor)
        gas_context_button.setMinimumHeight(52)
        gas_context_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        # Gas context is required before both standard Gas Ratio/Pixler and OPUS
        # interpretation, so keep its entry point outside mode-specific panels.
        sidebar_layout.insertWidget(1, gas_context_button)
        self.gas_context_button = gas_context_button

        button.setEnabled(self.print_button.isEnabled())
        self.setStyleSheet(
            self.styleSheet() + _interpretation_workspace_accessibility_stylesheet()
        )

    def _set_exports_enabled(self, enabled: bool) -> None:
        super()._set_exports_enabled(enabled)
        if self.workflow_help_button is not None:
            self.workflow_help_button.setEnabled(bool(enabled))

    def _retranslate_responsive_controls(self) -> None:
        super()._retranslate_responsive_controls()
        if self.workflow_help_button is not None:
            self._retranslate_workflow_help()
        self._apply_prospective_ui_terms()

    def _retranslate_workflow_help(self) -> None:
        button = self.workflow_help_button
        if button is None or self.workflow_title is None or self.workflow_steps is None:
            return
        self.workflow_title.setText(
            self._text("Порядок работы", "Жұмыс тәртібі", "Workflow")
        )
        self.workflow_steps.setText(
            self._text(
                "1. Проверьте газовые события\n"
                "2. Настройте входные данные\n"
                "3. Рассчитайте кривые\n"
                "4. Проверьте отчёт\n"
                "5. Напечатайте или экспортируйте",
                "1. Газ оқиғаларын тексеріңіз\n"
                "2. Кіріс деректерін баптаңыз\n"
                "3. Қисықтарды есептеңіз\n"
                "4. Есепті тексеріңіз\n"
                "5. Басып шығарыңыз немесе экспорттаңыз",
                "1. Review gas events\n"
                "2. Configure input data\n"
                "3. Calculate curves\n"
                "4. Review the report\n"
                "5. Print or export",
            )
        )
        button.setText(
            self._text(
                "5. Печать и экспорт",
                "5. Басып шығару және экспорт",
                "5. Print and export",
            )
        )
        tooltip = self._text(
            "Открыть готовый отчёт и перейти к кнопкам PDF, Word, Excel и печати.",
            "Дайын есепті ашып, PDF, Word, Excel және басып шығару батырмаларына өту.",
            "Open the prepared report and move to PDF, Word, Excel, and print actions.",
        )
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setAccessibleName(button.text())
        button.setAccessibleDescription(tooltip)

        guide = self.workflow_guide_button
        if guide is not None:
            guide.setText(self._text("Инструкция", "Нұсқаулық", "Instructions"))
            guide_tooltip = self._text(
                "Открыть пошаговую методику и пояснения по расчётам.",
                "Қадамдық әдістеме мен есептеу түсіндірмелерін ашу.",
                "Open the step-by-step method and calculation guidance.",
            )
            guide.setToolTip(guide_tooltip)
            guide.setAccessibleName(guide.text())
            guide.setAccessibleDescription(guide_tooltip)

        if self.gas_context_button is not None:
            self.gas_context_button.setText(
                self._text(
                    "1. Газовые события\nперед расчётом…",
                    "1. Есептеу алдындағы\nгаз оқиғалары…",
                    "1. Gas events before\ncalculation…",
                )
            )
            gas_context_tooltip = self._text(
                "Редактировать повторяющиеся интервалы: тип газа, глубины, TG/QC, "
                "confirmed/draft и влияние на интерпретацию.",
                "Қайталанатын аралықтарды өңдеу: газ түрі, тереңдіктер, TG/QC, "
                "confirmed/draft және интерпретацияға әсері.",
                "Edit repeated intervals: gas type, depths, TG/QC, confirmed/draft, "
                "and interpretation impact.",
            )
            self.gas_context_button.setToolTip(gas_context_tooltip)
            self.gas_context_button.setAccessibleName(self.gas_context_button.text())
            self.gas_context_button.setAccessibleDescription(gas_context_tooltip)

        self.normalized_actions_heading.setText(
            self._text("Расчёт и проверка", "Есептеу және тексеру", "Calculate and review")
        )
        self.configure_drilling_inputs_button.setText(
            self._text(
                "2. Настроить BIT и входные данные…",
                "2. BIT және кіріс деректерін баптау…",
                "2. Configure BIT and inputs…",
            )
        )
        self.recalculate_all_button.setText(
            self._text(
                "3. Рассчитать кривые и открыть планшет",
                "3. Қисықтарды есептеп, планшетті ашу",
                "3. Calculate curves and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "4. Обновить и проверить отчёт",
                "4. Есепті жаңартып, тексеру",
                "4. Refresh and review report",
            )
        )
        self.calculate_button.setText(
            self._text(
                "3. Рассчитать остальные методы",
                "3. Қалған әдістерді есептеу",
                "3. Calculate other methods",
            )
        )
        self.refresh_button.setText(
            self._text(
                "4. Обновить анализ",
                "4. Талдауды жаңарту",
                "4. Refresh analysis",
            )
        )

    def _edit_gas_context_events(self) -> None:
        try:
            controller = GasContextEventEditorController(self.controller.session)
        except GasContextEventEditorError:
            QMessageBox.warning(
                self,
                self._text(
                    "Газовые события",
                    "Газ оқиғалары",
                    "Gas events",
                ),
                self._text(
                    "Сначала выберите скважину для редактирования газовых событий.",
                    "Газ оқиғаларын өңдеу үшін алдымен ұңғыманы таңдаңыз.",
                    "Select a well before editing gas events.",
                ),
            )
            return
        dialog = GasContextEventDialog(
            controller,
            self,
            language=self.language,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _open_print_export(self) -> None:
        self.preview_toggle.setChecked(True)
        self.print_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _show_workflow_help(self) -> None:
        open_help_for_widget(self, "interpretation")

    def _workflow_help_html(self) -> str:
        """Compatibility accessor backed by the same content as the Help menu."""

        return append_pdf_layout_help(
            interpretation_guide_html(self.language),
            self.language,
        )

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
