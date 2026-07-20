from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.csv_adapter import CsvImportError, CsvImportPlan, probe_csv
from geoworkbench.services.localization import AppLanguage, Localizer


class CsvImportDialog(QDialog):
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
        self.setWindowTitle(self._t("csv.title", name=source.name))
        self.resize(760, 440)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8-sig", "utf-8", "cp1251", "latin-1"])
        self.delimiter = QComboBox()
        for label, value in (
            (self._t("common.auto"), None),
            (";", ";"),
            (",", ","),
            ("TAB", "\t"),
            ("|", "|"),
        ):
            self.delimiter.addItem(label, value)
        self.index_column = QComboBox()
        self.composite_time = QCheckBox(self._t("import.combine_datetime"))
        self.composite_time.toggled.connect(self._update_composite_controls)
        self.time_column = QComboBox()
        self.date_format = QLineEdit("%Y-%m-%d")
        self.time_format = QLineEdit("%H:%M:%S")
        self.timezone = QLineEdit()
        self.timezone.setPlaceholderText(self._t("import.timezone_example"))
        form.addRow(self._t("csv.encoding"), self.encoding)
        form.addRow(self._t("csv.delimiter"), self.delimiter)
        form.addRow(self._t("import.index_column"), self.index_column)
        form.addRow(self.composite_time)
        form.addRow(self._t("import.time_column"), self.time_column)
        form.addRow(self._t("import.date_format"), self.date_format)
        form.addRow(self._t("import.time_format"), self.time_format)
        form.addRow(self._t("import.timezone"), self.timezone)
        root.addLayout(form)
        refresh = QPushButton(self._t("import.refresh_preview"))
        refresh.clicked.connect(self._refresh_probe)
        root.addWidget(refresh)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.preview = QTableWidget()
        self.preview.setObjectName("csv-preview")
        root.addWidget(self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        root.addWidget(buttons)
        self._refresh_probe()
        self._update_composite_controls(False)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def import_plan(self) -> CsvImportPlan:
        index = self.index_column.currentText().strip() or None
        delimiter = self.delimiter.currentData()
        return CsvImportPlan(
            encoding=self.encoding.currentText(),
            delimiter=delimiter if isinstance(delimiter, str) else None,
            index_column=index,
            time_column=(
                self.time_column.currentText().strip() or None
                if self.composite_time.isChecked()
                else None
            ),
            date_format=self.date_format.text().strip(),
            time_format=self.time_format.text().strip(),
            timezone=self.timezone.text().strip() or None,
        )

    def _refresh_probe(self) -> None:
        previous_index = self.index_column.currentText()
        previous_time = self.time_column.currentText()
        try:
            result = probe_csv(self.source, self.import_plan())
        except (CsvImportError, FileNotFoundError, ValueError) as exc:
            self.status.setText(str(exc))
            self.index_column.clear()
            self.time_column.clear()
            self.preview.clear()
            self.preview.setRowCount(0)
            self.preview.setColumnCount(0)
            return
        self.status.setText(
            self._t(
                "csv.preview_status",
                delimiter=repr(result.delimiter),
                rows=len(result.preview_rows),
            )
        )
        self.index_column.clear()
        self.index_column.addItems(result.columns)
        self.time_column.clear()
        self.time_column.addItems(result.columns)
        if previous_index in result.columns:
            self.index_column.setCurrentText(previous_index)
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
        self.preview.resizeColumnsToContents()

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
