from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
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
HeaderCatalogCallback = Callable[[], tuple[tuple[str, str], ...]]
HeaderPreviewCallback = Callable[[str], QPixmap | None]
HeaderEditCallback = Callable[[str], None]


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
        header_choices: tuple[tuple[str, str], ...] = (),
        initial_header_template_id: str | None = None,
        paired_header_template_ids: dict[str, str] | None = None,
        manage_headers_callback: HeaderCatalogCallback | None = None,
        header_preview_callback: HeaderPreviewCallback | None = None,
        edit_header_callback: HeaderEditCallback | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.preview_callback = preview_callback
        self.supports_pagination = supports_pagination
        self.current_vertical_range = current_vertical_range
        self.full_vertical_range = full_vertical_range
        self.selected_vertical_range = selected_vertical_range
        self.vertical_unit = vertical_unit.strip()
        self.header_choices = tuple(header_choices)
        self.paired_header_template_ids = {
            str(orientation).strip().casefold(): str(template_id).strip()
            for orientation, template_id in (paired_header_template_ids or {}).items()
            if str(orientation).strip().casefold() in {"portrait", "landscape"}
            and str(template_id).strip()
        }
        self.manage_headers_callback = manage_headers_callback
        self.header_preview_callback = header_preview_callback
        self.edit_header_callback = edit_header_callback
        page = initial_page or PrintPageSettings()
        preferences = initial_preferences or PrintExportPreferences()
        self.source_name = _safe_file_stem(source_name)
        self.setWindowTitle(self._t("print_center.title"))
        self.setMinimumSize(600, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        source_label = QLabel(self._t("print_center.source", name=source_name))
        source_label.setObjectName("print-center-source")
        source_label.setStyleSheet("font-weight: 600;")
        source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(source_label)

        content = QWidget()
        content.setObjectName("print-center-settings")
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(10)

        header_group = QGroupBox(
            {
                AppLanguage.RU: "Печатная шапка",
                AppLanguage.KK: "Баспа тақырыбы",
                AppLanguage.EN: "Print header",
            }[language]
        )
        header_layout = QVBoxLayout(header_group)
        header_controls = QHBoxLayout()
        self.header_combo = QComboBox()
        self.header_combo.setObjectName("print-header-template-combo")
        self.header_combo.currentIndexChanged.connect(self._refresh_header_preview)
        self.manage_headers_button = QPushButton(
            {
                AppLanguage.RU: "Каталог шапок...",
                AppLanguage.KK: "Тақырыптар каталогы...",
                AppLanguage.EN: "Header catalog...",
            }[language]
        )
        self.manage_headers_button.clicked.connect(self._manage_headers)
        self.manage_headers_button.setEnabled(manage_headers_callback is not None)
        self.edit_header_button = QPushButton(
            {
                AppLanguage.RU: "Развернуть / редактировать...",
                AppLanguage.KK: "Ашу / өңдеу...",
                AppLanguage.EN: "Open / edit...",
            }[language]
        )
        self.edit_header_button.clicked.connect(self._open_header_editor)
        self.edit_header_button.setEnabled(False)
        header_controls.addWidget(self.header_combo, 1)
        header_controls.addWidget(self.manage_headers_button)
        header_controls.addWidget(self.edit_header_button)
        header_layout.addLayout(header_controls)
        self.header_preview = QLabel()
        self.header_preview.setObjectName("print-center-header-preview")
        self.header_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_preview.setMinimumHeight(68)
        self.header_preview.setMaximumHeight(180)
        self.header_preview.setStyleSheet(
            "QLabel { background: #e5e7eb; border: 1px solid #94a3b8; }"
        )
        header_layout.addWidget(self.header_preview)
        paired_initial = self.paired_header_template_ids.get(
            page.orientation.value, initial_header_template_id
        )
        self._set_header_choices(self.header_choices, paired_initial)
        self._refresh_header_preview()

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
        content_layout.addWidget(output_group)

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
        self.orientation_combo.currentIndexChanged.connect(self._sync_paired_header_to_orientation)
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

        self.repeat_column_header_check = QCheckBox(
            self._t("print_center.repeat_column_header_bottom")
        )
        self.repeat_column_header_check.setChecked(preferences.repeat_column_header_at_bottom)
        self.repeat_column_header_check.setToolTip(
            self._t("print_center.repeat_column_header_bottom_tooltip")
        )
        paper_layout.addRow(self.repeat_column_header_check)

        self.continuation_overlap_input = self._continuation_input(page.continuation_overlap_mm)
        self.continuation_overlap_input.setToolTip(
            self._t("print_center.continuation_overlap_tooltip")
        )
        paper_layout.addRow(
            self._t("print_center.continuation_overlap"),
            self.continuation_overlap_input,
        )
        content_layout.addWidget(paper_group)

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
        if requested_range is PrintRangeMode.SELECTION and selected_vertical_range is None:
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
        content_layout.addWidget(pagination_group)

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
        content_layout.addWidget(margins_group)

        # Header selection is secondary to the output and page settings.  Keeping
        # it below those controls makes the destination immediately discoverable,
        # while the empty preview no longer consumes most of a short screen.
        content_layout.addWidget(header_group)

        self.unicode_status = QLabel(self._t("print_center.unicode_preflight_hint"))
        self.unicode_status.setWordWrap(True)
        self.unicode_status.setObjectName("print-center-unicode-status")
        content_layout.addWidget(self.unicode_status)

        hint = QLabel(self._t("print_center.hint"))
        hint.setWordWrap(True)
        hint.setObjectName("print-center-hint")
        content_layout.addWidget(hint)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("print-center-settings-scroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.settings_scroll.setWidget(content)
        root.addWidget(self.settings_scroll, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(separator)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.preview_button = self.buttons.addButton(
            self._t("print_center.preview"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.preview_button.clicked.connect(self._preview)
        self.preview_button.setEnabled(preview_callback is not None)
        self.buttons.accepted.connect(self._accept_checked)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.setText(self._t("common.cancel"))

        for button in (self.preview_button, self.ok_button, self.cancel_button):
            button.setMinimumHeight(36)
        self.ok_button.setObjectName("print-center-primary-action")
        self.ok_button.setMinimumWidth(160)
        self.ok_button.setDefault(True)
        self.ok_button.setStyleSheet(
            "QPushButton#print-center-primary-action {"
            "background:#155e75; color:#ffffff; border:1px solid #22d3ee; "
            "border-radius:5px; padding:7px 18px; font-weight:700;}"
            "QPushButton#print-center-primary-action:hover {background:#0e7490;}"
            "QPushButton#print-center-primary-action:pressed {background:#164e63;}"
            "QPushButton#print-center-primary-action:disabled {"
            "background:#475569; color:#cbd5e1; border-color:#64748b;}"
        )

        self.action_summary = QLabel()
        self.action_summary.setObjectName("print-center-action-summary")
        self.action_summary.setStyleSheet("font-weight: 600;")
        self.action_summary.setWordWrap(True)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("print-center-action-bar")
        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(12)
        action_layout.addWidget(self.action_summary, 1)
        action_layout.addWidget(self.buttons)
        root.addWidget(self.action_bar)

        self._output_changed()
        self._update_enabled()
        self._update_pagination_enabled()
        self._apply_adaptive_size()

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
            repeat_column_header_at_bottom=(self.repeat_column_header_check.isChecked()),
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
            header_template_id=(
                str(self.header_combo.currentData())
                if isinstance(self.header_combo.currentData(), str)
                and str(self.header_combo.currentData()).strip()
                else None
            ),
            repeat_column_header_at_bottom=(self.repeat_column_header_check.isChecked()),
        )

    def _set_header_choices(
        self,
        choices: tuple[tuple[str, str], ...],
        selected_id: str | None = None,
    ) -> None:
        current = selected_id
        if current is None:
            data = self.header_combo.currentData() if hasattr(self, "header_combo") else None
            current = str(data) if isinstance(data, str) else None
        self.header_combo.blockSignals(True)
        self.header_combo.clear()
        self.header_combo.addItem(
            {
                AppLanguage.RU: "Без печатной шапки",
                AppLanguage.KK: "Баспа тақырыбынсыз",
                AppLanguage.EN: "No print header",
            }[self.localizer.language],
            None,
        )
        for catalog_id, label in choices:
            self.header_combo.addItem(label, catalog_id)
        index = self.header_combo.findData(current) if current else 0
        self.header_combo.setCurrentIndex(max(0, index))
        self.header_combo.blockSignals(False)

    def _sync_paired_header_to_orientation(self, _index: int = -1) -> None:
        orientation = str(self.orientation_combo.currentData()).strip().casefold()
        paired_id = self.paired_header_template_ids.get(orientation)
        if paired_id is None:
            return
        index = self.header_combo.findData(paired_id)
        if index >= 0:
            self.header_combo.setCurrentIndex(index)

    def _manage_headers(self) -> None:
        if self.manage_headers_callback is None:
            return
        current = self.header_combo.currentData()
        try:
            choices = self.manage_headers_callback()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.header_choices = tuple(choices)
        self._set_header_choices(
            self.header_choices,
            str(current) if isinstance(current, str) else None,
        )
        self._refresh_header_preview()

    def _refresh_header_preview(self, _index: int | None = None) -> None:
        raw = self.header_combo.currentData()
        catalog_id = str(raw) if isinstance(raw, str) and raw.strip() else None
        self.edit_header_button.setEnabled(
            catalog_id is not None and self.edit_header_callback is not None
        )
        if catalog_id is None or self.header_preview_callback is None:
            self._set_header_preview_expanded(False)
            self.header_preview.clear()
            self.header_preview.setText(
                {
                    AppLanguage.RU: "Шапка не выбрана",
                    AppLanguage.KK: "Тақырып таңдалмады",
                    AppLanguage.EN: "No header selected",
                }[self.localizer.language]
            )
            return
        try:
            pixmap = self.header_preview_callback(catalog_id)
        except (KeyError, RuntimeError, ValueError):
            pixmap = None
        if pixmap is None or pixmap.isNull():
            self._set_header_preview_expanded(False)
            self.header_preview.clear()
            self.header_preview.setText(
                {
                    AppLanguage.RU: "Предпросмотр недоступен",
                    AppLanguage.KK: "Алдын ала қарау қолжетімсіз",
                    AppLanguage.EN: "Preview unavailable",
                }[self.localizer.language]
            )
            return
        self._set_header_preview_expanded(True)
        target = QSize(max(240, self.header_preview.width() - 12), 152)
        self.header_preview.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_header_preview_expanded(self, expanded: bool) -> None:
        minimum = 132 if expanded else 68
        maximum = 180 if expanded else 68
        self.header_preview.setMinimumHeight(minimum)
        self.header_preview.setMaximumHeight(maximum)

    def _open_header_editor(self) -> None:
        raw = self.header_combo.currentData()
        if not isinstance(raw, str) or not raw.strip() or self.edit_header_callback is None:
            return
        self.edit_header_callback(raw)
        self._refresh_header_preview()

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
        self.action_summary.setText(
            f"{self._t('print_center.output')}: {self._output_name(output)}"
        )
        if file_enabled:
            current = Path(self.path_input.text()) if self.path_input.text().strip() else None
            if current is None:
                current = Path.cwd() / f"{self.source_name}{output.suffix}"
            elif current.suffix.casefold() not in output.accepted_suffixes:
                current = current.with_suffix(output.suffix)
            self.path_input.setText(str(current))

    def _apply_adaptive_size(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(900, 760)
            return
        available = screen.availableGeometry()
        self.resize(
            min(960, max(600, int(available.width() * 0.72))),
            min(860, max(480, int(available.height() * 0.82))),
        )

    def _update_enabled(self, _index: int | None = None) -> None:
        selected = PrintPageFormat(str(self.format_combo.currentData()))
        scale_mode = PrintScaleMode(str(self.scale_combo.currentData()))
        self.width_input.setEnabled(selected in {PrintPageFormat.CUSTOM, PrintPageFormat.ROLL})
        self.height_input.setEnabled(selected is PrintPageFormat.CUSTOM)
        self.orientation_combo.setEnabled(selected is not PrintPageFormat.ROLL)
        self.fit_columns_check.setEnabled(scale_mode is PrintScaleMode.FIT)
        self.continuation_overlap_input.setEnabled(scale_mode is PrintScaleMode.ACTUAL_SIZE)

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
