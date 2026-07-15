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


class CsvImportDialog(QDialog):
    def __init__(self, source: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self.setWindowTitle(f"Импорт CSV — {source.name}")
        self.resize(760, 440)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8-sig", "utf-8", "cp1251", "latin-1"])
        self.delimiter = QComboBox()
        for label, value in (("Авто", None), (";", ";"), (",", ","), ("TAB", "\t"), ("|", "|")):
            self.delimiter.addItem(label, value)
        self.index_column = QComboBox()
        self.composite_time = QCheckBox("Объединить индексную колонку DATE с отдельной TIME")
        self.composite_time.toggled.connect(self._update_composite_controls)
        self.time_column = QComboBox()
        self.date_format = QLineEdit("%Y-%m-%d")
        self.time_format = QLineEdit("%H:%M:%S")
        self.timezone = QLineEdit()
        self.timezone.setPlaceholderText("например Asia/Oral или UTC+05:00")
        form.addRow("Кодировка", self.encoding)
        form.addRow("Разделитель", self.delimiter)
        form.addRow("Индексная колонка", self.index_column)
        form.addRow(self.composite_time)
        form.addRow("Колонка TIME", self.time_column)
        form.addRow("Формат DATE", self.date_format)
        form.addRow("Формат TIME", self.time_format)
        form.addRow("Часовой пояс", self.timezone)
        root.addLayout(form)
        refresh = QPushButton("Обновить предпросмотр")
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
        root.addWidget(buttons)
        self._refresh_probe()
        self._update_composite_controls(False)

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
            f"Определён разделитель {result.delimiter!r}; показано до {len(result.preview_rows)} строк"
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
            self.status.setText("Выберите индексную колонку")
            return
        if self.composite_time.isChecked() and (
            not self.time_column.currentText().strip()
            or self.time_column.currentText() == self.index_column.currentText()
        ):
            self.status.setText("Для DATE+TIME выберите две разные колонки")
            return
        self.accept()

    def _update_composite_controls(self, enabled: bool) -> None:
        for widget in (self.time_column, self.date_format, self.time_format, self.timezone):
            widget.setEnabled(enabled)
