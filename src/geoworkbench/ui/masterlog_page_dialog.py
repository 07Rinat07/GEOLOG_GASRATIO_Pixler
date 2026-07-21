from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
)

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogPageDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("masterlog_page.title"))
        self.format_input = QComboBox()
        for value in ("A4", "A3", "A2", "A1", "A0", "letter", "legal", "custom", "roll"):
            self.format_input.addItem(
                self.localizer.text(f"masterlog_page.{value.casefold()}"), value
            )
        index = self.format_input.findData(template.page_format)
        self.format_input.setCurrentIndex(index if index >= 0 else 0)
        self.scale_input = QSpinBox()
        self.scale_input.setRange(10, 10000)
        self.scale_input.setValue(template.depth_scale)
        self.header_input = QDoubleSpinBox()
        self.header_input.setRange(5.0, 500.0)
        self.header_input.setDecimals(1)
        self.header_input.setValue(template.header_height_mm)
        self.orientation_input = QComboBox()
        for value in ("portrait", "landscape"):
            self.orientation_input.addItem(self.localizer.text(f"masterlog_page.{value}"), value)
        orientation = template.properties.get("orientation", "portrait")
        orientation_index = self.orientation_input.findData(orientation)
        self.orientation_input.setCurrentIndex(orientation_index if orientation_index >= 0 else 0)
        self.width_input = QDoubleSpinBox()
        self.height_input = QDoubleSpinBox()
        for control, key, fallback in (
            (self.width_input, "custom_width_mm", 210.0),
            (self.height_input, "custom_height_mm", 297.0),
        ):
            control.setRange(25.0, 5000.0)
            control.setDecimals(1)
            value = template.properties.get(key, fallback)
            control.setValue(
                float(value)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else fallback
            )
        self.width_label = QLabel(self.localizer.text("masterlog_page.width"))
        self.height_label = QLabel(self.localizer.text("masterlog_page.height"))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow(self.localizer.text("masterlog_page.format"), self.format_input)
        layout.addRow(self.localizer.text("masterlog_page.orientation"), self.orientation_input)
        layout.addRow(self.localizer.text("masterlog_page.scale"), self.scale_input)
        layout.addRow(self.localizer.text("masterlog_page.header_height"), self.header_input)
        layout.addRow(self.width_label, self.width_input)
        layout.addRow(self.height_label, self.height_input)
        layout.addRow(buttons)
        self.format_input.currentIndexChanged.connect(self._update_custom_visibility)
        self._update_custom_visibility()

    def _update_custom_visibility(self) -> None:
        selected = self.format_input.currentData()
        self.width_label.setVisible(selected in {"custom", "roll"})
        self.width_input.setVisible(selected in {"custom", "roll"})
        self.height_label.setVisible(selected == "custom")
        self.height_input.setVisible(selected == "custom")
        self.orientation_input.setEnabled(selected != "roll")

    def values(self) -> tuple[str, str, int, float, float, float]:
        return (
            str(self.format_input.currentData()),
            str(self.orientation_input.currentData()),
            self.scale_input.value(),
            self.header_input.value(),
            self.width_input.value(),
            self.height_input.value(),
        )
