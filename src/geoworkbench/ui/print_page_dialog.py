from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
)

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.print_layout import PrintScaleMode
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
        for label, value in (
            ("A4", PrintPageFormat.A4.value),
            ("A3", PrintPageFormat.A3.value),
            ("A2", PrintPageFormat.A2.value),
            ("A1", PrintPageFormat.A1.value),
            ("A0", PrintPageFormat.A0.value),
            (self._t("print.letter"), PrintPageFormat.LETTER.value),
            (self._t("print.legal"), PrintPageFormat.LEGAL.value),
            (self._t("print.custom"), PrintPageFormat.CUSTOM.value),
            (self._t("print.roll"), PrintPageFormat.ROLL.value),
        ):
            self.format_combo.addItem(label, value)
        self.format_combo.setCurrentIndex(self.format_combo.findData(settings.page_format.value))
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(self._t("print.portrait"), PrintOrientation.PORTRAIT.value)
        self.orientation_combo.addItem(self._t("print.landscape"), PrintOrientation.LANDSCAPE.value)
        self.orientation_combo.setCurrentIndex(
            self.orientation_combo.findData(settings.orientation.value)
        )
        self.width_input = self._dimension_input(settings.custom_width_mm)
        self.height_input = self._dimension_input(settings.custom_height_mm)
        self.scale_combo = QComboBox()
        self.scale_combo.addItem(self._t("print_center.scale_fit"), PrintScaleMode.FIT.value)
        self.scale_combo.addItem(
            self._t("print_center.scale_actual"), PrintScaleMode.ACTUAL_SIZE.value
        )
        self.scale_combo.setCurrentIndex(
            max(0, self.scale_combo.findData(settings.scale_mode.value))
        )
        self.scale_combo.currentIndexChanged.connect(self._update_custom_enabled)
        self.fit_columns_check = QCheckBox(self._t("print.fit_form_columns"))
        self.fit_columns_check.setChecked(settings.fit_form_columns)
        self.fit_columns_check.setToolTip(self._t("print.fit_form_columns_tooltip"))
        self.continuation_overlap_input = self._continuation_input(
            settings.continuation_overlap_mm
        )
        self.continuation_overlap_input.setToolTip(
            self._t("print_center.continuation_overlap_tooltip")
        )
        self.margin_left_input = self._margin_input(settings.margin_left_mm)
        self.margin_top_input = self._margin_input(settings.margin_top_mm)
        self.margin_right_input = self._margin_input(settings.margin_right_mm)
        self.margin_bottom_input = self._margin_input(settings.margin_bottom_mm)
        self.format_combo.currentIndexChanged.connect(self._update_custom_enabled)

        layout = QFormLayout(self)
        layout.addRow(self._t("print.page_format"), self.format_combo)
        layout.addRow(self._t("print.orientation"), self.orientation_combo)
        layout.addRow(self._t("print.width_mm"), self.width_input)
        layout.addRow(self._t("print.height_mm"), self.height_input)
        layout.addRow(self._t("print_center.scale_mode"), self.scale_combo)
        layout.addRow(self.fit_columns_check)
        layout.addRow(
            self._t("print_center.continuation_overlap"),
            self.continuation_overlap_input,
        )

        margins_group = QGroupBox(self._t("print_center.margins_group"))
        margins_layout = QGridLayout(margins_group)
        for label, control, row, column in (
            (self._t("print_center.margin_left"), self.margin_left_input, 0, 0),
            (self._t("print_center.margin_top"), self.margin_top_input, 0, 2),
            (self._t("print_center.margin_right"), self.margin_right_input, 1, 0),
            (self._t("print_center.margin_bottom"), self.margin_bottom_input, 1, 2),
        ):
            margins_layout.addWidget(QLabel(label), row, column)
            margins_layout.addWidget(control, row, column + 1)
        layout.addRow(margins_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        layout.addRow(buttons)
        self._update_custom_enabled()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def page_settings(self) -> PrintPageSettings:
        return PrintPageSettings(
            page_format=PrintPageFormat(str(self.format_combo.currentData())),
            orientation=PrintOrientation(str(self.orientation_combo.currentData())),
            custom_width_mm=self.width_input.value(),
            custom_height_mm=self.height_input.value(),
            fit_form_columns=self.fit_columns_check.isChecked(),
            margin_left_mm=self.margin_left_input.value(),
            margin_top_mm=self.margin_top_input.value(),
            margin_right_mm=self.margin_right_input.value(),
            margin_bottom_mm=self.margin_bottom_input.value(),
            scale_mode=PrintScaleMode(str(self.scale_combo.currentData())),
            continuation_overlap_mm=self.continuation_overlap_input.value(),
        )

    @staticmethod
    def _dimension_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(25.0, 5000.0)
        control.setDecimals(1)
        control.setSuffix(" mm")
        control.setValue(value)
        return control

    @staticmethod
    def _continuation_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(0.0, 50.0)
        control.setDecimals(1)
        control.setSuffix(" mm")
        control.setValue(value)
        return control

    @staticmethod
    def _margin_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(0.0, 100.0)
        control.setDecimals(1)
        control.setSuffix(" mm")
        control.setValue(value)
        return control

    def _update_custom_enabled(self) -> None:
        selected = self.format_combo.currentData()
        scale_mode = PrintScaleMode(str(self.scale_combo.currentData()))
        self.width_input.setEnabled(
            selected in {PrintPageFormat.CUSTOM.value, PrintPageFormat.ROLL.value}
        )
        self.height_input.setEnabled(selected == PrintPageFormat.CUSTOM.value)
        self.orientation_combo.setEnabled(selected != PrintPageFormat.ROLL.value)
        self.fit_columns_check.setEnabled(scale_mode is PrintScaleMode.FIT)
        self.continuation_overlap_input.setEnabled(
            scale_mode is PrintScaleMode.ACTUAL_SIZE
        )
