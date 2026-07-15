from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
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
        form.addRow("Кодировка", self.encoding)
        form.addRow("Разделитель", self.delimiter)
        form.addRow("Индексная колонка", self.index_column)
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

    def import_plan(self) -> CsvImportPlan:
        index = self.index_column.currentText().strip() or None
        delimiter = self.delimiter.currentData()
        return CsvImportPlan(
            encoding=self.encoding.currentText(),
            delimiter=delimiter if isinstance(delimiter, str) else None,
            index_column=index,
        )

    def _refresh_probe(self) -> None:
        previous_index = self.index_column.currentText()
        try:
            result = probe_csv(self.source, self.import_plan())
        except (CsvImportError, FileNotFoundError, ValueError) as exc:
            self.status.setText(str(exc))
            self.index_column.clear()
            self.preview.clear()
            self.preview.setRowCount(0)
            self.preview.setColumnCount(0)
            return
        self.status.setText(
            f"Определён разделитель {result.delimiter!r}; показано до {len(result.preview_rows)} строк"
        )
        self.index_column.clear()
        self.index_column.addItems(result.columns)
        if previous_index in result.columns:
            self.index_column.setCurrentText(previous_index)
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
        self.accept()
