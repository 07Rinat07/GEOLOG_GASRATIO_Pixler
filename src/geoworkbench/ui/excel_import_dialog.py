from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
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


class ExcelImportDialog(QDialog):
    def __init__(self, source: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self.setWindowTitle(f"Импорт Excel — {source.name}")
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.sheet = QComboBox()
        self.header_row = QSpinBox()
        self.header_row.setRange(1, 1_000_000)
        self.header_row.setValue(1)
        self.index_column = QComboBox()
        form.addRow("Лист", self.sheet)
        form.addRow("Строка заголовка", self.header_row)
        form.addRow("Индексная колонка", self.index_column)
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
        root.addWidget(buttons)
        self.sheet.currentTextChanged.connect(self._refresh)
        self.header_row.valueChanged.connect(self._refresh)
        self._load_sheets()

    def import_plan(self) -> ExcelImportPlan:
        return ExcelImportPlan(
            sheet_name=self.sheet.currentText(),
            header_row=self.header_row.value(),
            index_column=self.index_column.currentText().strip() or None,
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
        try:
            result = probe_excel(
                self.source,
                sheet_name=self.sheet.currentText(),
                header_row=self.header_row.value(),
            )
        except (ExcelImportError, FileNotFoundError) as exc:
            self.status.setText(str(exc))
            return
        self._show_probe(result, previous)

    def _show_probe(self, result: ExcelProbe, previous: str = "") -> None:
        sheet_number = (
            result.sheet_names.index(self.sheet.currentText()) + 1
            if self.sheet.currentText() in result.sheet_names
            else 1
        )
        self.status.setText(f"Лист: {sheet_number}; колонок: {len(result.columns)}")
        self.index_column.clear()
        self.index_column.addItems(result.columns)
        if previous in result.columns:
            self.index_column.setCurrentText(previous)
        self.preview.setColumnCount(len(result.columns))
        self.preview.setHorizontalHeaderLabels(result.columns)
        self.preview.setRowCount(len(result.preview_rows))
        for row, values in enumerate(result.preview_rows):
            for column, value in enumerate(values):
                self.preview.setItem(row, column, QTableWidgetItem(value))

    def _accept_if_valid(self) -> None:
        if not self.index_column.currentText().strip():
            self.status.setText("Выберите индексную колонку")
            return
        self.accept()
