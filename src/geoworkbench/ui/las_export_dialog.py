from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)

from geoworkbench.data.las_export_plan import LasExportPlan, LasExportVersion


class LasExportPlanDialog(QDialog):
    def __init__(self, parent=None, *, initial: LasExportPlan | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Параметры экспорта LAS")
        plan = initial or LasExportPlan()

        self.version_combo = QComboBox()
        self.version_combo.addItem("LAS 2.0", LasExportVersion.V2_0.value)
        self.version_combo.addItem("LAS 1.2 (совместимость)", LasExportVersion.V1_2.value)
        self.version_combo.setCurrentIndex(self.version_combo.findData(plan.version.value))

        self.wrap_check = QCheckBox("WRAP=YES")
        self.wrap_check.setChecked(plan.wrap)
        self.null_spin = QDoubleSpinBox()
        self.null_spin.setDecimals(8)
        self.null_spin.setRange(-1e100, 1e100)
        self.null_spin.setValue(plan.null_value)
        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(1, 15)
        self.precision_spin.setValue(plan.precision)
        self.preserve_check = QCheckBox("Переносить пользовательские секции и комментарии")
        self.preserve_check.setChecked(plan.preserve_custom_sections)

        layout = QFormLayout(self)
        layout.addRow("Версия", self.version_combo)
        layout.addRow("Перенос строк", self.wrap_check)
        layout.addRow("NULL", self.null_spin)
        layout.addRow("Знаков после запятой", self.precision_spin)
        layout.addRow(self.preserve_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def export_plan(self) -> LasExportPlan:
        version_value = self.version_combo.currentData()
        if not isinstance(version_value, str):
            raise RuntimeError("Не выбрана версия LAS")
        return LasExportPlan(
            version=LasExportVersion(version_value),
            wrap=self.wrap_check.isChecked(),
            null_value=self.null_spin.value(),
            precision=self.precision_spin.value(),
            preserve_custom_sections=self.preserve_check.isChecked(),
        )
