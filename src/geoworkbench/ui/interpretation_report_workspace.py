from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QWidget

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasCalculationMode,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    set_normalized_gas_report_mode,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace_legacy import (
    InterpretationReportWorkspace as _LegacyInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_LegacyInterpretationReportWorkspace):
    """Report workspace with explicit server/local normalized-gas modes."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        self._normalized_mode_ready = False
        super().__init__(controller, parent, language=language)
        self.normalized_gas_mode_label = QLabel()
        self.normalized_gas_mode = QComboBox()
        self.normalized_gas_mode.setObjectName("normalizedGasMode")
        self.normalized_gas_mode.setMinimumWidth(420)
        self.normalized_gas_mode_help = QLabel()
        self.normalized_gas_mode_help.setObjectName("normalized-gas-mode-help")
        self.normalized_gas_mode_help.setWordWrap(True)
        forms = self.findChildren(QFormLayout)
        if not forms:
            raise RuntimeError("Не найдена форма параметров интерпретации")
        form = forms[0]
        form.insertRow(1, self.normalized_gas_mode_label, self.normalized_gas_mode)
        form.insertRow(2, self.normalized_gas_mode_help)
        self.normalized_gas_mode.currentIndexChanged.connect(
            self._normalized_gas_mode_changed
        )
        self._normalized_mode_ready = True
        self._retranslate_normalized_gas_mode()
        self._apply_normalized_gas_mode()
        self.refresh()

    def refresh(self) -> None:
        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        super().refresh()
        if not self._normalized_mode_ready or self._is_mixture_mode():
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
        self.calculate_button.setText(
            self._text(
                "Рассчитать остальные методы"
                if mode is NormalizedGasCalculationMode.SERVER
                else "Рассчитать стандартные методы",
                "Қалған әдістерді есептеу"
                if mode is NormalizedGasCalculationMode.SERVER
                else "Стандартты әдістерді есептеу",
                "Calculate other methods"
                if mode is NormalizedGasCalculationMode.SERVER
                else "Calculate standard methods",
            )
        )

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if self._normalized_mode_ready:
            self._retranslate_normalized_gas_mode()
            self._apply_normalized_gas_mode()
            self.refresh()

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

    def _retranslate_normalized_gas_mode(self) -> None:
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
        self.normalized_gas_mode_label.setText(
            self._text(
                "Режим нормализованного газа:",
                "Нормаланған газ режимі:",
                "Normalized-gas mode:",
            )
        )

    def _apply_normalized_gas_mode(self) -> None:
        mode = self._current_normalized_gas_mode()
        set_normalized_gas_report_mode(self.controller.session, mode)
        self.controller.normalized_gas_mode = mode
        text = {
            NormalizedGasCalculationMode.COMPARE: self._text(
                "Готовая кривая с сервера/из файла не изменяется. Программа отдельно "
                "рассчитывает TG_NORM_CALC. В отчёте обе серии анализируются относительно "
                "собственного фона, а найденные интервалы отдельно сопоставляются с ЛБА.",
                "Серверден/файлдан келген дайын қисық өзгермейді. Бағдарлама TG_NORM_CALC "
                "қисығын бөлек есептейді. Есепте екі қатар өз фоны бойынша талданып, әр "
                "аралық ЛБА-мен жеке салыстырылады.",
                "The server/file curve is kept unchanged. The program calculates "
                "TG_NORM_CALC separately. The report analyses both series against their "
                "own baselines and correlates every interval with LBA independently.",
            ),
            NormalizedGasCalculationMode.SERVER: self._text(
                "Используется только готовая нормализованная кривая сервера/файла. "
                "Локальный TG_NORM_CALC не пересчитывается; остальные стандартные методы "
                "можно обновить кнопкой ниже.",
                "Тек сервердің/файлдың дайын нормаланған қисығы пайдаланылады. Жергілікті "
                "TG_NORM_CALC қайта есептелмейді; басқа стандартты әдістерді төмендегі "
                "батырмамен жаңартуға болады.",
                "Only the ready server/file normalized curve is used. Local TG_NORM_CALC "
                "is not recalculated; the other standard methods can still be updated below.",
            ),
            NormalizedGasCalculationMode.LOCAL: self._text(
                "Программа рассчитывает TG_NORM_CALC по C1–C5, ROP, BIT и FLOW. "
                "Серверная кривая сохраняется в наборе, но не участвует в текущем отчёте.",
                "Бағдарлама TG_NORM_CALC қисығын C1–C5, ROP, BIT және FLOW бойынша "
                "есептейді. Серверлік қисық жинақта сақталады, бірақ ағымдағы есепке кірмейді.",
                "The program calculates TG_NORM_CALC from C1–C5, ROP, BIT, and FLOW. "
                "The server curve remains in the dataset but is excluded from this report.",
            ),
        }[mode]
        self.normalized_gas_mode_help.setText(text)


__all__ = ["InterpretationReportWorkspace"]
