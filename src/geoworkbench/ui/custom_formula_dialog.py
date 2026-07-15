from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from geoworkbench.calculations.custom_formula import CustomFormulaError, formula_inputs
from geoworkbench.domain.models import CustomFormulaDefinition
from geoworkbench.project.custom_formula_controller import CustomFormulaController
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: ("Пользовательские формулы", "Новая формула", "Название", "Выходная мнемоника", "Единица результата", "Формула", "Описание", "Найденные входы", "Новая", "Сохранить", "Удалить", "Рассчитать", "Закрыть", "Рассчитана кривая"),
    AppLanguage.EN: ("Custom formulas", "New formula", "Name", "Output mnemonic", "Output unit", "Formula", "Description", "Detected inputs", "New", "Save", "Delete", "Calculate", "Close", "Calculated curve"),
    AppLanguage.KK: ("Пайдаланушы формулалары", "Жаңа формула", "Атауы", "Шығыс мнемоникасы", "Нәтиже бірлігі", "Формула", "Сипаттама", "Табылған кірістер", "Жаңа", "Сақтау", "Жою", "Есептеу", "Жабу", "Есептелген қисық"),
}


class CustomFormulaDialog(QDialog):
    def __init__(self, controller: CustomFormulaController, parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__(parent)
        self.controller = controller
        self.text = _TEXT[language]
        self.calculated_mnemonic: str | None = None
        self.setWindowTitle(self.text[0])
        self.resize(720, 360)
        root = QVBoxLayout(self)
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self._load_selected)
        root.addWidget(self.selector)
        form = QFormLayout()
        self.formula_id = QLineEdit()
        self.name = QLineEdit()
        self.output = QLineEdit()
        self.unit = QLineEdit()
        self.expression = QLineEdit()
        self.description = QLineEdit()
        self.inputs = QLabel("—")
        self.expression.textChanged.connect(self._preview_inputs)
        form.addRow("ID", self.formula_id)
        form.addRow(self.text[2], self.name)
        form.addRow(self.text[3], self.output)
        form.addRow(self.text[4], self.unit)
        form.addRow(self.text[5], self.expression)
        form.addRow(self.text[6], self.description)
        form.addRow(self.text[7], self.inputs)
        root.addLayout(form)
        buttons = QHBoxLayout()
        for text, handler in (
            (self.text[8], self._new), (self.text[9], self._save),
            (self.text[10], self._delete), (self.text[11], self._calculate),
            (self.text[12], self.accept),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        root.addLayout(buttons)
        self._refresh()

    def _refresh(self, selected_id: str | None = None) -> None:
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem(self.text[1], None)
        for formula in self.controller.session.project.custom_formulas.values():
            self.selector.addItem(f"{formula.name} → {formula.output_mnemonic}", formula.formula_id)
        self.selector.blockSignals(False)
        index = self.selector.findData(selected_id) if selected_id else 0
        self.selector.setCurrentIndex(max(index, 0))
        self._load_selected()

    def _load_selected(self) -> None:
        formula_id = self.selector.currentData()
        if not isinstance(formula_id, str):
            self._new()
            return
        formula = self.controller.session.project.custom_formulas[formula_id]
        self.formula_id.setText(formula.formula_id)
        self.formula_id.setReadOnly(True)
        self.name.setText(formula.name)
        self.output.setText(formula.output_mnemonic)
        self.unit.setText(formula.output_unit)
        self.expression.setText(formula.expression)
        self.description.setText(formula.description)

    def _new(self) -> None:
        self.formula_id.setReadOnly(False)
        for editor in (self.formula_id, self.name, self.output, self.unit, self.expression, self.description):
            editor.clear()
        self.inputs.setText("—")

    def _definition(self) -> CustomFormulaDefinition:
        return CustomFormulaDefinition(
            self.formula_id.text().strip(), self.name.text().strip(),
            self.expression.text().strip(), self.output.text().strip().upper(),
            self.unit.text().strip(), self.description.text().strip(),
        )

    def _save(self) -> None:
        try:
            stored = self.controller.save(self._definition())
        except (CustomFormulaError, ValueError) as exc:
            QMessageBox.warning(self, "Формула", str(exc))
            return
        self._refresh(stored.formula_id)

    def _delete(self) -> None:
        formula_id = self.selector.currentData()
        if not isinstance(formula_id, str):
            return
        self.controller.delete(formula_id)
        self._refresh()

    def _calculate(self) -> None:
        try:
            stored = self.controller.save(self._definition())
            curve = self.controller.calculate(stored.formula_id)
        except (CustomFormulaError, KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Формула", str(exc))
            return
        self.calculated_mnemonic = curve.metadata.original_mnemonic
        self._refresh(stored.formula_id)
        QMessageBox.information(self, self.text[5], f"{self.text[13]} {self.calculated_mnemonic}")

    def _preview_inputs(self) -> None:
        try:
            self.inputs.setText(", ".join(formula_inputs(self.expression.text())) or "—")
        except CustomFormulaError as exc:
            self.inputs.setText(str(exc))
