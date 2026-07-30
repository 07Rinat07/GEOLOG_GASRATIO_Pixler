from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasReference,
)
from geoworkbench.services.drilling_input_plan import (
    DepthValueSection,
    DrillingInputPlan,
    DrillingInputResolver,
    InputSourceMode,
    ParameterSource,
    candidate_curves,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class DrillingCalculationRequest:
    plan: DrillingInputPlan
    normalized_reference: NormalizedGasReference
    normal_mud_density_ppg: float | None


@dataclass(slots=True)
class _SourceRow:
    combo: QComboBox
    value: QDoubleSpinBox
    unit: QComboBox
    status: QLabel


class DrillingCalculationDialog(QDialog):
    """Configure shared drilling inputs for normalized gas, DEXP, and DEXPC."""

    _PARAMETERS = (
        ("ROP", "rop", ("m/h", "ft/h"), "m/h"),
        ("FLOW_IN", "flow", ("L/min", "m3/h", "gpm"), "L/min"),
        ("RPM", "rpm", ("1/min",), "1/min"),
        ("WOB", "wob", ("t", "kN", "lbf"), "t"),
        ("MW_IN", "mud_density", ("g/cm3", "kg/m3", "ppg"), "g/cm3"),
    )

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        normalized_reference: NormalizedGasReference | None = None,
        normal_mud_density_ppg: float | None = None,
    ) -> None:
        super().__init__(parent)
        dataset = controller.session.current_dataset
        if dataset is None:
            raise RuntimeError(
                self._language_text(
                    language,
                    "Сначала выберите набор данных",
                    "Алдымен деректер жинағын таңдаңыз",
                    "Select a dataset first",
                )
            )
        self.controller = controller
        self.dataset = dataset
        self.language = language
        self._request: DrillingCalculationRequest | None = None
        self._source_rows: dict[str, _SourceRow] = {}

        self.setObjectName("drillingCalculationDialog")
        self.setWindowTitle(
            self._text(
                "Нормализованный газ и DEXP",
                "Нормаланған газ және DEXP",
                "Normalized gas and DEXP",
            )
        )
        self.resize(1_050, 760)

        root = QVBoxLayout(self)
        intro = QLabel(
            self._text(
                "Фактические буровые параметры берутся из выбранных кривых или из явно "
                "заданных значений. При смене диаметра BIT задаётся секциями по MD.",
                "Нақты бұрғылау параметрлері таңдалған қисықтардан немесе анық енгізілген "
                "мәндерден алынады. Диаметр өзгерсе, BIT MD секцияларымен беріледі.",
                "Actual drilling parameters come from selected curves or explicit values. "
                "When hole size changes, define BIT by MD sections.",
            )
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        tabs = QTabWidget()
        tabs.addTab(
            self._build_sources_tab(),
            self._text("Буровые параметры", "Бұрғылау параметрлері", "Drilling inputs"),
        )
        tabs.addTab(
            self._build_bit_tab(),
            self._text("Секции BIT", "BIT секциялары", "BIT sections"),
        )
        tabs.addTab(
            self._build_reference_tab(normalized_reference, normal_mud_density_ppg),
            self._text("Эталон и DEXPC", "Эталон және DEXPC", "Reference and DEXPC"),
        )
        root.addWidget(tabs, 1)

        note = QLabel(
            self._text(
                "Одно постоянное значение допустимо только когда весь расчётный интервал "
                "пробурен одним долотом. Для нескольких секций используйте таблицу.",
                "Бір тұрақты мән тек есептік аралықтың барлығы бір қашаумен бұрғыланса жарайды. "
                "Бірнеше секция үшін кестені пайдаланыңыз.",
                "A single constant is valid only when the full calculation interval was drilled "
                "with one bit. Use the table for multiple sections.",
            )
        )
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(
                self._text("Применить и рассчитать", "Қолданып есептеу", "Apply and calculate")
            )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_sources_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        help_label = QLabel(
            self._text(
                "Автовыбор объединяет только численно идентичные дубли. Если два канала "
                "отличаются, выберите нужный явно.",
                "Автовыбор тек сандық мәндері бірдей дубльдерді біріктіреді. Екі арна "
                "айырмашылық жасаса, қажеттісін нақты таңдаңыз.",
                "Automatic selection merges only numerically identical duplicates. Select a "
                "specific curve when candidates differ.",
            )
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        grid = QGridLayout()
        for column, text in enumerate(
            (
                self._text("Параметр", "Параметр", "Parameter"),
                self._text("Источник", "Дереккөз", "Source"),
                self._text("Ручное значение", "Қолмен енгізу", "Manual value"),
                self._text("Единица", "Бірлік", "Unit"),
                self._text("Состояние", "Күй", "Status"),
            )
        ):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, column)

        plan = self.controller.drilling_input_plan
        for row_index, (canonical, attribute, units, default_unit) in enumerate(
            self._PARAMETERS, start=1
        ):
            grid.addWidget(QLabel(self._parameter_label(canonical)), row_index, 0)
            combo = self._source_combo(canonical)
            value = QDoubleSpinBox()
            value.setDecimals(4)
            value.setRange(0.0, 1.0e9)
            value.setSpecialValueText(self._text("не задано", "берілмеген", "not set"))
            unit = QComboBox()
            unit.addItems(list(units))
            unit.setCurrentText(default_unit)
            status = QLabel()
            status.setWordWrap(True)
            status.setMinimumWidth(230)
            grid.addWidget(combo, row_index, 1)
            grid.addWidget(value, row_index, 2)
            grid.addWidget(unit, row_index, 3)
            grid.addWidget(status, row_index, 4)

            source = getattr(plan, attribute)
            self._restore_source(combo, value, unit, source)
            self._source_rows[attribute] = _SourceRow(combo, value, unit, status)
            combo.currentIndexChanged.connect(
                lambda _index, name=attribute: self._update_source_row(name)
            )
            self._update_source_row(attribute)

        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(4, 1)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _source_combo(self, canonical: str) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(330)
        combo.addItem(self._text("Автоматически", "Автоматты", "Automatic"), "auto")
        candidate_keys = (canonical,)
        if canonical == "FLOW_IN":
            candidate_keys = ("FLOW_IN", "FLOW_OUT")
        elif canonical == "MW_IN":
            candidate_keys = ("MW_IN", "MW_OUT")
        seen_ids: set[str] = set()
        for key in candidate_keys:
            for match in candidate_curves(self.dataset, key):
                if match.curve_id in seen_ids:
                    continue
                seen_ids.add(match.curve_id)
                combo.addItem(
                    f"{match.source_mnemonic} [{match.unit or '—'}] · "
                    f"{self._coverage(match.curve.values):.1f}%",
                    f"curve:{match.curve_id}",
                )
        combo.addItem(
            self._text("Постоянное значение", "Тұрақты мән", "Constant value"),
            "constant",
        )
        return combo

    def _build_bit_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.bit_mode = QComboBox()
        self.bit_mode.addItem(
            self._text(
                "Автоматически из BIT/BS/HOLE_SIZE",
                "BIT/BS/HOLE_SIZE қисығынан автоматты",
                "Automatic from BIT/BS/HOLE_SIZE",
            ),
            InputSourceMode.AUTO.value,
        )
        self.bit_mode.addItem(
            self._text("Таблица секций по MD", "MD бойынша секциялар кестесі", "MD section table"),
            InputSourceMode.SECTIONS.value,
        )
        self.bit_mode.addItem(
            self._text("Одно постоянное значение", "Бір тұрақты мән", "One constant value"),
            InputSourceMode.CONSTANT.value,
        )
        form.addRow(
            self._text("Источник фактического BIT:", "Нақты BIT дереккөзі:", "Actual BIT source:"),
            self.bit_mode,
        )

        constant_widget = QWidget()
        constant_layout = QHBoxLayout(constant_widget)
        constant_layout.setContentsMargins(0, 0, 0, 0)
        self.bit_constant = QDoubleSpinBox()
        self.bit_constant.setDecimals(3)
        self.bit_constant.setRange(0.0, 10_000.0)
        self.bit_constant.setSpecialValueText(
            self._text("не задано", "берілмеген", "not set")
        )
        self.bit_constant_unit = QComboBox()
        self.bit_constant_unit.addItems(["mm", "in"])
        constant_layout.addWidget(self.bit_constant)
        constant_layout.addWidget(self.bit_constant_unit)
        form.addRow(
            self._text("Постоянный диаметр:", "Тұрақты диаметр:", "Constant diameter:"),
            constant_widget,
        )
        layout.addLayout(form)

        self.bit_table = QTableWidget(0, 5)
        self.bit_table.setObjectName("bitSectionTable")
        self.bit_table.setHorizontalHeaderLabels(
            [
                self._text("MD от", "MD бастап", "MD top"),
                self._text("MD до", "MD дейін", "MD bottom"),
                self._text("Диаметр", "Диаметр", "Diameter"),
                self._text("Единица", "Бірлік", "Unit"),
                self._text("Комментарий", "Түсініктеме", "Comment"),
            ]
        )
        header = self.bit_table.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.bit_table, 1)

        actions = QHBoxLayout()
        add_button = QPushButton(self._text("Добавить секцию", "Секция қосу", "Add section"))
        remove_button = QPushButton(
            self._text("Удалить выбранные", "Таңдалғанды жою", "Remove selected")
        )
        add_button.clicked.connect(self._add_bit_section)
        remove_button.clicked.connect(self._remove_bit_sections)
        actions.addWidget(add_button)
        actions.addWidget(remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        plan = self.controller.drilling_input_plan
        self.bit_mode.setCurrentIndex(max(0, self.bit_mode.findData(plan.bit.mode.value)))
        if plan.bit.value is not None:
            self.bit_constant.setValue(plan.bit.value)
        if plan.bit.unit:
            self.bit_constant_unit.setCurrentText(plan.bit.unit)
        if plan.bit_sections:
            for section in plan.bit_sections:
                self._append_bit_section(section)
        else:
            depth = np.asarray(self.dataset.depth, dtype=np.float64)
            finite = depth[np.isfinite(depth)]
            if finite.size:
                self._append_bit_section(
                    DepthValueSection(
                        float(np.min(finite)), float(np.max(finite)), 0.0, "mm"
                    )
                )
        self.bit_mode.currentIndexChanged.connect(self._update_bit_controls)
        self._update_bit_controls()
        return page

    def _build_reference_tab(
        self,
        reference: NormalizedGasReference | None,
        normal_mud_density_ppg: float | None,
    ) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        current = reference or NormalizedGasReference()
        self.rop_reference = self._spin(0.01, 10_000.0, current.rop_ref_fph, " ft/h")
        self.bit_reference = self._spin(0.01, 100.0, current.bit_ref_in, " in")
        self.flow_reference = self._spin(0.01, 100_000.0, current.flow_ref_gpm, " gpm")
        self.gas_efficiency = self._spin(
            0.01, 1.0, current.gas_system_efficiency, ""
        )
        self.normal_density = self._spin(
            0.0, 30.0, normal_mud_density_ppg or 0.0, " ppg"
        )
        self.normal_density.setSpecialValueText(
            self._text("DEXPC не считать", "DEXPC есептемеу", "Do not calculate DEXPC")
        )
        form.addRow("ROP_REF:", self.rop_reference)
        form.addRow("BIT_REF:", self.bit_reference)
        form.addRow("FLOW_REF:", self.flow_reference)
        form.addRow(
            self._text(
                "Эффективность газовой системы:",
                "Газ жүйесінің тиімділігі:",
                "Gas-system efficiency:",
            ),
            self.gas_efficiency,
        )
        form.addRow(
            self._text(
                "Нормальная плотность для DEXPC:",
                "DEXPC үшін қалыпты тығыздық:",
                "Normal mud density for DEXPC:",
            ),
            self.normal_density,
        )
        explanation = QLabel(
            self._text(
                "BIT_REF — эталон нормализации, а не фактический диаметр. Фактический BIT "
                "задаётся на вкладке секций и одновременно используется в DEXP.",
                "BIT_REF — нормалау эталоны, нақты диаметр емес. Нақты BIT секциялар бетінде "
                "беріледі және DEXP есептеуінде де қолданылады.",
                "BIT_REF is a normalization reference, not the actual hole size. Actual BIT is "
                "defined on the sections tab and is also used by DEXP.",
            )
        )
        explanation.setWordWrap(True)
        form.addRow(explanation)
        return page

    def request(self) -> DrillingCalculationRequest:
        if self._request is None:
            raise RuntimeError("Диалог ещё не подтверждён")
        return self._request

    def accept(self) -> None:
        try:
            plan = self._build_plan()
            plan.validate()
            probe = DrillingInputResolver(plan=plan)
            if plan.bit.mode is not InputSourceMode.AUTO:
                probe.resolve_dataset(self.dataset, targets=("BIT",)).require("BIT")
            reference = NormalizedGasReference(
                rop_ref_fph=self.rop_reference.value(),
                bit_ref_in=self.bit_reference.value(),
                flow_ref_gpm=self.flow_reference.value(),
                gas_system_efficiency=self.gas_efficiency.value(),
            )
            reference.parameters()
            density = self.normal_density.value()
            self._request = DrillingCalculationRequest(
                plan, reference, density if density > 0.0 else None
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        super().accept()

    def _build_plan(self) -> DrillingInputPlan:
        sources = {
            name: self._source_from_row(row) for name, row in self._source_rows.items()
        }
        mode = InputSourceMode(str(self.bit_mode.currentData()))
        if mode is InputSourceMode.SECTIONS:
            bit = ParameterSource(InputSourceMode.SECTIONS)
            sections = self._read_bit_sections()
        elif mode is InputSourceMode.CONSTANT:
            bit = ParameterSource(
                InputSourceMode.CONSTANT,
                value=self.bit_constant.value(),
                unit=self.bit_constant_unit.currentText(),
            )
            sections = ()
        else:
            bit = ParameterSource()
            sections = ()
        return DrillingInputPlan(
            rop=sources["rop"],
            flow=sources["flow"],
            rpm=sources["rpm"],
            wob=sources["wob"],
            mud_density=sources["mud_density"],
            bit=bit,
            bit_sections=sections,
        )

    @staticmethod
    def _source_from_row(row: _SourceRow) -> ParameterSource:
        data = str(row.combo.currentData())
        if data == "auto":
            return ParameterSource()
        if data == "constant":
            return ParameterSource(
                InputSourceMode.CONSTANT,
                value=row.value.value(),
                unit=row.unit.currentText(),
            )
        if data.startswith("curve:"):
            return ParameterSource(
                InputSourceMode.CURVE, curve_id=data.split(":", 1)[1]
            )
        raise ValueError(f"Неизвестный источник: {data}")

    def _read_bit_sections(self) -> tuple[DepthValueSection, ...]:
        result: list[DepthValueSection] = []
        for row in range(self.bit_table.rowCount()):
            unit_widget = self.bit_table.cellWidget(row, 3)
            unit = unit_widget.currentText() if isinstance(unit_widget, QComboBox) else "mm"
            comment_item = self.bit_table.item(row, 4)
            result.append(
                DepthValueSection(
                    self._table_float(row, 0),
                    self._table_float(row, 1),
                    self._table_float(row, 2),
                    unit,
                    comment_item.text().strip() if comment_item is not None else "",
                )
            )
        return tuple(result)

    def _add_bit_section(self) -> None:
        previous_bottom = (
            self._table_float(self.bit_table.rowCount() - 1, 1, default=0.0)
            if self.bit_table.rowCount()
            else 0.0
        )
        self._append_bit_section(
            DepthValueSection(previous_bottom, previous_bottom, 0.0, "mm")
        )

    def _append_bit_section(self, section: DepthValueSection) -> None:
        row = self.bit_table.rowCount()
        self.bit_table.insertRow(row)
        for column, value in enumerate((section.top_md, section.bottom_md, section.value)):
            self.bit_table.setItem(row, column, QTableWidgetItem(f"{value:g}"))
        unit = QComboBox()
        unit.addItems(["mm", "in"])
        unit.setCurrentText(section.unit)
        self.bit_table.setCellWidget(row, 3, unit)
        self.bit_table.setItem(row, 4, QTableWidgetItem(section.comment))

    def _remove_bit_sections(self) -> None:
        rows = sorted(
            {index.row() for index in self.bit_table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self.bit_table.removeRow(row)

    def _update_bit_controls(self) -> None:
        mode = InputSourceMode(str(self.bit_mode.currentData()))
        self.bit_constant.setEnabled(mode is InputSourceMode.CONSTANT)
        self.bit_constant_unit.setEnabled(mode is InputSourceMode.CONSTANT)
        self.bit_table.setEnabled(mode is InputSourceMode.SECTIONS)

    def _update_source_row(self, name: str) -> None:
        row = self._source_rows[name]
        data = str(row.combo.currentData())
        manual = data == "constant"
        row.value.setEnabled(manual)
        row.unit.setEnabled(manual)
        if data == "auto":
            text = self._text(
                "Автовыбор с проверкой дублей",
                "Дубльдерді тексеретін автовыбор",
                "Automatic selection with duplicate check",
            )
        elif manual:
            text = self._text(
                "Постоянно на всей глубинной оси",
                "Барлық тереңдік осінде тұрақты",
                "Constant over the full depth axis",
            )
        else:
            text = self._text(
                "Явно выбранная кривая",
                "Нақты таңдалған қисық",
                "Explicitly selected curve",
            )
        row.status.setText(text)

    @staticmethod
    def _restore_source(
        combo: QComboBox,
        value: QDoubleSpinBox,
        unit: QComboBox,
        source: ParameterSource,
    ) -> None:
        data = (
            f"curve:{source.curve_id}"
            if source.mode is InputSourceMode.CURVE
            else source.mode.value
        )
        combo.setCurrentIndex(max(0, combo.findData(data)))
        if source.value is not None:
            value.setValue(source.value)
        if source.unit:
            unit.setCurrentText(source.unit)

    @staticmethod
    def _spin(
        minimum: float, maximum: float, value: float, suffix: str
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    @staticmethod
    def _coverage(values: np.ndarray) -> float:
        array = np.asarray(values, dtype=np.float64)
        if not array.size:
            return 0.0
        return 100.0 * float(np.count_nonzero(np.isfinite(array))) / float(array.size)

    def _table_float(
        self, row: int, column: int, *, default: float | None = None
    ) -> float:
        item = self.bit_table.item(row, column)
        text = item.text().strip().replace(",", ".") if item is not None else ""
        if not text and default is not None:
            return default
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(
                self._text(
                    f"Некорректное число в строке секции {row + 1}",
                    f"Секцияның {row + 1}-жолында қате сан",
                    f"Invalid number in section row {row + 1}",
                )
            ) from exc

    def _parameter_label(self, canonical: str) -> str:
        return {
            "ROP": "ROP",
            "FLOW_IN": "FLOW",
            "RPM": "RPM",
            "WOB": "WOB",
            "MW_IN": self._text(
                "Плотность раствора", "Ерітінді тығыздығы", "Mud density"
            ),
        }[canonical]

    def _text(self, ru: str, kk: str, en: str) -> str:
        return self._language_text(self.language, ru, kk, en)

    @staticmethod
    def _language_text(language: AppLanguage, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[language]


__all__ = ["DrillingCalculationDialog", "DrillingCalculationRequest"]
