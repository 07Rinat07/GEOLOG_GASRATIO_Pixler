from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.data_inspector_controller import DataInspectorController


class DataInspectorDialog(QDialog):
    def __init__(self, controller: DataInspectorController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Сведения о данных и индексах")
        self.resize(980, 620)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.summary_text = QPlainTextEdit()
        self.summary_text.setObjectName("data-summary")
        self.summary_text.setReadOnly(True)
        self.tabs.addTab(self.summary_text, "Сводка")

        indexes_page = QWidget()
        indexes_layout = QVBoxLayout(indexes_page)
        self.index_table = QTableWidget(0, 9)
        self.index_table.setObjectName("data-indexes")
        self.index_table.setHorizontalHeaderLabels(
            ["Активный", "Мнемоника", "Тип", "Роль", "Единица", "Точек", "Начало", "Конец", "Confidence"]
        )
        self.index_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.index_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.index_table.itemSelectionChanged.connect(self._show_index_details)
        indexes_layout.addWidget(self.index_table)
        actions = QHBoxLayout()
        activate_button = QPushButton("Сделать индекс активным")
        activate_button.clicked.connect(self._activate_selected_index)
        actions.addWidget(activate_button)
        actions.addStretch()
        indexes_layout.addLayout(actions)
        self.index_details = QPlainTextEdit()
        self.index_details.setObjectName("index-details")
        self.index_details.setReadOnly(True)
        self.index_details.setMaximumHeight(150)
        indexes_layout.addWidget(QLabel("Обоснование и предупреждения"))
        indexes_layout.addWidget(self.index_details)
        self.tabs.addTab(indexes_page, "Индексы")

        self.curve_table = QTableWidget(0, 6)
        self.curve_table.setObjectName("data-curves")
        self.curve_table.setHorizontalHeaderLabels(
            ["Мнемоника", "Единица", "Описание", "Точек", "Пропусков", "Curve ID"]
        )
        self.tabs.addTab(self.curve_table, "Кривые")

        self.issue_table = QTableWidget(0, 3)
        self.issue_table.setObjectName("import-issues")
        self.issue_table.setHorizontalHeaderLabels(["Уровень", "Код", "Сообщение"])
        self.tabs.addTab(self.issue_table, "Диагностика импорта")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        summary = self.controller.summary()
        headers = "\n".join(f"  {key}: {value}" for key, value in summary.headers) or "  —"
        self.summary_text.setPlainText(
            f"Скважина: {summary.well_name}\n"
            f"Dataset: {summary.dataset_name}\n"
            f"Источник: {summary.source_path or '—'}\n"
            f"Отсчётов: {summary.sample_count}\n"
            f"Кривых: {summary.curve_count}\n"
            f"Индексов: {summary.index_count}\n"
            f"Активный индекс: {summary.active_index_id}\n\n"
            f"Заголовки WELL:\n{headers}"
        )

        indexes = self.controller.indexes()
        self.index_table.setRowCount(len(indexes))
        for row, index in enumerate(indexes):
            index_values = (
                "●" if index.active else "",
                index.mnemonic,
                index.index_type.value,
                index.role.value,
                index.unit or "—",
                str(index.sample_count),
                index.start or "—",
                index.stop or "—",
                f"{index.confidence:.0%}",
            )
            for column, value in enumerate(index_values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, index.index_id)
                self.index_table.setItem(row, column, item)
        self.index_table.resizeColumnsToContents()

        curves = self.controller.curves()
        self.curve_table.setRowCount(len(curves))
        for row, curve in enumerate(curves):
            curve_values = (
                curve.mnemonic,
                curve.unit or "—",
                curve.description or "—",
                str(curve.sample_count),
                str(curve.missing_count),
                curve.curve_id,
            )
            for column, value in enumerate(curve_values):
                self.curve_table.setItem(row, column, QTableWidgetItem(value))
        self.curve_table.resizeColumnsToContents()

        issues = self.controller.import_issues()
        self.issue_table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for column, value in enumerate((issue.severity.value, issue.code, issue.message)):
                self.issue_table.setItem(row, column, QTableWidgetItem(value))
        self.issue_table.resizeColumnsToContents()

    def _selected_index_id(self) -> str | None:
        row = self.index_table.currentRow()
        item = self.index_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, str) else None

    def _show_index_details(self) -> None:
        index_id = self._selected_index_id()
        inspection = next(
            (item for item in self.controller.indexes() if item.index_id == index_id),
            None,
        )
        if inspection is None:
            self.index_details.clear()
            return
        evidence = "\n".join(f"• {item}" for item in inspection.evidence) or "• нет"
        warnings = "\n".join(f"• {item}" for item in inspection.warnings) or "• нет"
        self.index_details.setPlainText(f"Evidence:\n{evidence}\n\nWarnings:\n{warnings}")

    def _activate_selected_index(self) -> None:
        index_id = self._selected_index_id()
        if index_id is None:
            QMessageBox.information(self, "Индексы", "Сначала выберите индекс")
            return
        try:
            self.controller.set_active_index(index_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Индексы", str(exc))
            return
        self._refresh()
