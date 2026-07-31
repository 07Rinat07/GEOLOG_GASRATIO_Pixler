from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.gas_mixture_ramp_report import GasMixtureRampReport
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_html_with_chart,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    InterpretationCalculationResult,
    NormalizedGasCalculationMode,
    NormalizedGasReference,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    set_normalized_gas_report_mode,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_legacy import (
    InterpretationReportWorkspace as _LegacyInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_LegacyInterpretationReportWorkspace):
    """Interpretation workspace with explicit recalculation, tablet, and chart actions."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self._expert_ready = False
        super().__init__(controller, parent, language=language)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._build_normalized_gas_panel()
        self._apply_opaque_theme()
        self._expert_ready = True
        self._retranslate_expert_controls()
        self._apply_normalized_gas_mode()
        self.refresh()

    def _build_normalized_gas_panel(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Не найден основной layout отчётов интерпретации")

        self.normalized_gas_panel = QFrame()
        self.normalized_gas_panel.setObjectName("normalized-gas-panel")
        self.normalized_gas_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.normalized_gas_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        panel = QVBoxLayout(self.normalized_gas_panel)
        panel.setContentsMargins(14, 12, 14, 12)
        panel.setSpacing(8)

        self.normalized_gas_title = QLabel()
        self.normalized_gas_title.setObjectName("normalized-gas-title")
        panel.addWidget(self.normalized_gas_title)

        mode_row = QHBoxLayout()
        self.normalized_gas_mode_label = QLabel()
        self.normalized_gas_mode = QComboBox()
        self.normalized_gas_mode.setObjectName("normalizedGasMode")
        self.normalized_gas_mode.setMinimumWidth(520)
        self.normalized_gas_mode.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.normalized_gas_mode.setMinimumContentsLength(42)
        mode_row.addWidget(self.normalized_gas_mode_label)
        mode_row.addWidget(self.normalized_gas_mode, 1)
        panel.addLayout(mode_row)

        self.normalized_gas_mode_help = QLabel()
        self.normalized_gas_mode_help.setObjectName("normalized-gas-mode-help")
        self.normalized_gas_mode_help.setWordWrap(True)
        panel.addWidget(self.normalized_gas_mode_help)

        source_row = QHBoxLayout()
        self.server_curve_status = QLabel()
        self.server_curve_status.setObjectName("normalized-gas-source-status")
        self.server_curve_status.setWordWrap(True)
        self.local_curve_status = QLabel()
        self.local_curve_status.setObjectName("normalized-gas-source-status")
        self.local_curve_status.setWordWrap(True)
        source_row.addWidget(self.server_curve_status, 1)
        source_row.addWidget(self.local_curve_status, 1)
        panel.addLayout(source_row)

        primary_actions = QHBoxLayout()
        self.recalculate_all_button = QPushButton()
        self.recalculate_all_button.setObjectName("interpretation-recalculate-all")
        self.recalculate_all_button.clicked.connect(self.recalculate_all_and_open_tablet)
        self.refresh_chart_report_button = QPushButton()
        self.refresh_chart_report_button.setObjectName("interpretation-refresh-chart-report")
        self.refresh_chart_report_button.clicked.connect(self.refresh_report_with_charts)
        primary_actions.addWidget(self.recalculate_all_button)
        primary_actions.addWidget(self.refresh_chart_report_button)
        primary_actions.addStretch(1)
        panel.addLayout(primary_actions)

        normalized_actions = QHBoxLayout()
        self.calculate_normalized_gas_button = QPushButton()
        self.calculate_normalized_gas_button.setObjectName("normalized-gas-calculate")
        self.calculate_normalized_gas_button.clicked.connect(self.calculate_normalized_gas)
        self.show_normalized_gas_button = QPushButton()
        self.show_normalized_gas_button.setObjectName("normalized-gas-show")
        self.show_normalized_gas_button.clicked.connect(self.show_normalized_gas_on_tablet)
        normalized_actions.addWidget(self.calculate_normalized_gas_button)
        normalized_actions.addWidget(self.show_normalized_gas_button)
        normalized_actions.addStretch(1)
        panel.addLayout(normalized_actions)

        root.insertWidget(2, self.normalized_gas_panel)
        self.normalized_gas_mode.currentIndexChanged.connect(
            self._normalized_gas_mode_changed
        )

    def _apply_opaque_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget#interpretation-report-workspace {
                background: #f4f7fb;
                background-color: palette(window);
                color: palette(window-text);
            }
            QWidget#interpretation-report-workspace QLabel {
                color: palette(window-text);
                background-color: transparent;
            }
            QLabel#calculation-input-help,
            QLabel#normalized-gas-mode-help {
                padding: 8px 10px;
                color: palette(text);
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            QFrame#normalized-gas-panel {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
            QLabel#normalized-gas-title {
                border: none;
                font-size: 15px;
                font-weight: 700;
                color: palette(text);
            }
            QLabel#normalized-gas-source-status {
                min-height: 34px;
                padding: 7px 10px;
                color: palette(text);
                background-color: palette(alternate-base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            QWidget#interpretation-report-workspace QDoubleSpinBox,
            QWidget#interpretation-report-workspace QComboBox {
                min-height: 30px;
                padding: 2px 8px;
                color: palette(text);
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 5px;
                selection-color: palette(highlighted-text);
                selection-background-color: palette(highlight);
            }
            QWidget#interpretation-report-workspace QComboBox QAbstractItemView {
                color: palette(text);
                background-color: palette(base);
                border: 1px solid palette(mid);
                selection-color: palette(highlighted-text);
                selection-background-color: palette(highlight);
                outline: 0;
            }
            QWidget#interpretation-report-workspace QPushButton {
                min-height: 32px;
                padding: 4px 13px;
                color: palette(button-text);
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 5px;
            }
            QWidget#interpretation-report-workspace QPushButton:hover {
                border-color: palette(highlight);
            }
            QWidget#interpretation-report-workspace QPushButton:disabled {
                color: palette(mid);
                background-color: palette(window);
            }
            QPushButton#interpretation-recalculate-all,
            QPushButton#normalized-gas-calculate {
                min-height: 38px;
                font-weight: 700;
                color: palette(highlighted-text);
                background-color: palette(highlight);
                border-color: palette(highlight);
            }
            QTextBrowser#hydrocarbon-interpretation-preview {
                color: palette(text);
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
                selection-color: palette(highlighted-text);
                selection-background-color: palette(highlight);
            }
            """
        )

    def refresh(self) -> None:
        if not getattr(self, "_expert_ready", False):
            super().refresh()
            return

        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        super().refresh()

        mixture_mode = self._is_mixture_mode()
        has_dataset = self.controller.session.current_dataset is not None
        self.normalized_gas_panel.setEnabled(not mixture_mode)
        self.recalculate_all_button.setEnabled(has_dataset and not mixture_mode)
        self.refresh_chart_report_button.setEnabled(has_dataset and not mixture_mode)
        if mixture_mode:
            return

        local_enabled = mode is not NormalizedGasCalculationMode.SERVER
        for control in (
            self.normalized_gas_reference_note,
            self.rop_reference,
            self.bit_reference,
            self.flow_reference,
            self.gas_efficiency,
        ):
            control.setEnabled(local_enabled)
        self.calculate_normalized_gas_button.setEnabled(local_enabled and has_dataset)
        self.calculate_button.setText(
            self._text(
                "Рассчитать остальные методы",
                "Қалған әдістерді есептеу",
                "Calculate other methods",
            )
        )
        self._set_well_report_mode_label()
        self._update_normalized_curve_status()
        self._apply_chart_preview()

    def calculate_standard_methods(self) -> None:
        super().calculate_standard_methods()
        if self._expert_ready:
            self._update_normalized_curve_status()
            self._apply_chart_preview()

    def recalculate_all_and_open_tablet(self) -> None:
        density = self.normal_density.value()
        try:
            result = self.controller.calculate_standard_curves(
                normal_mud_density_ppg=density if density > 0.0 else None,
                normalized_gas_reference=self._normalized_reference(),
                normalized_gas_mode=self._current_normalized_gas_mode(),
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            self._show_normalized_error(str(exc))
            return

        self.calculation_completed.emit(result)
        self.refresh()
        self._set_combined_result_status(result)
        visible = tuple(
            dict.fromkeys(
                (
                    *result.track_curves.get("gas_ratio_pixler", ()),
                    *result.track_curves.get("normalized_gas", ()),
                    *result.track_curves.get("dexp", ()),
                )
            )
        )
        if visible:
            self._open_tablet()
        elif result.issues:
            self._show_result_warning(result)

    def refresh_report_with_charts(self) -> None:
        self.refresh()
        if self.report is None:
            return
        self.status.setText(
            self._text(
                "Отчёт и графики перестроены по текущим кривым.",
                "Есеп пен графиктер ағымдағы қисықтар бойынша қайта құрылды.",
                "The report and charts were rebuilt from the current curves.",
            )
        )

    def calculate_normalized_gas(self) -> None:
        mode = self._current_normalized_gas_mode()
        try:
            result = self.controller.calculate_normalized_gas(
                normalized_gas_reference=self._normalized_reference(),
                normalized_gas_mode=mode,
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            self._show_normalized_error(str(exc))
            return

        self.calculation_completed.emit(result)
        self.refresh()
        self._set_normalized_result_status(result)
        if not result.track_curves.get("normalized_gas") and result.issues:
            self._show_result_warning(result)

    def show_normalized_gas_on_tablet(self) -> None:
        try:
            result = self.controller.normalized_gas_track_result(
                self._current_normalized_gas_mode()
            )
        except RuntimeError as exc:
            self._show_normalized_error(str(exc))
            return
        curves = result.track_curves.get("normalized_gas", ())
        if not curves:
            self._set_normalized_result_status(result)
            self._show_result_warning(result)
            return

        self.calculation_completed.emit(result)
        self._open_tablet()
        self.status.setText(
            self._text(
                "На планшете показаны кривые: ",
                "Планшетте көрсетілген қисықтар: ",
                "Curves shown on the tablet: ",
            )
            + ", ".join(curves)
        )

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if self._expert_ready:
            self._retranslate_expert_controls()
            self._apply_normalized_gas_mode()
            self.refresh()

    def _apply_chart_preview(self) -> None:
        dataset = self.controller.session.current_dataset
        if self.report is None or dataset is None or self._is_mixture_mode():
            return
        self.preview.setHtml(
            hydrocarbon_interpretation_html_with_chart(
                self.report,
                dataset,
                self.language,
            )
        )

    def _export_pdf(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        if isinstance(report, GasMixtureRampReport):
            super()._export_pdf()
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        target = self._choose_target(".pdf", "PDF (*.pdf)")
        if target is None:
            return
        try:
            exported = export_hydrocarbon_interpretation_pdf(
                report,
                target,
                language=self.language,
                dataset=dataset,
                include_chart=True,
                overwrite=target.exists(),
            )
        except (OSError, FileExistsError, HydrocarbonInterpretationPdfError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _normalized_reference(self) -> NormalizedGasReference:
        return NormalizedGasReference(
            rop_ref_fph=self.rop_reference.value(),
            bit_ref_in=self.bit_reference.value(),
            flow_ref_gpm=self.flow_reference.value(),
            gas_system_efficiency=self.gas_efficiency.value(),
        )

    def _normalized_gas_mode_changed(self, _index: int) -> None:
        if not self._expert_ready:
            return
        self._apply_normalized_gas_mode()
        self.refresh()

    def _current_normalized_gas_mode(self) -> NormalizedGasCalculationMode:
        if not getattr(self, "_expert_ready", False):
            return NormalizedGasCalculationMode.COMPARE
        value = self.normalized_gas_mode.currentData()
        try:
            return NormalizedGasCalculationMode(str(value))
        except ValueError:
            return NormalizedGasCalculationMode.COMPARE

    def _retranslate_expert_controls(self) -> None:
        current = self._current_normalized_gas_mode()
        self.normalized_gas_mode.blockSignals(True)
        self.normalized_gas_mode.clear()
        self.normalized_gas_mode.addItem(
            self._text(
                "Сервер + локальный расчёт — сопоставить оба",
                "Сервер + жергілікті есеп — екеуін салыстыру",
                "Server + local calculation — compare both",
            ),
            NormalizedGasCalculationMode.COMPARE.value,
        )
        self.normalized_gas_mode.addItem(
            self._text(
                "Только серверная/файловая кривая",
                "Тек серверлік/файлдық қисық",
                "Server/file curve only",
            ),
            NormalizedGasCalculationMode.SERVER.value,
        )
        self.normalized_gas_mode.addItem(
            self._text(
                "Только локальный расчёт программы",
                "Тек бағдарламаның жергілікті есебі",
                "Local program calculation only",
            ),
            NormalizedGasCalculationMode.LOCAL.value,
        )
        index = self.normalized_gas_mode.findData(current.value)
        self.normalized_gas_mode.setCurrentIndex(max(0, index))
        self.normalized_gas_mode.blockSignals(False)

        self.normalized_gas_title.setText(
            self._text(
                "Нормализованный газ — источник, расчёт и кривые",
                "Нормаланған газ — дереккөз, есеп және қисықтар",
                "Normalized gas — source, calculation, and curves",
            )
        )
        self.normalized_gas_mode_label.setText(
            self._text("Режим отчёта:", "Есеп режимі:", "Report mode:")
        )
        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать все доступные кривые и открыть планшет",
                "Барлық қолжетімді қисықтарды қайта есептеп, планшетті ашу",
                "Recalculate all available curves and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "Обновить отчёт с графиками",
                "Графиктері бар есепті жаңарту",
                "Refresh report with charts",
            )
        )
        self.calculate_normalized_gas_button.setText(
            self._text(
                "Рассчитать только локальный нормализованный газ",
                "Тек жергілікті нормаланған газды есептеу",
                "Calculate local normalized gas only",
            )
        )
        self.show_normalized_gas_button.setText(
            self._text(
                "Показать нормализованные кривые на планшете",
                "Нормаланған қисықтарды планшетте көрсету",
                "Show normalized curves on tablet",
            )
        )
        self._set_well_report_mode_label()

    def _set_well_report_mode_label(self) -> None:
        index = self.report_mode.findData("well_text")
        if index >= 0:
            self.report_mode.setItemText(
                index,
                self._text(
                    "Интерпретация скважины — с графиками кривых",
                    "Ұңғыманы интерпретациялау — қисықтар графиктерімен",
                    "Well interpretation — with curve charts",
                ),
            )

    def _apply_normalized_gas_mode(self) -> None:
        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        text = {
            NormalizedGasCalculationMode.COMPARE: self._text(
                "Серверная кривая сохраняется без изменений. Локальная TG_NORM_CALC "
                "создаётся отдельно. Общая кнопка пересчитывает все доступные методы, "
                "добавляет дорожки на планшет и обновляет отчёт с графиками.",
                "Серверлік қисық өзгеріссіз сақталады. Жергілікті TG_NORM_CALC бөлек "
                "құрылады. Жалпы батырма барлық қолжетімді әдістерді қайта есептеп, "
                "планшет жолдарын және графиктері бар есепті жаңартады.",
                "The server curve is preserved. Local TG_NORM_CALC is stored separately. "
                "The main action recalculates all available methods, updates tablet tracks, "
                "and rebuilds the report with charts.",
            ),
            NormalizedGasCalculationMode.SERVER: self._text(
                "Используется только готовая серверная/файловая кривая. Локальный расчёт "
                "отключён, но остальные доступные методы и графики можно пересчитать.",
                "Тек дайын серверлік/файлдық қисық пайдаланылады. Жергілікті есеп өшірілген, "
                "бірақ басқа қолжетімді әдістер мен графиктерді қайта есептеуге болады.",
                "Only the ready server/file curve is used. Local calculation is disabled, "
                "but other available methods and charts can still be recalculated.",
            ),
            NormalizedGasCalculationMode.LOCAL: self._text(
                "TG_NORM_CALC рассчитывается по C1–C5, фактическим ROP, BIT и FLOW. При "
                "отсутствии входа программа покажет его имя отдельным предупреждением.",
                "TG_NORM_CALC C1–C5, нақты ROP, BIT және FLOW бойынша есептеледі. Кіріс "
                "болмаса, бағдарлама оның атауын жеке ескерту арқылы көрсетеді.",
                "TG_NORM_CALC is calculated from C1–C5 and actual ROP, BIT, and FLOW. "
                "Any missing input is named in a separate warning.",
            ),
        }[mode]
        self.normalized_gas_mode_help.setText(text)

    def _update_normalized_curve_status(self) -> None:
        try:
            server = self.controller.normalized_gas_track_result(
                NormalizedGasCalculationMode.SERVER
            ).track_curves["normalized_gas"]
            local = self.controller.normalized_gas_track_result(
                NormalizedGasCalculationMode.LOCAL
            ).track_curves["normalized_gas"]
            selected = self.controller.normalized_gas_track_result(
                self._current_normalized_gas_mode()
            ).track_curves["normalized_gas"]
        except RuntimeError:
            server = ()
            local = ()
            selected = ()

        self.server_curve_status.setText(self._curve_status_text("server", server))
        self.local_curve_status.setText(self._curve_status_text("local", local))
        self.show_normalized_gas_button.setEnabled(bool(selected))

    def _curve_status_text(self, source: str, curves: tuple[str, ...]) -> str:
        title = (
            self._text("Сервер/файл", "Сервер/файл", "Server/file")
            if source == "server"
            else self._text("Локальный расчёт", "Жергілікті есеп", "Local calculation")
        )
        if curves:
            return f"{title}: " + ", ".join(curves)
        return f"{title}: " + self._text(
            "кривые не найдены",
            "қисықтар табылмады",
            "no curves found",
        )

    def _set_combined_result_status(self, result: InterpretationCalculationResult) -> None:
        visible = tuple(
            dict.fromkeys(
                (
                    *result.track_curves.get("gas_ratio_pixler", ()),
                    *result.track_curves.get("normalized_gas", ()),
                    *result.track_curves.get("dexp", ()),
                )
            )
        )
        changed = ", ".join(result.changed) or self._text("нет", "жоқ", "none")
        shown = ", ".join(visible) or self._text("нет", "жоқ", "none")
        issues = "\n".join(f"• {issue.message}" for issue in result.issues)
        self.status.setText(
            self._text(
                f"Созданы/обновлены: {changed}. На планшет переданы: {shown}.",
                f"Құрылған/жаңартылған: {changed}. Планшетке берілген: {shown}.",
                f"Created/updated: {changed}. Sent to tablet: {shown}.",
            )
            + (f"\n{issues}" if issues else "")
        )

    def _set_normalized_result_status(
        self,
        result: InterpretationCalculationResult,
    ) -> None:
        curves = result.track_curves.get("normalized_gas", ())
        changed = result.changed
        issue_text = "\n".join(f"• {issue.message}" for issue in result.issues)
        if changed:
            message = self._text(
                "Рассчитаны и добавлены на планшет: ",
                "Есептеліп, планшетке қосылды: ",
                "Calculated and added to the tablet: ",
            ) + ", ".join(changed)
        elif curves:
            message = self._text(
                "Доступные кривые: ",
                "Қолжетімді қисықтар: ",
                "Available curves: ",
            ) + ", ".join(curves)
        else:
            message = self._text(
                "Кривые нормализованного газа не созданы.",
                "Нормаланған газ қисықтары жасалмады.",
                "No normalized-gas curves were created.",
            )
        self.status.setText(message + (f"\n{issue_text}" if issue_text else ""))
        self._update_normalized_curve_status()
        self._apply_chart_preview()

    def _show_result_warning(self, result: InterpretationCalculationResult) -> None:
        details = "\n".join(f"• {issue.message}" for issue in result.issues)
        if not details:
            details = self._text(
                "Подходящие кривые не найдены.",
                "Сәйкес қисықтар табылмады.",
                "No matching curves were found.",
            )
        QMessageBox.warning(
            self,
            self.tab_title(self.language),
            self._text(
                "Не все запрошенные кривые удалось построить:\n",
                "Сұралған қисықтардың барлығын құру мүмкін болмады:\n",
                "Not all requested curves could be built:\n",
            )
            + details,
        )

    def _open_tablet(self) -> None:
        window = self.window()
        tabs = getattr(window, "tabs", None)
        tablet = getattr(window, "tablet_view", None)
        if isinstance(tabs, QTabWidget) and isinstance(tablet, QWidget):
            tabs.setCurrentWidget(tablet)

    def _show_normalized_error(self, message: str) -> None:
        QMessageBox.critical(self, self.tab_title(self.language), message)


__all__ = ["InterpretationReportWorkspace"]
