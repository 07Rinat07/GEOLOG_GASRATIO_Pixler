from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout

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

        layout = QFormLayout(self)
        layout.addRow(self._t("print.page_format"), self.format_combo)
        layout.addRow(self._t("print.orientation"), self.orientation_combo)
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

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def page_settings(self) -> PrintPageSettings:
        return PrintPageSettings(
            PrintPageFormat(str(self.format_combo.currentData())),
            PrintOrientation(str(self.orientation_combo.currentData())),
        )
