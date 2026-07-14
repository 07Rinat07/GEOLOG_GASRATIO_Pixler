from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics


class IntervalStatisticsDialog(QDialog):
    def __init__(
        self,
        depth_top: float,
        depth_bottom: float,
        statistics: tuple[CurveIntervalStatistics, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Статистика глубинного интервала")
        self.resize(720, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Интервал: {depth_top:g}–{depth_bottom:g}"))
        self.table = QTableWidget(len(statistics), 6)
        self.table.setObjectName("interval-statistics-table")
        self.table.setHorizontalHeaderLabels(
            ["Кривая", "Единица", "Точек", "Минимум", "Максимум", "Среднее"]
        )
        for row, item in enumerate(statistics):
            values = (
                item.mnemonic,
                item.unit or "—",
                str(item.valid_count),
                f"{item.minimum:.8g}",
                f"{item.maximum:.8g}",
                f"{item.mean:.8g}",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
