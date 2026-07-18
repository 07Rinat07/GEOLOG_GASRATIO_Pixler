from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES, Localizer


class MasterlogOutputDialog(QDialog):
    def __init__(
        self,
        depth_range: tuple[float, float],
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("masterlog_output.title"))
        top, bottom = depth_range
        self.top_input = QDoubleSpinBox()
        self.bottom_input = QDoubleSpinBox()
        for control in (self.top_input, self.bottom_input):
            control.setRange(top, bottom)
            control.setDecimals(3)
        self.top_input.setValue(top)
        self.bottom_input.setValue(bottom)
        self.language_input = QComboBox()
        for value in AppLanguage:
            self.language_input.addItem(LANGUAGE_NAMES[value], value.value)
        self.language_input.setCurrentIndex(
            self.language_input.findData(language.value)
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow(self.localizer.text("masterlog_output.top"), self.top_input)
        layout.addRow(self.localizer.text("masterlog_output.bottom"), self.bottom_input)
        layout.addRow(self.localizer.text("masterlog_output.language"), self.language_input)
        layout.addRow(buttons)

    def settings(self) -> MasterlogOutputSettings:
        return MasterlogOutputSettings(
            self.top_input.value(),
            self.bottom_input.value(),
            AppLanguage(str(self.language_input.currentData())),
        )
