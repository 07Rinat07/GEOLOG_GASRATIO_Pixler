from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from geoworkbench.calculations.custom_formula import CustomFormulaError, formula_inputs
from geoworkbench.domain.models import CustomFormulaDefinition
from geoworkbench.project.custom_formula_controller import (
    CustomFormulaController,
    FormulaBatchPlan,
)
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: ("Пользовательские формулы", "Новая формула", "Название", "Выходная мнемоника", "Единица результата", "Формула", "Описание", "Найденные входы", "Новая", "Сохранить", "Удалить", "Рассчитать", "Закрыть", "Рассчитана кривая"),
    AppLanguage.EN: ("Custom formulas", "New formula", "Name", "Output mnemonic", "Output unit", "Formula", "Description", "Detected inputs", "New", "Save", "Delete", "Calculate", "Close", "Calculated curve"),
    AppLanguage.KK: ("Пайдаланушы формулалары", "Жаңа формула", "Атауы", "Шығыс мнемоникасы", "Нәтиже бірлігі", "Формула", "Сипаттама", "Табылған кірістер", "Жаңа", "Сақтау", "Жою", "Есептеу", "Жабу", "Есептелген қисық"),
}

_BATCH_TEXT = {
    AppLanguage.RU: ("Пересчитать все...", "Предварительный анализ формул", "Формула", "Выход", "Конечных", "Минимум", "Максимум", "Изменится", "Применить", "Отменить массовый пересчёт", "Повторить массовый пересчёт"),
    AppLanguage.EN: ("Recalculate all...", "Formula batch preview", "Formula", "Output", "Finite", "Minimum", "Maximum", "Changed", "Apply", "Undo batch recalculation", "Redo batch recalculation"),
    AppLanguage.KK: ("Барлығын қайта есептеу...", "Формулаларды алдын ала талдау", "Формула", "Шығыс", "Соңғы", "Минимум", "Максимум", "Өзгереді", "Қолдану", "Жаппай қайта есептеуді болдырмау", "Жаппай қайта есептеуді қайталау"),
}


class FormulaBatchPreviewDialog(QDialog):
    def __init__(
        self,
        plan: FormulaBatchPlan,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        text = _BATCH_TEXT[language]
        self.setWindowTitle(text[1])
        self.resize(760, 360)
        root = QVBoxLayout(self)
        table = QTableWidget(len(plan.previews), 6)
        table.setObjectName("formula-batch-preview")
        table.setHorizontalHeaderLabels(text[2:8])
        for row, preview in enumerate(plan.previews):
            values = (
                preview.name,
                preview.output_mnemonic,
                str(preview.finite_count),
                "—" if preview.minimum is None else f"{preview.minimum:.8g}",
                "—" if preview.maximum is None else f"{preview.maximum:.8g}",
                str(preview.changed_count),
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        root.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(text[8])
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)


class CustomFormulaDialog(QDialog):
    def __init__(self, controller: CustomFormulaController, parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.text = _TEXT[language]
        self.calculated_mnemonic: str | None = None
        self.dataset_changed = False
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
            (_BATCH_TEXT[language][0], self._calculate_all),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        self.undo_batch_button = QPushButton(_BATCH_TEXT[language][9])
        self.undo_batch_button.clicked.connect(self._undo_batch)
        buttons.addWidget(self.undo_batch_button)
        self.redo_batch_button = QPushButton(_BATCH_TEXT[language][10])
        self.redo_batch_button.clicked.connect(self._redo_batch)
        buttons.addWidget(self.redo_batch_button)
        close_button = QPushButton(self.text[12])
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        root.addLayout(buttons)
        self._refresh()
        self._update_batch_actions()

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
        self.dataset_changed = True
        self._refresh(stored.formula_id)
        QMessageBox.information(self, self.text[5], f"{self.text[13]} {self.calculated_mnemonic}")

    def _calculate_all(self) -> None:
        try:
            plan = self.controller.analyze_batch()
        except (CustomFormulaError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.text[0], str(exc))
            return
        preview = FormulaBatchPreviewDialog(plan, self, language=self.language)
        if preview.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            curves = self.controller.apply_batch(plan)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.text[0], str(exc))
            return
        if curves:
            self.calculated_mnemonic = curves[-1].metadata.original_mnemonic
        self.dataset_changed = True
        self._refresh(self.selector.currentData())
        self._update_batch_actions()

    def _undo_batch(self) -> None:
        try:
            self.controller.undo_batch()
        except RuntimeError as exc:
            QMessageBox.warning(self, self.text[0], str(exc))
            return
        self.calculated_mnemonic = None
        self.dataset_changed = True
        self._update_batch_actions()

    def _redo_batch(self) -> None:
        try:
            curves = self.controller.redo_batch()
        except RuntimeError as exc:
            QMessageBox.warning(self, self.text[0], str(exc))
            return
        self.calculated_mnemonic = (
            curves[-1].metadata.original_mnemonic if curves else None
        )
        self.dataset_changed = True
        self._update_batch_actions()

    def _update_batch_actions(self) -> None:
        self.undo_batch_button.setEnabled(self.controller.can_undo_batch)
        self.redo_batch_button.setEnabled(self.controller.can_redo_batch)

    def _preview_inputs(self) -> None:
        try:
            self.inputs.setText(", ".join(formula_inputs(self.expression.text())) or "—")
        except CustomFormulaError as exc:
            self.inputs.setText(str(exc))
