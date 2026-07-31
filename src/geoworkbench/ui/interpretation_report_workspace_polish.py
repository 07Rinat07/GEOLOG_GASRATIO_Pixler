from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.interpretation_calculation_diagnostics import (
    DexpCoverageDiagnostic,
    diagnose_dexp_coverage,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_drilling import (
    InterpretationReportWorkspace as _DrillingInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_DrillingInterpretationReportWorkspace):
    """Structured interpretation workspace with visible hierarchy and DEXP diagnostics."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self._polish_ready = False
        self._last_dexp_diagnostic: DexpCoverageDiagnostic | None = None
        super().__init__(controller, parent, language=language)
        self._rebuild_page_layout()
        self._decorate_actions()
        self._apply_polished_theme()
        self._polish_ready = True
        self._retranslate_polish_controls()
        self._update_dexp_diagnostics()

    def _rebuild_page_layout(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Не найден основной layout отчётов интерпретации")
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # The legacy form and its action row are replaced by two compact cards.
        root.takeAt(3)
        root.takeAt(3)
        explanation_item = root.takeAt(0)
        help_item = root.takeAt(0)
        if explanation_item is None or help_item is None:
            raise RuntimeError("Не найдены вводные элементы страницы интерпретации")
        explanation = explanation_item.widget()
        help_label = help_item.widget()
        if explanation is None or help_label is None:
            raise RuntimeError("Не найдены вводные элементы страницы интерпретации")

        self.intro_panel = QFrame()
        self.intro_panel.setObjectName("interpretation-intro-panel")
        intro_layout = QVBoxLayout(self.intro_panel)
        intro_layout.setContentsMargins(16, 12, 16, 12)
        intro_layout.setSpacing(6)
        self.explanation.setObjectName("interpretation-intro-title")
        intro_layout.addWidget(explanation)
        intro_layout.addWidget(help_label)
        root.insertWidget(0, self.intro_panel)

        self._rebuild_normalized_gas_panel()
        self._build_dexp_quality_panel()
        root.insertWidget(2, self.dexp_quality_panel)

        self._build_settings_panel()
        root.insertWidget(3, self.settings_panel)

        self.status.setObjectName("interpretation-status")
        self.preview.setMinimumHeight(260)

    def _rebuild_normalized_gas_panel(self) -> None:
        panel = self.normalized_gas_panel.layout()
        if not isinstance(panel, QVBoxLayout):
            raise RuntimeError("Не найден layout блока нормализованного газа")
        while panel.count():
            panel.takeAt(0)
        panel.setContentsMargins(18, 14, 18, 14)
        panel.setSpacing(10)

        panel.addWidget(self.normalized_gas_title)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_row.addWidget(self.normalized_gas_mode_label)
        mode_row.addWidget(self.normalized_gas_mode, 1)
        panel.addLayout(mode_row)
        panel.addWidget(self.normalized_gas_mode_help)

        self.normalized_source_heading = QLabel()
        self.normalized_source_heading.setObjectName("interpretation-section-heading")
        panel.addWidget(self.normalized_source_heading)
        source_row = QHBoxLayout()
        source_row.setSpacing(10)
        source_row.addWidget(self.server_curve_status, 1)
        source_row.addWidget(self.local_curve_status, 1)
        panel.addLayout(source_row)

        self.drilling_input_card = QFrame()
        self.drilling_input_card.setObjectName("interpretation-inner-card")
        input_layout = QHBoxLayout(self.drilling_input_card)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(12)
        input_text_layout = QVBoxLayout()
        input_text_layout.setSpacing(3)
        self.drilling_inputs_heading = QLabel()
        self.drilling_inputs_heading.setObjectName("interpretation-section-heading")
        input_text_layout.addWidget(self.drilling_inputs_heading)
        input_text_layout.addWidget(self.drilling_input_status)
        input_layout.addLayout(input_text_layout, 1)
        input_layout.addWidget(self.configure_drilling_inputs_button)
        panel.addWidget(self.drilling_input_card)

        self.normalized_actions_heading = QLabel()
        self.normalized_actions_heading.setObjectName("interpretation-section-heading")
        panel.addWidget(self.normalized_actions_heading)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(10)
        primary_actions.addWidget(self.recalculate_all_button, 2)
        primary_actions.addWidget(self.refresh_chart_report_button, 1)
        panel.addLayout(primary_actions)

        secondary_actions = QHBoxLayout()
        secondary_actions.setSpacing(10)
        secondary_actions.addWidget(self.calculate_normalized_gas_button)
        secondary_actions.addWidget(self.show_normalized_gas_button)
        secondary_actions.addStretch(1)
        panel.addLayout(secondary_actions)

    def _build_dexp_quality_panel(self) -> None:
        self.dexp_quality_panel = QFrame()
        self.dexp_quality_panel.setObjectName("dexp-quality-panel")
        self.dexp_quality_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout = QHBoxLayout(self.dexp_quality_panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(18)

        coverage_column = QVBoxLayout()
        coverage_column.setSpacing(5)
        self.dexp_quality_title = QLabel()
        self.dexp_quality_title.setObjectName("dexp-quality-title")
        coverage_column.addWidget(self.dexp_quality_title)
        self.dexp_quality_summary = QLabel()
        self.dexp_quality_summary.setObjectName("dexp-quality-summary")
        self.dexp_quality_summary.setWordWrap(True)
        coverage_column.addWidget(self.dexp_quality_summary)
        self.dexp_quality_progress = QProgressBar()
        self.dexp_quality_progress.setObjectName("dexp-quality-progress")
        self.dexp_quality_progress.setRange(0, 1_000)
        self.dexp_quality_progress.setTextVisible(False)
        self.dexp_quality_progress.setMaximumHeight(8)
        coverage_column.addWidget(self.dexp_quality_progress)
        layout.addLayout(coverage_column, 3)

        reason_column = QVBoxLayout()
        reason_column.setSpacing(6)
        self.dexp_quality_reasons = QLabel()
        self.dexp_quality_reasons.setObjectName("dexp-quality-reasons")
        self.dexp_quality_reasons.setWordWrap(True)
        reason_column.addWidget(self.dexp_quality_reasons)
        self.dexp_details_button = QPushButton()
        self.dexp_details_button.setObjectName("dexp-details-button")
        self.dexp_details_button.clicked.connect(self._show_dexp_details)
        reason_column.addWidget(self.dexp_details_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(reason_column, 2)

    def _build_settings_panel(self) -> None:
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("interpretation-settings-panel")
        panel_layout = QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(16, 12, 16, 12)
        panel_layout.setSpacing(10)

        self.settings_title = QLabel()
        self.settings_title.setObjectName("interpretation-panel-title")
        panel_layout.addWidget(self.settings_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.analysis_settings_card = QFrame()
        self.analysis_settings_card.setObjectName("interpretation-inner-card")
        analysis_layout = QVBoxLayout(self.analysis_settings_card)
        analysis_layout.setContentsMargins(12, 10, 12, 10)
        analysis_layout.setSpacing(7)
        self.analysis_settings_title = QLabel()
        self.analysis_settings_title.setObjectName("interpretation-section-heading")
        analysis_layout.addWidget(self.analysis_settings_title)
        analysis_form = QFormLayout()
        analysis_form.setSpacing(7)
        analysis_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        analysis_form.addRow(self.report_mode_label, self.report_mode)
        analysis_form.addRow(self.normal_density_label, self.normal_density)
        analysis_form.addRow(self.threshold_label, self.threshold)
        analysis_layout.addLayout(analysis_form)
        grid.addWidget(self.analysis_settings_card, 0, 0)

        self.reference_settings_card = QFrame()
        self.reference_settings_card.setObjectName("interpretation-inner-card")
        reference_layout = QVBoxLayout(self.reference_settings_card)
        reference_layout.setContentsMargins(12, 10, 12, 10)
        reference_layout.setSpacing(7)
        self.reference_settings_title = QLabel()
        self.reference_settings_title.setObjectName("interpretation-section-heading")
        reference_layout.addWidget(self.reference_settings_title)
        reference_layout.addWidget(self.normalized_gas_reference_note)
        reference_form = QFormLayout()
        reference_form.setSpacing(7)
        reference_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        reference_form.addRow(self.rop_reference_label, self.rop_reference)
        reference_form.addRow(self.bit_reference_label, self.bit_reference)
        reference_form.addRow(self.flow_reference_label, self.flow_reference)
        reference_form.addRow(self.gas_efficiency_label, self.gas_efficiency)
        reference_layout.addLayout(reference_form)
        grid.addWidget(self.reference_settings_card, 0, 1)
        panel_layout.addLayout(grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.calculate_button)
        action_row.addWidget(self.refresh_button)
        action_row.addStretch(1)
        panel_layout.addLayout(action_row)

    def _decorate_actions(self) -> None:
        role_map = {
            self.recalculate_all_button: "primary",
            self.refresh_chart_report_button: "secondary",
            self.calculate_normalized_gas_button: "secondary",
            self.show_normalized_gas_button: "ghost",
            self.configure_drilling_inputs_button: "ghost",
            self.calculate_button: "secondary",
            self.refresh_button: "ghost",
            self.dexp_details_button: "ghost",
            self.xlsx_button: "ghost",
            self.docx_button: "ghost",
            self.pdf_button: "ghost",
            self.print_button: "ghost",
        }
        for button, role in role_map.items():
            button.setProperty("role", role)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        style = self.style()
        icon_map = {
            self.recalculate_all_button: QStyle.StandardPixmap.SP_BrowserReload,
            self.refresh_chart_report_button: QStyle.StandardPixmap.SP_FileDialogDetailedView,
            self.calculate_normalized_gas_button: QStyle.StandardPixmap.SP_DialogApplyButton,
            self.show_normalized_gas_button: QStyle.StandardPixmap.SP_ComputerIcon,
            self.configure_drilling_inputs_button: QStyle.StandardPixmap.SP_FileDialogContentsView,
            self.calculate_button: QStyle.StandardPixmap.SP_DialogApplyButton,
            self.refresh_button: QStyle.StandardPixmap.SP_BrowserReload,
            self.dexp_details_button: QStyle.StandardPixmap.SP_DialogHelpButton,
            self.xlsx_button: QStyle.StandardPixmap.SP_DialogSaveButton,
            self.docx_button: QStyle.StandardPixmap.SP_DialogSaveButton,
            self.pdf_button: QStyle.StandardPixmap.SP_DialogSaveButton,
            self.print_button: QStyle.StandardPixmap.SP_FileDialogDetailedView,
        }
        for button, icon in icon_map.items():
            button.setIcon(style.standardIcon(icon))
            button.setIconSize(QSize(16, 16))

    def _apply_polished_theme(self) -> None:
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if dark:
            background = "#15191f"
            panel = "#1e242c"
            card = "#252c35"
            field = "#171c22"
            border = "#3a4451"
            text = "#f3f6fa"
            muted = "#b4bec9"
            accent = "#4f9cff"
            accent_hover = "#6aaaff"
            accent_pressed = "#3b83db"
            success = "#42b883"
            warning = "#d9a441"
            disabled = "#717b87"
        else:
            background = "#edf2f7"
            panel = "#ffffff"
            card = "#f7f9fc"
            field = "#ffffff"
            border = "#c8d2df"
            text = "#172033"
            muted = "#5d6a78"
            accent = "#2563b8"
            accent_hover = "#1d73d2"
            accent_pressed = "#194f91"
            success = "#21865b"
            warning = "#a46a00"
            disabled = "#8a96a3"

        self.setStyleSheet(
            f"""
            QWidget#interpretation-report-workspace {{
                background-color: {background};
                color: {text};
            }}
            QWidget#interpretation-report-workspace QLabel {{
                color: {text};
                background: transparent;
                border: none;
            }}
            QFrame#interpretation-intro-panel,
            QFrame#normalized-gas-panel,
            QFrame#dexp-quality-panel,
            QFrame#interpretation-settings-panel {{
                background-color: {panel};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QFrame#interpretation-intro-panel {{
                border-left: 4px solid {accent};
            }}
            QFrame#interpretation-inner-card {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#interpretation-intro-title,
            QLabel#normalized-gas-title,
            QLabel#dexp-quality-title,
            QLabel#interpretation-panel-title {{
                color: {text};
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#interpretation-section-heading {{
                color: {muted};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#calculation-input-help,
            QLabel#normalized-gas-mode-help {{
                color: {muted};
                background-color: {card};
                border: 1px solid {border};
                border-radius: 7px;
                padding: 8px 10px;
            }}
            QLabel#normalized-gas-source-status {{
                min-height: 36px;
                color: {text};
                background-color: {card};
                border: 1px solid {border};
                border-radius: 7px;
                padding: 8px 10px;
            }}
            QLabel#drilling-input-plan-status,
            QLabel#dexp-quality-summary,
            QLabel#dexp-quality-reasons {{
                color: {muted};
            }}
            QLabel#interpretation-status {{
                color: {text};
                background-color: {card};
                border: 1px solid {border};
                border-radius: 7px;
                padding: 8px 10px;
            }}
            QWidget#interpretation-report-workspace QDoubleSpinBox,
            QWidget#interpretation-report-workspace QComboBox {{
                min-height: 32px;
                color: {text};
                background-color: {field};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 2px 8px;
                selection-color: white;
                selection-background-color: {accent};
            }}
            QWidget#interpretation-report-workspace QDoubleSpinBox:hover,
            QWidget#interpretation-report-workspace QComboBox:hover {{
                border-color: {accent};
            }}
            QWidget#interpretation-report-workspace QDoubleSpinBox:focus,
            QWidget#interpretation-report-workspace QComboBox:focus {{
                border: 2px solid {accent};
            }}
            QWidget#interpretation-report-workspace QComboBox QAbstractItemView {{
                color: {text};
                background-color: {panel};
                border: 1px solid {border};
                selection-color: white;
                selection-background-color: {accent};
                outline: 0;
            }}
            QWidget#interpretation-report-workspace QPushButton {{
                min-height: 34px;
                color: {text};
                background-color: {card};
                border: 1px solid {border};
                border-radius: 7px;
                padding: 4px 13px;
                font-weight: 600;
            }}
            QWidget#interpretation-report-workspace QPushButton:hover {{
                border-color: {accent};
                background-color: {panel};
            }}
            QWidget#interpretation-report-workspace QPushButton:pressed {{
                background-color: {field};
            }}
            QWidget#interpretation-report-workspace QPushButton:disabled {{
                color: {disabled};
                background-color: {background};
                border-color: {border};
            }}
            QWidget#interpretation-report-workspace QPushButton[role="primary"] {{
                min-height: 40px;
                color: white;
                background-color: {accent};
                border-color: {accent};
                font-weight: 700;
            }}
            QWidget#interpretation-report-workspace QPushButton[role="primary"]:hover {{
                background-color: {accent_hover};
                border-color: {accent_hover};
            }}
            QWidget#interpretation-report-workspace QPushButton[role="primary"]:pressed {{
                background-color: {accent_pressed};
                border-color: {accent_pressed};
            }}
            QWidget#interpretation-report-workspace QPushButton[role="secondary"] {{
                border-color: {accent};
            }}
            QWidget#interpretation-report-workspace QPushButton[role="ghost"] {{
                color: {muted};
            }}
            QProgressBar#dexp-quality-progress {{
                background-color: {field};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar#dexp-quality-progress::chunk {{
                background-color: {accent};
                border-radius: 4px;
            }}
            QFrame#dexp-quality-panel[coverageLevel="good"] {{
                border-left: 4px solid {success};
            }}
            QFrame#dexp-quality-panel[coverageLevel="warning"] {{
                border-left: 4px solid {warning};
            }}
            QFrame#dexp-quality-panel[coverageLevel="poor"] {{
                border-left: 4px solid {accent};
            }}
            QTextBrowser#hydrocarbon-interpretation-preview {{
                color: {text};
                background-color: {field};
                border: 1px solid {border};
                border-radius: 8px;
                selection-color: white;
                selection-background-color: {accent};
            }}
            """
        )

    def refresh(self) -> None:
        super().refresh()
        if self._polish_ready:
            self._update_dexp_diagnostics()

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if self._polish_ready:
            self._retranslate_polish_controls()
            self._update_dexp_diagnostics()

    def _retranslate_polish_controls(self) -> None:
        self.normalized_source_heading.setText(
            self._text("Доступные кривые", "Қолжетімді қисықтар", "Available curves")
        )
        self.drilling_inputs_heading.setText(
            self._text("Входные данные бурения", "Бұрғылау кірістері", "Drilling inputs")
        )
        self.normalized_actions_heading.setText(
            self._text("Действия", "Әрекеттер", "Actions")
        )
        self.settings_title.setText(
            self._text(
                "Параметры отчёта и расчёта",
                "Есеп пен есептеу параметрлері",
                "Report and calculation settings",
            )
        )
        self.analysis_settings_title.setText(
            self._text("Интерпретация", "Интерпретация", "Interpretation")
        )
        self.reference_settings_title.setText(
            self._text("Эталонные условия", "Эталондық шарттар", "Reference conditions")
        )
        self.dexp_quality_title.setText(
            self._text("Качество кривой DEXP", "DEXP қисығының сапасы", "DEXP curve quality")
        )
        self.dexp_details_button.setText(
            self._text("Причины разрывов", "Үзіліс себептері", "Gap details")
        )

        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать всё и открыть планшет",
                "Барлығын қайта есептеп, планшетті ашу",
                "Recalculate all and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text("Обновить отчёт", "Есепті жаңарту", "Refresh report")
        )
        self.calculate_normalized_gas_button.setText(
            self._text(
                "Рассчитать локальный нормализованный газ",
                "Жергілікті нормаланған газды есептеу",
                "Calculate local normalized gas",
            )
        )
        self.show_normalized_gas_button.setText(
            self._text(
                "Показать кривые на планшете",
                "Қисықтарды планшетте көрсету",
                "Show curves on tablet",
            )
        )
        self.configure_drilling_inputs_button.setText(
            self._text(
                "Настроить входные данные…",
                "Кіріс деректерін баптау…",
                "Configure inputs…",
            )
        )

        self.recalculate_all_button.setToolTip(
            self._text(
                "Проверить входные кривые, пересчитать газовые методы и DEXP, обновить "
                "дорожки и сразу открыть планшет.",
                "Кіріс қисықтарын тексеріп, газ әдістері мен DEXP-ті қайта есептеу, "
                "жолдарды жаңарту және планшетті ашу.",
                "Validate inputs, recalculate gas methods and DEXP, refresh tracks, and "
                "open the tablet.",
            )
        )
        self.refresh_chart_report_button.setToolTip(
            self._text(
                "Перестроить текст отчёта и графики по уже имеющимся кривым.",
                "Бар қисықтар бойынша есеп мәтіні мен графиктерді қайта құру.",
                "Rebuild the report text and charts from existing curves.",
            )
        )
        self.calculate_normalized_gas_button.setToolTip(
            self._text(
                "Пересчитать только локальные TG_NORM_CALC и C1–C5_NORM, не изменяя "
                "готовые серверные кривые.",
                "Дайын серверлік қисықтарды өзгертпей, тек жергілікті TG_NORM_CALC және "
                "C1–C5_NORM қисықтарын есептеу.",
                "Recalculate local TG_NORM_CALC and C1–C5_NORM only, preserving server curves.",
            )
        )
        self.show_normalized_gas_button.setToolTip(
            self._text(
                "Открыть планшет с доступными нормализованными газовыми кривыми.",
                "Қолжетімді нормаланған газ қисықтарымен планшетті ашу.",
                "Open the tablet with available normalized-gas curves.",
            )
        )
        self.configure_drilling_inputs_button.setToolTip(
            self._text(
                "Выбрать ROP, RPM, WOB, FLOW и BIT либо задать ручные значения и секции.",
                "ROP, RPM, WOB, FLOW және BIT таңдау немесе қолмен мәндер мен секциялар беру.",
                "Select ROP, RPM, WOB, FLOW, and BIT or define manual values and sections.",
            )
        )
        self.dexp_details_button.setToolTip(
            self._text(
                "Показать интервалы без DEXP и конкретные причины для каждой группы точек.",
                "DEXP жоқ аралықтарды және әр нүкте тобының нақты себептерін көрсету.",
                "Show DEXP gap intervals and the specific causes for each group of points.",
            )
        )

        self.rop_reference.setToolTip(
            self._text(
                "Эталонная скорость проходки для нормализации газа; это не фактический ROP.",
                "Газды нормалау үшін эталондық өту жылдамдығы; бұл нақты ROP емес.",
                "Reference penetration rate for gas normalization; this is not actual ROP.",
            )
        )
        self.bit_reference.setToolTip(
            self._text(
                "Эталонный диаметр для нормализации газа; фактический BIT задаётся отдельно.",
                "Газды нормалау диаметрі; нақты BIT бөлек беріледі.",
                "Reference diameter for gas normalization; actual BIT is configured separately.",
            )
        )
        self.flow_reference.setToolTip(
            self._text(
                "Эталонный расход для приведения газовых показаний к общим условиям.",
                "Газ көрсеткіштерін ортақ шарттарға келтіруге арналған эталондық шығын.",
                "Reference flow used to normalize gas readings to common conditions.",
            )
        )
        self.gas_efficiency.setToolTip(
            self._text(
                "Доля извлечения и регистрации газа от 0,01 до 1,00.",
                "Газды алу және тіркеу үлесі: 0,01-ден 1,00-ге дейін.",
                "Gas extraction and detection fraction from 0.01 to 1.00.",
            )
        )

        self.xlsx_button.setToolTip(
            self._text(
                "Экспортировать таблицы в Excel.",
                "Excel-ге экспорттау.",
                "Export tables to Excel.",
            )
        )
        self.docx_button.setToolTip(
            self._text(
                "Экспортировать отчёт в Word.",
                "Word-қа экспорттау.",
                "Export the report to Word.",
            )
        )
        self.pdf_button.setToolTip(
            self._text(
                "Экспортировать отчёт и графики в PDF.",
                "PDF-ке экспорттау.",
                "Export the report and charts to PDF.",
            )
        )
        self.print_button.setToolTip(
            self._text(
                "Открыть системный диалог печати.",
                "Басып шығару терезесін ашу.",
                "Open the system print dialog.",
            )
        )

    def _update_dexp_diagnostics(self) -> None:
        diagnostic = diagnose_dexp_coverage(self.controller)
        self._last_dexp_diagnostic = diagnostic
        if diagnostic.total_points <= 0:
            self.dexp_quality_progress.setValue(0)
            self.dexp_quality_summary.setText(
                self._text(
                    "Откройте набор данных, чтобы проверить покрытие DEXP.",
                    "DEXP қамтуын тексеру үшін деректер жинағын ашыңыз.",
                    "Open a dataset to inspect DEXP coverage.",
                )
            )
            self.dexp_quality_reasons.setText(
                self._text(
                    "Диагностика пока недоступна.",
                    "Диагностика әзірге қолжетімсіз.",
                    "Diagnostics are not available yet.",
                )
            )
            self.dexp_details_button.setEnabled(False)
            self._set_coverage_level("poor")
            return

        percent = diagnostic.coverage_percent
        self.dexp_quality_progress.setValue(int(round(percent * 10.0)))
        source = {
            "calculation": self._text(
                "локальный расчёт", "жергілікті есеп", "local calculation"
            ),
            "source": self._text("готовая кривая", "дайын қисық", "source curve"),
            "potential": self._text(
                "оценка по входам", "кірістер бойынша бағалау", "input-based estimate"
            ),
            "missing": self._text("не определён", "анықталмаған", "not defined"),
        }.get(diagnostic.curve_source, diagnostic.curve_source)
        percent_text = f"{percent:.1f}"
        if self.language in {AppLanguage.RU, AppLanguage.KK}:
            percent_text = percent_text.replace(".", ",")
        self.dexp_quality_summary.setText(
            self._text(
                f"Покрытие: {percent_text}% — {diagnostic.valid_points} из "
                f"{diagnostic.total_points} точек. Источник: {source}.",
                f"Қамту: {percent_text}% — {diagnostic.total_points} нүктенің "
                f"{diagnostic.valid_points} нүктесі. Дереккөз: {source}.",
                f"Coverage: {percent_text}% — {diagnostic.valid_points} of "
                f"{diagnostic.total_points} points. Source: {source}.",
            )
        )

        if diagnostic.missing_points == 0:
            reason_text = self._text(
                "Разрывов не найдено: кривая непрерывна на всей корректной глубинной оси.",
                "Үзілістер табылмады: қисық дұрыс тереңдік осінде үздіксіз.",
                "No gaps found: the curve is continuous across the valid depth axis.",
            )
        else:
            top_reasons = diagnostic.reason_counts[:3]
            details = ", ".join(
                f"{self._reason_text(code)} — {count}" for code, count in top_reasons
            )
            if not details:
                details = self._text(
                    "причина не определена",
                    "себеп анықталмаған",
                    "cause not identified",
                )
            reason_text = self._text(
                f"Пропущено точек: {diagnostic.missing_points}. Основные причины: {details}.",
                f"Өткізілген нүктелер: {diagnostic.missing_points}. Негізгі себептер: {details}.",
                f"Missing points: {diagnostic.missing_points}. Main causes: {details}.",
            )
        self.dexp_quality_reasons.setText(reason_text)
        self.dexp_details_button.setEnabled(
            bool(diagnostic.gap_intervals or diagnostic.resolution_messages)
        )
        level = "good" if percent >= 95.0 else "warning" if percent >= 70.0 else "poor"
        self._set_coverage_level(level)

    def _set_coverage_level(self, level: str) -> None:
        self.dexp_quality_panel.setProperty("coverageLevel", level)
        self.dexp_quality_panel.style().unpolish(self.dexp_quality_panel)
        self.dexp_quality_panel.style().polish(self.dexp_quality_panel)
        self.dexp_quality_panel.update()

    def _show_dexp_details(self) -> None:
        diagnostic = self._last_dexp_diagnostic
        if diagnostic is None or diagnostic.total_points <= 0:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._text(
                "Диагностика разрывов DEXP",
                "DEXP үзілістерін талдау",
                "DEXP gap diagnostics",
            )
        )
        dialog.resize(820, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        summary = QLabel(self.dexp_quality_summary.text())
        summary.setWordWrap(True)
        layout.addWidget(summary)

        if diagnostic.resolution_messages:
            resolution = QLabel("\n".join(f"• {item}" for item in diagnostic.resolution_messages))
            resolution.setWordWrap(True)
            layout.addWidget(resolution)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(
            (
                self._text("Интервал", "Аралық", "Interval"),
                self._text("Точек", "Нүкте", "Points"),
                self._text("Причины", "Себептер", "Reasons"),
            )
        )
        intervals = diagnostic.gap_intervals[:100]
        table.setRowCount(len(intervals))
        unit = f" {diagnostic.depth_unit}" if diagnostic.depth_unit else ""
        for row, gap in enumerate(intervals):
            interval = f"{gap.top:g}–{gap.bottom:g}{unit}"
            reasons = ", ".join(self._reason_text(code) for code in gap.reason_codes)
            table.setItem(row, 0, QTableWidgetItem(interval))
            table.setItem(row, 1, QTableWidgetItem(str(gap.point_count)))
            table.setItem(row, 2, QTableWidgetItem(reasons))
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, 1)

        if len(diagnostic.gap_intervals) > len(intervals):
            limit_note = QLabel(
                self._text(
                    "Показаны первые 100 интервалов.",
                    "Алғашқы 100 аралық көрсетілді.",
                    "The first 100 intervals are shown.",
                )
            )
            layout.addWidget(limit_note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _reason_text(self, code: str) -> str:
        texts = {
            "rop_missing": self._text("нет ROP", "ROP жоқ", "ROP missing"),
            "rop_nonpositive": self._text("ROP ≤ 0", "ROP ≤ 0", "ROP ≤ 0"),
            "rpm_missing": self._text("нет RPM", "RPM жоқ", "RPM missing"),
            "rpm_nonpositive": self._text("RPM ≤ 0", "RPM ≤ 0", "RPM ≤ 0"),
            "wob_missing": self._text("нет WOB", "WOB жоқ", "WOB missing"),
            "wob_nonpositive": self._text("WOB ≤ 0", "WOB ≤ 0", "WOB ≤ 0"),
            "bit_missing": self._text("нет BIT", "BIT жоқ", "BIT missing"),
            "bit_nonpositive": self._text("BIT ≤ 0", "BIT ≤ 0", "BIT ≤ 0"),
            "formula_singular": self._text(
                "вырожденный логарифм WOB/BIT",
                "WOB/BIT логарифмі анықталмаған",
                "singular WOB/BIT logarithm",
            ),
            "output_nonfinite": self._text(
                "пустое значение в готовой DEXP",
                "дайын DEXP ішіндегі бос мән",
                "non-finite value in the DEXP curve",
            ),
            "input_resolution": self._text(
                "не удалось определить входы",
                "кірістер анықталмады",
                "input resolution failed",
            ),
        }
        return texts.get(code, code)


__all__ = ["InterpretationReportWorkspace"]
