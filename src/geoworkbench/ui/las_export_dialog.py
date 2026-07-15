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
from geoworkbench.services.localization import AppLanguage, Localizer


class LasExportPlanDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial: LasExportPlan | None = None,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("export.plan_title"))
        plan = initial or LasExportPlan()

        self.version_combo = QComboBox()
        self.version_combo.addItem("LAS 2.0", LasExportVersion.V2_0.value)
        self.version_combo.addItem(
            self._t("export.las12_compatibility"), LasExportVersion.V1_2.value
        )
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
        self.preserve_check = QCheckBox(self._t("export.preserve_custom"))
        self.preserve_check.setChecked(plan.preserve_custom_sections)

        layout = QFormLayout(self)
        layout.addRow(self._t("export.version"), self.version_combo)
        layout.addRow(self._t("export.wrap"), self.wrap_check)
        layout.addRow("NULL", self.null_spin)
        layout.addRow(self._t("export.precision"), self.precision_spin)
        layout.addRow(self.preserve_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        layout.addRow(buttons)

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def export_plan(self) -> LasExportPlan:
        version_value = self.version_combo.currentData()
        if not isinstance(version_value, str):
            raise RuntimeError(self._t("export.select_version"))
        return LasExportPlan(
            version=LasExportVersion(version_value),
            wrap=self.wrap_check.isChecked(),
            null_value=self.null_spin.value(),
            precision=self.precision_spin.value(),
            preserve_custom_sections=self.preserve_check.isChecked(),
        )
