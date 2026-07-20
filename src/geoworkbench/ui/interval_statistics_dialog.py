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
from geoworkbench.services.localization import AppLanguage, Localizer


class IntervalStatisticsDialog(QDialog):
    def __init__(
        self,
        depth_top: float,
        depth_bottom: float,
        statistics: tuple[CurveIntervalStatistics, ...],
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("statistics.interval_title"))
        self.resize(720, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                self._t(
                    "statistics.interval",
                    top=f"{depth_top:g}",
                    bottom=f"{depth_bottom:g}",
                )
            )
        )
        self.table = QTableWidget(len(statistics), 6)
        self.table.setObjectName("interval-statistics-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("statistics.curve"),
                self._t("statistics.unit"),
                self._t("statistics.points"),
                self._t("statistics.minimum"),
                self._t("statistics.maximum"),
                self._t("statistics.mean"),
            ]
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
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
