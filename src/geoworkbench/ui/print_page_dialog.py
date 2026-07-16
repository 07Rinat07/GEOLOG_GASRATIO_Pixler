from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class PrintPageDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial: PrintPageSettings | None = None,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        settings = initial or PrintPageSettings()
        self.setWindowTitle(self._t("print.page_setup"))

        self.format_combo = QComboBox()
        self.format_combo.addItem("A4", PrintPageFormat.A4.value)
        self.format_combo.addItem("A3", PrintPageFormat.A3.value)
        self.format_combo.addItem(
            self._t("print.custom"), PrintPageFormat.CUSTOM.value
        )
        self.format_combo.addItem(
            self._t("print.roll"), PrintPageFormat.ROLL.value
        )
        self.format_combo.setCurrentIndex(
            self.format_combo.findData(settings.page_format.value)
        )
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(
            self._t("print.portrait"), PrintOrientation.PORTRAIT.value
        )
        self.orientation_combo.addItem(
            self._t("print.landscape"), PrintOrientation.LANDSCAPE.value
        )
        self.orientation_combo.setCurrentIndex(
            self.orientation_combo.findData(settings.orientation.value)
        )
        self.width_input = self._dimension_input(settings.custom_width_mm)
        self.height_input = self._dimension_input(settings.custom_height_mm)
        self.format_combo.currentIndexChanged.connect(self._update_custom_enabled)

        layout = QFormLayout(self)
        layout.addRow(self._t("print.page_format"), self.format_combo)
        layout.addRow(self._t("print.orientation"), self.orientation_combo)
        layout.addRow(self._t("print.width_mm"), self.width_input)
        layout.addRow(self._t("print.height_mm"), self.height_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        layout.addRow(buttons)
        self._update_custom_enabled()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def page_settings(self) -> PrintPageSettings:
        return PrintPageSettings(
            PrintPageFormat(str(self.format_combo.currentData())),
            PrintOrientation(str(self.orientation_combo.currentData())),
            self.width_input.value(),
            self.height_input.value(),
        )

    @staticmethod
    def _dimension_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(25.0, 5000.0)
        control.setDecimals(1)
        control.setSuffix(" mm")
        control.setValue(value)
        return control

    def _update_custom_enabled(self) -> None:
        selected = self.format_combo.currentData()
        self.width_input.setEnabled(
            selected in {PrintPageFormat.CUSTOM.value, PrintPageFormat.ROLL.value}
        )
        self.height_input.setEnabled(selected == PrintPageFormat.CUSTOM.value)
