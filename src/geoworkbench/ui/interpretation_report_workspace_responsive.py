from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_compat import (
    InterpretationReportWorkspace as _CompatibleInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_CompatibleInterpretationReportWorkspace):
    """Responsive interpretation workspace with separated controls and report preview."""

    _TWO_COLUMN_BREAKPOINT = 1_280

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self._responsive_ready = False
        self._configuration_columns = 0
        super().__init__(controller, parent, language=language)
        self._build_responsive_workspace()
        self._apply_responsive_theme()
        self._responsive_ready = True
        self._retranslate_responsive_controls()
        self._set_methodology_visible(False)
        self._set_log_visible(False)
        self._relayout_configuration(force=True)

    def _build_responsive_workspace(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Не найден основной layout отчётов интерпретации")
        while root.count():
            root.takeAt(0)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        self._rebuild_normalized_panel()
        self._rebuild_dexp_panel()
        self._rebuild_settings_panel()

        self.page_header = QFrame()
        self.page_header.setObjectName("interpretation-page-header")
        header_layout = QHBoxLayout(self.page_header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(14)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        self.page_title = QLabel()
        self.page_title.setObjectName("interpretation-page-title")
        header_text.addWidget(self.page_title)
        self.explanation.setObjectName("interpretation-page-subtitle")
        self.explanation.setWordWrap(True)
        header_text.addWidget(self.explanation)
        header_layout.addLayout(header_text, 1)

        self.methodology_toggle = QToolButton()
        self.methodology_toggle.setObjectName("methodology-toggle")
        self.methodology_toggle.setCheckable(True)
        self.methodology_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.methodology_toggle.toggled.connect(self._set_methodology_visible)
        header_layout.addWidget(
            self.methodology_toggle,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        root.addWidget(self.page_header)

        self.methodology_panel = QFrame()
        self.methodology_panel.setObjectName("interpretation-methodology-panel")
        methodology_layout = QVBoxLayout(self.methodology_panel)
        methodology_layout.setContentsMargins(12, 10, 12, 10)
        methodology_layout.addWidget(self.calculation_inputs_help)
        root.addWidget(self.methodology_panel)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setObjectName("interpretation-main-splitter")
        self.main_splitter.setChildrenCollapsible(False)

        self.configuration_scroll = QScrollArea()
        self.configuration_scroll.setObjectName("interpretation-config-scroll")
        self.configuration_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.configuration_scroll.setWidgetResizable(True)
        self.configuration_scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.configuration_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.configuration_shell = QWidget()
        self.configuration_shell.setObjectName("interpretation-config-shell")
        shell_layout = QHBoxLayout(self.configuration_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.configuration_content = QWidget()
        self.configuration_content.setObjectName("interpretation-config-content")
        self.configuration_content.setMaximumWidth(1_480)
        self._configuration_grid = QGridLayout(self.configuration_content)
        self._configuration_grid.setContentsMargins(0, 0, 0, 0)
        self._configuration_grid.setHorizontalSpacing(12)
        self._configuration_grid.setVerticalSpacing(12)
        shell_layout.addWidget(self.configuration_content, 1)
        self.configuration_scroll.setWidget(self.configuration_shell)
        self.main_splitter.addWidget(self.configuration_scroll)

        self.report_panel = QFrame()
        self.report_panel.setObjectName("interpretation-report-panel")
        report_layout = QVBoxLayout(self.report_panel)
        report_layout.setContentsMargins(14, 12, 14, 12)
        report_layout.setSpacing(9)

        report_header = QHBoxLayout()
        report_header.setSpacing(10)
        self.report_title = QLabel()
        self.report_title.setObjectName("interpretation-report-title")
        report_header.addWidget(self.report_title)
        report_header.addStretch(1)
        self.log_toggle = QToolButton()
        self.log_toggle.setObjectName("interpretation-log-toggle")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.log_toggle.toggled.connect(self._set_log_visible)
        report_header.addWidget(self.log_toggle)
        report_layout.addLayout(report_header)

        self.log_panel = QFrame()
        self.log_panel.setObjectName("interpretation-log-panel")
        log_panel_layout = QVBoxLayout(self.log_panel)
        log_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.log_scroll = QScrollArea()
        self.log_scroll.setObjectName("interpretation-log-scroll")
        self.log_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setMaximumHeight(150)
        log_content = QWidget()
        log_content.setObjectName("interpretation-log-content")
        log_layout = QVBoxLayout(log_content)
        log_layout.setContentsMargins(10, 8, 10, 8)
        self.status.setObjectName("interpretation-status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        log_layout.addWidget(self.status)
        log_layout.addStretch(1)
        self.log_scroll.setWidget(log_content)
        log_panel_layout.addWidget(self.log_scroll)
        report_layout.addWidget(self.log_panel)

        self.preview.setMinimumHeight(260)
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        report_layout.addWidget(self.preview, 1)

        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        self.export_label = QLabel()
        self.export_label.setObjectName("interpretation-export-label")
        export_row.addWidget(self.export_label)
        export_row.addStretch(1)
        for button in (
            self.xlsx_button,
            self.docx_button,
            self.pdf_button,
            self.print_button,
        ):
            export_row.addWidget(button)
        report_layout.addLayout(export_row)

        self.main_splitter.addWidget(self.report_panel)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([430, 520])
        root.addWidget(self.main_splitter, 1)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _rebuild_normalized_panel(self) -> None:
        panel = self.normalized_gas_panel.layout()
        if not isinstance(panel, QVBoxLayout):
            raise RuntimeError("Не найден layout блока нормализованного газа")
        while panel.count():
            panel.takeAt(0)
        panel.setContentsMargins(16, 14, 16, 14)
        panel.setSpacing(10)
        self.normalized_gas_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        panel.addWidget(self.normalized_gas_title)

        mode_card = QFrame()
        mode_card.setObjectName("interpretation-inner-card")
        mode_layout = QGridLayout(mode_card)
        mode_layout.setContentsMargins(12, 10, 12, 10)
        mode_layout.setHorizontalSpacing(10)
        mode_layout.setVerticalSpacing(7)
        self.normalized_gas_mode.setMinimumWidth(0)
        self.normalized_gas_mode.setMinimumContentsLength(18)
        self.normalized_gas_mode.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        mode_layout.addWidget(self.normalized_gas_mode_label, 0, 0)
        mode_layout.addWidget(self.normalized_gas_mode, 0, 1)
        mode_layout.addWidget(self.normalized_gas_mode_help, 1, 0, 1, 2)
        mode_layout.setColumnStretch(1, 1)
        panel.addWidget(mode_card)

        panel.addWidget(self.normalized_source_heading)
        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(10)
        source_grid.setVerticalSpacing(8)
        source_grid.addWidget(self.server_curve_status, 0, 0)
        source_grid.addWidget(self.local_curve_status, 0, 1)
        source_grid.setColumnStretch(0, 1)
        source_grid.setColumnStretch(1, 1)
        panel.addLayout(source_grid)

        panel.addWidget(self.drilling_input_card)
        self.configure_drilling_inputs_button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        panel.addWidget(self.normalized_actions_heading)
        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(9)
        action_grid.setVerticalSpacing(9)
        action_grid.addWidget(self.recalculate_all_button, 0, 0, 1, 2)
        action_grid.addWidget(self.refresh_chart_report_button, 1, 0)
        action_grid.addWidget(self.calculate_normalized_gas_button, 1, 1)
        action_grid.addWidget(self.show_normalized_gas_button, 2, 0, 1, 2)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)
        for button in (
            self.recalculate_all_button,
            self.refresh_chart_report_button,
            self.calculate_normalized_gas_button,
            self.show_normalized_gas_button,
        ):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.addLayout(action_grid)

    def _rebuild_dexp_panel(self) -> None:
        panel = self.dexp_quality_panel.layout()
        if not isinstance(panel, QHBoxLayout):
            raise RuntimeError("Не найден layout блока качества DEXP")
        while panel.count():
            panel.takeAt(0)
        replacement = QVBoxLayout()
        replacement.setContentsMargins(16, 13, 16, 13)
        replacement.setSpacing(8)
        self.dexp_quality_panel.setLayout(replacement)
        self.dexp_quality_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        header = QHBoxLayout()
        header.addWidget(self.dexp_quality_title)
        header.addStretch(1)
        header.addWidget(self.dexp_details_button)
        replacement.addLayout(header)
        replacement.addWidget(self.dexp_quality_summary)
        replacement.addWidget(self.dexp_quality_progress)
        replacement.addWidget(self.dexp_quality_reasons)

    def _rebuild_settings_panel(self) -> None:
        panel = self.settings_panel.layout()
        if not isinstance(panel, QVBoxLayout):
            raise RuntimeError("Не найден layout панели параметров")
        while panel.count():
            panel.takeAt(0)
        panel.setContentsMargins(16, 14, 16, 14)
        panel.setSpacing(10)
        self.settings_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        panel.addWidget(self.settings_title)
        panel.addWidget(self.analysis_settings_card)
        panel.addWidget(self.reference_settings_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(9)
        action_row.addWidget(self.calculate_button)
        action_row.addWidget(self.refresh_button)
        action_row.addStretch(1)
        panel.addLayout(action_row)

    def _relayout_configuration(self, *, force: bool = False) -> None:
        columns = 2 if self.width() >= self._TWO_COLUMN_BREAKPOINT else 1
        if not force and columns == self._configuration_columns:
            return
        self._configuration_columns = columns
        while self._configuration_grid.count():
            self._configuration_grid.takeAt(0)

        if columns == 2:
            self.configuration_content.setMaximumWidth(1_480)
            self._configuration_grid.addWidget(self.normalized_gas_panel, 0, 0, 2, 1)
            self._configuration_grid.addWidget(self.settings_panel, 0, 1)
            self._configuration_grid.addWidget(self.dexp_quality_panel, 1, 1)
            self._configuration_grid.setColumnStretch(0, 3)
            self._configuration_grid.setColumnStretch(1, 2)
        else:
            self.configuration_content.setMaximumWidth(940)
            self._configuration_grid.addWidget(self.normalized_gas_panel, 0, 0)
            self._configuration_grid.addWidget(self.dexp_quality_panel, 1, 0)
            self._configuration_grid.addWidget(self.settings_panel, 2, 0)
            self._configuration_grid.setColumnStretch(0, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._responsive_ready:
            self._relayout_configuration()

    def refresh(self) -> None:
        super().refresh()
        if self._responsive_ready:
            self._update_log_toggle_state()

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if self._responsive_ready:
            self._retranslate_responsive_controls()

    def _set_methodology_visible(self, visible: bool) -> None:
        self.methodology_panel.setVisible(visible)
        self.methodology_toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )
        if self._responsive_ready:
            self._retranslate_responsive_controls()

    def _set_log_visible(self, visible: bool) -> None:
        self.log_panel.setVisible(visible)
        self.log_toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )
        if self._responsive_ready:
            self._retranslate_responsive_controls()

    def _update_log_toggle_state(self) -> None:
        has_text = bool(self.status.text().strip())
        self.log_toggle.setEnabled(has_text)
        if not has_text and self.log_toggle.isChecked():
            self.log_toggle.setChecked(False)

    def _retranslate_responsive_controls(self) -> None:
        self.page_title.setText(
            self._text(
                "Интерпретация газового каротажа",
                "Газ каротажын интерпретациялау",
                "Gas logging interpretation",
            )
        )
        self.explanation.setText(
            self._text(
                "Расчёт кривых, контроль качества DEXP и подготовка отчёта по текущей скважине.",
                "Қисықтарды есептеу, DEXP сапасын бақылау және ағымдағы ұңғыма бойынша есеп дайындау.",
                "Calculate curves, review DEXP quality, and prepare the current-well report.",
            )
        )
        self.methodology_toggle.setText(
            self._text(
                "Скрыть методику" if self.methodology_panel.isVisible() else "Показать методику",
                "Әдістемені жасыру" if self.methodology_panel.isVisible() else "Әдістемені көрсету",
                "Hide methodology" if self.methodology_panel.isVisible() else "Show methodology",
            )
        )
        self.report_title.setText(
            self._text(
                "Предварительный просмотр отчёта",
                "Есепті алдын ала қарау",
                "Report preview",
            )
        )
        self.log_toggle.setText(
            self._text(
                "Скрыть журнал" if self.log_panel.isVisible() else "Показать журнал расчёта",
                "Журналды жасыру" if self.log_panel.isVisible() else "Есептеу журналын көрсету",
                "Hide log" if self.log_panel.isVisible() else "Show calculation log",
            )
        )
        self.export_label.setText(
            self._text("Экспорт:", "Экспорт:", "Export:")
        )
        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать всё и открыть планшет",
                "Барлығын қайта есептеп, планшетті ашу",
                "Recalculate all and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "Обновить отчёт и графики",
                "Есеп пен графиктерді жаңарту",
                "Refresh report and charts",
            )
        )
        self.configure_drilling_inputs_button.setText(
            self._text(
                "Настроить BIT и входные данные…",
                "BIT және кіріс деректерін баптау…",
                "Configure BIT and inputs…",
            )
        )
        self._update_log_toggle_state()

    def _apply_responsive_theme(self) -> None:
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if dark:
            background = "#12171d"
            panel = "#1b222a"
            inner = "#222b35"
            field = "#151b22"
            border = "#34414f"
            text = "#f4f7fb"
            muted = "#aeb9c6"
            accent = "#4f9cf9"
            accent_hover = "#6dadfb"
        else:
            background = "#edf2f7"
            panel = "#ffffff"
            inner = "#f7f9fc"
            field = "#ffffff"
            border = "#ccd6e2"
            text = "#172033"
            muted = "#617083"
            accent = "#2563b8"
            accent_hover = "#1e73cf"

        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QWidget#interpretation-report-workspace {{
                background: {background};
                color: {text};
            }}
            QFrame#interpretation-page-header,
            QFrame#normalized-gas-panel,
            QFrame#dexp-quality-panel,
            QFrame#interpretation-settings-panel,
            QFrame#interpretation-report-panel {{
                background: {panel};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QFrame#interpretation-page-header {{
                border-left: 4px solid {accent};
            }}
            QFrame#interpretation-methodology-panel,
            QFrame#interpretation-log-panel {{
                background: {inner};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#interpretation-inner-card {{
                background: {inner};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QWidget#interpretation-config-shell,
            QWidget#interpretation-config-content,
            QWidget#interpretation-log-content,
            QScrollArea#interpretation-config-scroll,
            QScrollArea#interpretation-log-scroll {{
                background: transparent;
                border: none;
            }}
            QLabel#interpretation-page-title {{
                color: {text};
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#interpretation-page-subtitle,
            QLabel#interpretation-status,
            QLabel#interpretation-export-label {{
                color: {muted};
            }}
            QLabel#interpretation-report-title {{
                color: {text};
                font-size: 15px;
                font-weight: 700;
            }}
            QToolButton#methodology-toggle,
            QToolButton#interpretation-log-toggle {{
                min-height: 30px;
                color: {muted};
                background: {inner};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 3px 9px;
                font-weight: 600;
            }}
            QToolButton#methodology-toggle:hover,
            QToolButton#interpretation-log-toggle:hover {{
                color: {text};
                border-color: {accent};
            }}
            QToolButton#interpretation-log-toggle:disabled {{
                color: {border};
            }}
            QSplitter#interpretation-main-splitter::handle {{
                height: 8px;
                background: {background};
            }}
            QWidget#interpretation-report-workspace QPushButton[role="primary"] {{
                background: {accent};
                border-color: {accent};
                color: white;
            }}
            QWidget#interpretation-report-workspace QPushButton[role="primary"]:hover {{
                background: {accent_hover};
                border-color: {accent_hover};
            }}
            QTextBrowser#hydrocarbon-interpretation-preview {{
                color: {text};
                background: {field};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            """
        )


__all__ = ["InterpretationReportWorkspace"]
