from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
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
from geoworkbench.services.localization import AppLanguage
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

        button.setEnabled(self.print_button.isEnabled())
        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#interpretation-workflow-card {
                border: 1px solid palette(mid);
                border-radius: 7px;
                background: palette(alternate-base);
            }
            QLabel#interpretation-workflow-title {
                border: none;
                background: transparent;
                color: palette(text);
                font-weight: 700;
            }
            QLabel#interpretation-workflow-steps {
                border: none;
                background: transparent;
                color: palette(text);
                line-height: 1.35;
            }
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
            QToolButton#interpretation-workflow-help:disabled {
                color: palette(mid);
                border-left-color: palette(mid);
            }
            QToolButton#interpretation-workflow-guide {
                border: none;
                color: palette(link);
                background: transparent;
                text-decoration: underline;
            }
            QToolButton#interpretation-workflow-guide:hover {
                color: palette(highlight);
            }
            """
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
                "1. Настройте входные данные\n"
                "2. Рассчитайте кривые\n"
                "3. Проверьте отчёт\n"
                "4. Напечатайте или экспортируйте",
                "1. Кіріс деректерін баптаңыз\n"
                "2. Қисықтарды есептеңіз\n"
                "3. Есепті тексеріңіз\n"
                "4. Басып шығарыңыз немесе экспорттаңыз",
                "1. Configure input data\n"
                "2. Calculate curves\n"
                "3. Review the report\n"
                "4. Print or export",
            )
        )
        button.setText(
            self._text(
                "4. Печать и экспорт",
                "4. Басып шығару және экспорт",
                "4. Print and export",
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

        self.normalized_actions_heading.setText(
            self._text("Расчёт и проверка", "Есептеу және тексеру", "Calculate and review")
        )
        self.configure_drilling_inputs_button.setText(
            self._text(
                "1. Настроить BIT и входные данные…",
                "1. BIT және кіріс деректерін баптау…",
                "1. Configure BIT and inputs…",
            )
        )
        self.recalculate_all_button.setText(
            self._text(
                "2. Рассчитать кривые и открыть планшет",
                "2. Қисықтарды есептеп, планшетті ашу",
                "2. Calculate curves and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "3. Обновить и проверить отчёт",
                "3. Есепті жаңартып, тексеру",
                "3. Refresh and review report",
            )
        )
        self.calculate_button.setText(
            self._text(
                "2. Рассчитать остальные методы",
                "2. Қалған әдістерді есептеу",
                "2. Calculate other methods",
            )
        )
        self.refresh_button.setText(
            self._text(
                "3. Обновить анализ",
                "3. Талдауды жаңарту",
                "3. Refresh analysis",
            )
        )

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
