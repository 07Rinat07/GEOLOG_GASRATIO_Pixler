from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
    """Report workspace with explicit server/local normalized-gas controls."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self._normalized_mode_ready = False
        super().__init__(controller, parent, language=language)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._build_normalized_gas_panel()
        self._apply_opaque_theme()
        self._normalized_mode_ready = True
        self._retranslate_normalized_gas_panel()
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

        actions = QHBoxLayout()
        self.calculate_normalized_gas_button = QPushButton()
        self.calculate_normalized_gas_button.setObjectName("normalized-gas-calculate")
        self.calculate_normalized_gas_button.clicked.connect(
            self.calculate_normalized_gas
        )
        self.show_normalized_gas_button = QPushButton()
        self.show_normalized_gas_button.setObjectName("normalized-gas-show")
        self.show_normalized_gas_button.clicked.connect(
            self.show_normalized_gas_on_tablet
        )
        actions.addWidget(self.calculate_normalized_gas_button)
        actions.addWidget(self.show_normalized_gas_button)
        actions.addStretch(1)
        panel.addLayout(actions)

        root.insertWidget(2, self.normalized_gas_panel)
        self.normalized_gas_mode.currentIndexChanged.connect(
            self._normalized_gas_mode_changed
        )

    def _apply_opaque_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget#interpretation-report-workspace {
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
            QPushButton#normalized-gas-calculate {
                min-height: 36px;
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
        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        super().refresh()
        if not self._normalized_mode_ready:
            return

        mixture_mode = self._is_mixture_mode()
        self.normalized_gas_panel.setEnabled(not mixture_mode)
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
        self.calculate_normalized_gas_button.setEnabled(
            local_enabled and self.controller.session.current_dataset is not None
        )
        self.calculate_button.setText(
            self._text(
                "Рассчитать остальные методы",
                "Қалған әдістерді есептеу",
                "Calculate other methods",
            )
        )
        self._update_normalized_curve_status()

    def calculate_standard_methods(self) -> None:
        super().calculate_standard_methods()
        if self._normalized_mode_ready:
            self._update_normalized_curve_status()

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
            return

        self.calculation_completed.emit(result)
        window = self.window()
        tabs = getattr(window, "tabs", None)
        tablet = getattr(window, "tablet_view", None)
        if isinstance(tabs, QTabWidget) and isinstance(tablet, QWidget):
            tabs.setCurrentWidget(tablet)
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
        if self._normalized_mode_ready:
            self._retranslate_normalized_gas_panel()
            self._apply_normalized_gas_mode()
            self.refresh()

    def _normalized_reference(self) -> NormalizedGasReference:
        return NormalizedGasReference(
            rop_ref_fph=self.rop_reference.value(),
            bit_ref_in=self.bit_reference.value(),
            flow_ref_gpm=self.flow_reference.value(),
            gas_system_efficiency=self.gas_efficiency.value(),
        )

    def _normalized_gas_mode_changed(self, _index: int) -> None:
        if not self._normalized_mode_ready:
            return
        self._apply_normalized_gas_mode()
        self.refresh()

    def _current_normalized_gas_mode(self) -> NormalizedGasCalculationMode:
        if not self._normalized_mode_ready:
            return NormalizedGasCalculationMode.COMPARE
        value = self.normalized_gas_mode.currentData()
        try:
            return NormalizedGasCalculationMode(str(value))
        except ValueError:
            return NormalizedGasCalculationMode.COMPARE

    def _retranslate_normalized_gas_panel(self) -> None:
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
            self._text(
                "Режим отчёта:",
                "Есеп режимі:",
                "Report mode:",
            )
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

    def _apply_normalized_gas_mode(self) -> None:
        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        text = {
            NormalizedGasCalculationMode.COMPARE: self._text(
                "Серверная кривая сохраняется без изменений. Кнопка ниже рассчитывает "
                "отдельную TG_NORM_CALC. В отчёте сопоставляются только совместимые total-gas "
                "ряды, а их интервалы независимо проверяются по ЛБА.",
                "Серверлік қисық өзгеріссіз сақталады. Төмендегі батырма TG_NORM_CALC "
                "қисығын бөлек есептейді. Есепте тек үйлесімді total-gas қатарлары салыстырылып, "
                "олардың аралықтары ЛБА бойынша жеке тексеріледі.",
                "The server curve is kept unchanged. The button below calculates a separate "
                "TG_NORM_CALC. The report compares only compatible total-gas series and checks "
                "their intervals against LBA independently.",
            ),
            NormalizedGasCalculationMode.SERVER: self._text(
                "Используется только готовая нормализованная кривая сервера/файла. "
                "Локальный расчёт отключён; кнопка показа открывает найденную серверную кривую.",
                "Тек сервердің/файлдың дайын нормаланған қисығы пайдаланылады. Жергілікті есеп "
                "өшірілген; көрсету батырмасы табылған серверлік қисықты ашады.",
                "Only the ready server/file normalized curve is used. Local calculation is "
                "disabled; the show button opens the detected server curve.",
            ),
            NormalizedGasCalculationMode.LOCAL: self._text(
                "Кнопка рассчитывает TG_NORM_CALC по C1–C5, ROP, BIT и FLOW. Серверная кривая "
                "остаётся в наборе, но не участвует в текущем отчёте.",
                "Батырма TG_NORM_CALC қисығын C1–C5, ROP, BIT және FLOW бойынша есептейді. "
                "Серверлік қисық жинақта қалады, бірақ ағымдағы есепке қатыспайды.",
                "The button calculates TG_NORM_CALC from C1–C5, ROP, BIT, and FLOW. The server "
                "curve remains in the dataset but is excluded from the current report.",
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

        self.server_curve_status.setText(
            self._curve_status_text("server", server)
        )
        self.local_curve_status.setText(self._curve_status_text("local", local))
        self.show_normalized_gas_button.setEnabled(bool(selected))

    def _curve_status_text(self, source: str, curves: tuple[str, ...]) -> str:
        if source == "server":
            title = self._text(
                "Сервер/файл",
                "Сервер/файл",
                "Server/file",
            )
        else:
            title = self._text(
                "Локальный расчёт",
                "Жергілікті есеп",
                "Local calculation",
            )
        if curves:
            return f"{title}: " + ", ".join(curves)
        return f"{title}: " + self._text(
            "кривые не найдены",
            "қисықтар табылмады",
            "no curves found",
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

    def _show_normalized_error(self, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(self, self.tab_title(self.language), message)


__all__ = ["InterpretationReportWorkspace"]
