from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.print_job import (
    PrintExportPreferences,
    PrintJobSettings,
    PrintOutputFormat,
    available_output_formats,
)
from geoworkbench.services.localization import AppLanguage, Localizer


PreviewCallback = Callable[[PrintJobSettings], None]


class PrintCenterDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_page: PrintPageSettings | None = None,
        initial_preferences: PrintExportPreferences | None = None,
        language: AppLanguage = AppLanguage.RU,
        source_name: str = "visualization",
        preview_callback: PreviewCallback | None = None,
        supports_pagination: bool = False,
        current_vertical_range: tuple[float, float] | None = None,
        full_vertical_range: tuple[float, float] | None = None,
        selected_vertical_range: tuple[float, float] | None = None,
        vertical_unit: str = "",
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.preview_callback = preview_callback
        self.supports_pagination = supports_pagination
        self.current_vertical_range = current_vertical_range
        self.full_vertical_range = full_vertical_range
        self.selected_vertical_range = selected_vertical_range
        self.vertical_unit = vertical_unit.strip()
        page = initial_page or PrintPageSettings()
        preferences = initial_preferences or PrintExportPreferences()
        self.source_name = _safe_file_stem(source_name)
        self.setWindowTitle(self._t("print_center.title"))
        self.resize(700, 900)

        root = QVBoxLayout(self)
        source_label = QLabel(self._t("print_center.source", name=source_name))
        source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(source_label)

        output_group = QGroupBox(self._t("print_center.output_group"))
        output_layout = QFormLayout(output_group)
        self.output_combo = QComboBox()
        for output in available_output_formats():
            self.output_combo.addItem(self._output_name(output), output.value)
        index = self.output_combo.findData(preferences.output_format.value)
        if index < 0:
            index = self.output_combo.findData(PrintOutputFormat.PDF.value)
        self.output_combo.setCurrentIndex(max(0, index))
        self.output_combo.currentIndexChanged.connect(self._output_changed)
        output_layout.addRow(self._t("print_center.output"), self.output_combo)

        path_widget = QHBoxLayout()
        self.path_input = QLineEdit()
        self.browse_button = QPushButton(self._t("print_center.browse"))
        self.browse_button.clicked.connect(self._browse)
        path_widget.addWidget(self.path_input, 1)
        path_widget.addWidget(self.browse_button)
        output_layout.addRow(self._t("print_center.file"), path_widget)

        self.dpi_combo = QComboBox()
        self.dpi_combo.setEditable(True)
        for dpi in (96, 150, 200, 300, 600):
            self.dpi_combo.addItem(f"{dpi} DPI", dpi)
        dpi_index = self.dpi_combo.findData(preferences.dpi)
        self.dpi_combo.setCurrentIndex(max(0, dpi_index))
        output_layout.addRow(self._t("print_center.resolution"), self.dpi_combo)

        self.quality_input = QSpinBox()
        self.quality_input.setRange(1, 100)
        self.quality_input.setSuffix(" %")
        self.quality_input.setValue(preferences.image_quality)
        output_layout.addRow(self._t("print_center.image_quality"), self.quality_input)
        root.addWidget(output_group)

        paper_group = QGroupBox(self._t("print_center.paper_group"))
        paper_layout = QFormLayout(paper_group)
        self.format_combo = QComboBox()
        self.format_combo.addItem("A4", PrintPageFormat.A4.value)
        self.format_combo.addItem("A3", PrintPageFormat.A3.value)
        self.format_combo.addItem(self._t("print.custom"), PrintPageFormat.CUSTOM.value)
        self.format_combo.addItem(self._t("print.roll"), PrintPageFormat.ROLL.value)
        self.format_combo.setCurrentIndex(self.format_combo.findData(page.page_format.value))
        self.format_combo.currentIndexChanged.connect(self._update_enabled)
        paper_layout.addRow(self._t("print.page_format"), self.format_combo)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(self._t("print.portrait"), PrintOrientation.PORTRAIT.value)
        self.orientation_combo.addItem(self._t("print.landscape"), PrintOrientation.LANDSCAPE.value)
        self.orientation_combo.setCurrentIndex(
            self.orientation_combo.findData(page.orientation.value)
        )
        paper_layout.addRow(self._t("print.orientation"), self.orientation_combo)

        dimensions = QHBoxLayout()
        self.width_input = self._dimension_input(page.custom_width_mm)
        self.height_input = self._dimension_input(page.custom_height_mm)
        dimensions.addWidget(QLabel(self._t("print.width_mm")))
        dimensions.addWidget(self.width_input)
        dimensions.addWidget(QLabel(self._t("print.height_mm")))
        dimensions.addWidget(self.height_input)
        paper_layout.addRow(self._t("print_center.custom_size"), dimensions)

        self.scale_combo = QComboBox()
        self.scale_combo.addItem(self._t("print_center.scale_fit"), PrintScaleMode.FIT.value)
        self.scale_combo.addItem(
            self._t("print_center.scale_actual"), PrintScaleMode.ACTUAL_SIZE.value
        )
        scale_index = self.scale_combo.findData(page.scale_mode.value)
        self.scale_combo.setCurrentIndex(max(0, scale_index))
        self.scale_combo.currentIndexChanged.connect(self._update_enabled)
        paper_layout.addRow(self._t("print_center.scale_mode"), self.scale_combo)

        self.fit_columns_check = QCheckBox(self._t("print.fit_form_columns"))
        self.fit_columns_check.setChecked(page.fit_form_columns)
        self.fit_columns_check.setToolTip(self._t("print.fit_form_columns_tooltip"))
        paper_layout.addRow(self.fit_columns_check)

        self.continuation_overlap_input = self._continuation_input(
            page.continuation_overlap_mm
        )
        self.continuation_overlap_input.setToolTip(
            self._t("print_center.continuation_overlap_tooltip")
        )
        paper_layout.addRow(
            self._t("print_center.continuation_overlap"),
            self.continuation_overlap_input,
        )
        root.addWidget(paper_group)

        pagination_group = QGroupBox(self._t("print_center.pagination_group"))
        pagination_layout = QFormLayout(pagination_group)
        self.range_combo = QComboBox()
        self.range_combo.addItem(
            self._t("print_center.range_current"), PrintRangeMode.CURRENT.value
        )
        self.range_combo.addItem(self._t("print_center.range_full"), PrintRangeMode.FULL.value)
        if selected_vertical_range is not None:
            self.range_combo.addItem(
                self._t("print_center.range_selection"),
                PrintRangeMode.SELECTION.value,
            )
        self.range_combo.addItem(self._t("print_center.range_custom"), PrintRangeMode.CUSTOM.value)
        requested_range = preferences.range_mode if supports_pagination else PrintRangeMode.CURRENT
        if (
            requested_range is PrintRangeMode.SELECTION
            and selected_vertical_range is None
        ):
            requested_range = PrintRangeMode.CURRENT
        range_index = self.range_combo.findData(requested_range.value)
        self.range_combo.setCurrentIndex(max(0, range_index))
        self.range_combo.setEnabled(supports_pagination)
        self.range_combo.currentIndexChanged.connect(self._update_pagination_enabled)
        pagination_layout.addRow(self._t("print_center.range_mode"), self.range_combo)

        default_span = preferences.units_per_page
        if default_span <= 0 and current_vertical_range is not None:
            default_span = abs(current_vertical_range[1] - current_vertical_range[0])
        self.units_per_page_input = self._axis_value_input(max(default_span, 1e-6))
        self.units_per_page_input.setSuffix(f" {self.vertical_unit}" if self.vertical_unit else "")
        pagination_layout.addRow(self._t("print_center.units_per_page"), self.units_per_page_input)

        self.overlap_input = self._axis_value_input(preferences.overlap, allow_zero=True)
        self.overlap_input.setSuffix(f" {self.vertical_unit}" if self.vertical_unit else "")
        pagination_layout.addRow(self._t("print_center.page_overlap"), self.overlap_input)

        custom_row = QHBoxLayout()
        custom_start_default = preferences.custom_start
        custom_end_default = preferences.custom_end
        if custom_start_default is None or custom_end_default is None:
            fallback = current_vertical_range or full_vertical_range or (0.0, 1.0)
            custom_start_default, custom_end_default = fallback
        self.custom_start_input = self._axis_value_input(custom_start_default, signed=True)
        self.custom_end_input = self._axis_value_input(custom_end_default, signed=True)
        custom_row.addWidget(QLabel(self._t("print_center.range_start")))
        custom_row.addWidget(self.custom_start_input)
        custom_row.addWidget(QLabel(self._t("print_center.range_end")))
        custom_row.addWidget(self.custom_end_input)
        pagination_layout.addRow(self._t("print_center.custom_range"), custom_row)

        self.page_numbers_check = QCheckBox(self._t("print_center.show_page_numbers"))
        self.page_numbers_check.setChecked(preferences.show_page_numbers)
        pagination_layout.addRow(self.page_numbers_check)
        self.page_range_check = QCheckBox(self._t("print_center.show_page_range"))
        self.page_range_check.setChecked(preferences.show_page_range)
        pagination_layout.addRow(self.page_range_check)
        root.addWidget(pagination_group)

        margins_group = QGroupBox(self._t("print_center.margins_group"))
        margins_layout = QGridLayout(margins_group)
        self.margin_left_input = self._margin_input(page.margin_left_mm)
        self.margin_top_input = self._margin_input(page.margin_top_mm)
        self.margin_right_input = self._margin_input(page.margin_right_mm)
        self.margin_bottom_input = self._margin_input(page.margin_bottom_mm)
        margin_controls = (
            (self._t("print_center.margin_left"), self.margin_left_input, 0, 0),
            (self._t("print_center.margin_top"), self.margin_top_input, 0, 2),
            (self._t("print_center.margin_right"), self.margin_right_input, 1, 0),
            (self._t("print_center.margin_bottom"), self.margin_bottom_input, 1, 2),
        )
        for label, control, row, column in margin_controls:
            margins_layout.addWidget(QLabel(label), row, column)
            margins_layout.addWidget(control, row, column + 1)
        root.addWidget(margins_group)

        self.unicode_status = QLabel(self._t("print_center.unicode_preflight_hint"))
        self.unicode_status.setWordWrap(True)
        root.addWidget(self.unicode_status)

        hint = QLabel(self._t("print_center.hint"))
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.preview_button = self.buttons.addButton(
            self._t("print_center.preview"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.preview_button.clicked.connect(self._preview)
        self.buttons.accepted.connect(self._accept_checked)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.setText(self._t("common.cancel"))
        root.addWidget(self.buttons)

        self._output_changed()
        self._update_enabled()
        self._update_pagination_enabled()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _output_name(self, output: PrintOutputFormat) -> str:
        return self._t(f"print_center.output_{output.value}")

    def selected_output(self) -> PrintOutputFormat:
        return PrintOutputFormat(str(self.output_combo.currentData()))

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

    def pagination_settings(self) -> PrintPaginationSettings:
        mode = PrintRangeMode(str(self.range_combo.currentData()))
        if not self.supports_pagination:
            mode = PrintRangeMode.CURRENT
        return PrintPaginationSettings(
            range_mode=mode,
            units_per_page=self.units_per_page_input.value(),
            overlap=self.overlap_input.value(),
            custom_start=self.custom_start_input.value() if mode is PrintRangeMode.CUSTOM else None,
            custom_end=self.custom_end_input.value() if mode is PrintRangeMode.CUSTOM else None,
            show_page_numbers=self.page_numbers_check.isChecked(),
            show_page_range=self.page_range_check.isChecked(),
        )

    def preferences(self) -> PrintExportPreferences:
        output = self.selected_output()
        persistent_output = PrintOutputFormat.PDF if output is PrintOutputFormat.PRINTER else output
        pagination = self.pagination_settings()
        return PrintExportPreferences(
            output_format=persistent_output,
            dpi=self._dpi(),
            image_quality=self.quality_input.value(),
            range_mode=pagination.range_mode,
            units_per_page=pagination.units_per_page,
            overlap=pagination.overlap,
            custom_start=pagination.custom_start,
            custom_end=pagination.custom_end,
            show_page_numbers=pagination.show_page_numbers,
            show_page_range=pagination.show_page_range,
        )

    def job_settings(self, *, allow_missing_target: bool = False) -> PrintJobSettings:
        output = self.selected_output()
        target: Path | None = None
        if output.is_file:
            raw = self.path_input.text().strip()
            if not raw and not allow_missing_target:
                raise ValueError(self._t("print_center.choose_file_error"))
            if raw:
                target = Path(raw)
            elif allow_missing_target:
                target = Path.cwd() / f"{self.source_name}{output.suffix}"
            if target is not None and target.suffix.casefold() not in output.accepted_suffixes:
                target = target.with_suffix(output.suffix)
        return PrintJobSettings(
            output_format=output,
            page=self.page_settings(),
            dpi=self._dpi(),
            image_quality=self.quality_input.value(),
            target=target,
            pagination=self.pagination_settings(),
            strict_unicode=True,
        )

    def _dpi(self) -> int:
        data = self.dpi_combo.currentData()
        if isinstance(data, int) and self.dpi_combo.currentText().startswith(str(data)):
            return data
        text = self.dpi_combo.currentText().upper().replace("DPI", "").strip()
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(self._t("print_center.dpi_error")) from exc

    def _output_changed(self, _index: int | None = None) -> None:
        output = self.selected_output()
        file_enabled = output.is_file
        self.path_input.setEnabled(file_enabled)
        self.browse_button.setEnabled(file_enabled)
        self.dpi_combo.setEnabled(output is not PrintOutputFormat.SVG)
        self.quality_input.setEnabled(output in {PrintOutputFormat.JPEG, PrintOutputFormat.WEBP})
        self.ok_button.setText(
            self._t("print_center.print")
            if output is PrintOutputFormat.PRINTER
            else self._t("print_center.export")
        )
        if file_enabled:
            current = Path(self.path_input.text()) if self.path_input.text().strip() else None
            if current is None:
                current = Path.cwd() / f"{self.source_name}{output.suffix}"
            elif current.suffix.casefold() not in output.accepted_suffixes:
                current = current.with_suffix(output.suffix)
            self.path_input.setText(str(current))

    def _update_enabled(self, _index: int | None = None) -> None:
        selected = PrintPageFormat(str(self.format_combo.currentData()))
        scale_mode = PrintScaleMode(str(self.scale_combo.currentData()))
        self.width_input.setEnabled(selected in {PrintPageFormat.CUSTOM, PrintPageFormat.ROLL})
        self.height_input.setEnabled(selected is PrintPageFormat.CUSTOM)
        self.orientation_combo.setEnabled(selected is not PrintPageFormat.ROLL)
        self.fit_columns_check.setEnabled(scale_mode is PrintScaleMode.FIT)
        self.continuation_overlap_input.setEnabled(
            scale_mode is PrintScaleMode.ACTUAL_SIZE
        )

    def _update_pagination_enabled(self, _index: int | None = None) -> None:
        mode = PrintRangeMode(str(self.range_combo.currentData()))
        multipage = self.supports_pagination and mode is not PrintRangeMode.CURRENT
        custom = self.supports_pagination and mode is PrintRangeMode.CUSTOM
        self.units_per_page_input.setEnabled(multipage)
        self.overlap_input.setEnabled(multipage)
        self.custom_start_input.setEnabled(custom)
        self.custom_end_input.setEnabled(custom)
        self.page_range_check.setEnabled(self.supports_pagination)

    def _browse(self) -> None:
        output = self.selected_output()
        if not output.is_file:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("print_center.choose_file"),
            self.path_input.text(),
            output.file_filter,
        )
        if filename:
            target = Path(filename)
            if target.suffix.casefold() not in output.accepted_suffixes:
                target = target.with_suffix(output.suffix)
            self.path_input.setText(str(target))

    def _preview(self) -> None:
        if self.preview_callback is None:
            return
        try:
            self.preview_callback(self.job_settings(allow_missing_target=True))
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _accept_checked(self) -> None:
        try:
            self.job_settings()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()

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

    @staticmethod
    def _axis_value_input(
        value: float,
        *,
        allow_zero: bool = False,
        signed: bool = False,
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        minimum = -1e12 if signed else (0.0 if allow_zero else 1e-6)
        control.setRange(minimum, 1e12)
        control.setDecimals(6)
        control.setValue(float(value))
        return control


def _safe_file_stem(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in value
    )
    return cleaned.strip("_-")[:120] or "visualization"
