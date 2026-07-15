from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.excel_adapter import (
    ExcelImportError,
    ExcelImportPlan,
    ExcelProbe,
    excel_sheet_names,
    probe_excel,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class ExcelImportDialog(QDialog):
    def __init__(
        self,
        source: Path,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.source = source
        self.setWindowTitle(self._t("excel.title", name=source.name))
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.sheet = QComboBox()
        self.header_row = QSpinBox()
        self.header_row.setRange(1, 1_000_000)
        self.header_row.setValue(1)
        self.index_column = QComboBox()
        self.composite_time = QCheckBox(self._t("import.combine_datetime"))
        self.composite_time.toggled.connect(self._update_composite_controls)
        self.time_column = QComboBox()
        self.date_format = QLineEdit("%Y-%m-%d")
        self.time_format = QLineEdit("%H:%M:%S")
        self.timezone = QLineEdit()
        self.timezone.setPlaceholderText(self._t("import.timezone_example"))
        form.addRow(self._t("excel.sheet"), self.sheet)
        form.addRow(self._t("excel.header_row"), self.header_row)
        form.addRow(self._t("import.index_column"), self.index_column)
        form.addRow(self.composite_time)
        form.addRow(self._t("import.time_column"), self.time_column)
        form.addRow(self._t("import.date_format"), self.date_format)
        form.addRow(self._t("import.time_format"), self.time_format)
        form.addRow(self._t("import.timezone"), self.timezone)
        root.addLayout(form)
        self.status = QLabel()
        root.addWidget(self.status)
        self.preview = QTableWidget()
        root.addWidget(self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        root.addWidget(buttons)
        self.sheet.currentTextChanged.connect(self._refresh)
        self.header_row.valueChanged.connect(self._refresh)
        self._load_sheets()
        self._update_composite_controls(False)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def import_plan(self) -> ExcelImportPlan:
        return ExcelImportPlan(
            sheet_name=self.sheet.currentText(),
            header_row=self.header_row.value(),
            index_column=self.index_column.currentText().strip() or None,
            time_column=(
                self.time_column.currentText().strip() or None
                if self.composite_time.isChecked()
                else None
            ),
            date_format=self.date_format.text().strip(),
            time_format=self.time_format.text().strip(),
            timezone=self.timezone.text().strip() or None,
        )

    def _load_sheets(self) -> None:
        try:
            sheets = excel_sheet_names(self.source)
        except (ExcelImportError, FileNotFoundError) as exc:
            self.status.setText(str(exc))
            return
        self.sheet.addItems(sheets)
        self._refresh()

    def _refresh(self) -> None:
        if not self.sheet.currentText():
            return
        previous = self.index_column.currentText()
        previous_time = self.time_column.currentText()
        try:
            result = probe_excel(
                self.source,
                sheet_name=self.sheet.currentText(),
                header_row=self.header_row.value(),
            )
        except (ExcelImportError, FileNotFoundError) as exc:
            self.status.setText(str(exc))
            return
        self._show_probe(result, previous, previous_time)

    def _show_probe(
        self,
        result: ExcelProbe,
        previous: str = "",
        previous_time: str = "",
    ) -> None:
        sheet_number = (
            result.sheet_names.index(self.sheet.currentText()) + 1
            if self.sheet.currentText() in result.sheet_names
            else 1
        )
        self.status.setText(
            self._t("excel.preview_status", sheet=sheet_number, columns=len(result.columns))
        )
        self.index_column.clear()
        self.index_column.addItems(result.columns)
        self.time_column.clear()
        self.time_column.addItems(result.columns)
        if previous in result.columns:
            self.index_column.setCurrentText(previous)
        if previous_time in result.columns:
            self.time_column.setCurrentText(previous_time)
        elif len(result.columns) > 1:
            self.time_column.setCurrentIndex(1)
        self.preview.setColumnCount(len(result.columns))
        self.preview.setHorizontalHeaderLabels(result.columns)
        self.preview.setRowCount(len(result.preview_rows))
        for row, values in enumerate(result.preview_rows):
            for column, value in enumerate(values):
                self.preview.setItem(row, column, QTableWidgetItem(value))

    def _accept_if_valid(self) -> None:
        if not self.index_column.currentText().strip():
            self.status.setText(self._t("import.select_index"))
            return
        if self.composite_time.isChecked() and (
            not self.time_column.currentText().strip()
            or self.time_column.currentText() == self.index_column.currentText()
        ):
            self.status.setText(self._t("import.select_distinct_datetime"))
            return
        self.accept()

    def _update_composite_controls(self, enabled: bool) -> None:
        for widget in (self.time_column, self.date_format, self.time_format, self.timezone):
            widget.setEnabled(enabled)
