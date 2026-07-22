from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
from geoworkbench.data.interval_statistics_export import statistics_tsv
from geoworkbench.services.localization import AppLanguage, Localizer


class IntervalStatisticsPanel(QWidget):
    export_requested = Signal(str)
    clear_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self._language = language
        self._localizer = Localizer.create(language)
        self._statistics: tuple[CurveIntervalStatistics, ...] = ()
        self._dataset_name = ""
        self._interval_label = "—"

        self.summary = QLabel(self._t("statistics.panel_hint"))
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            "font-weight: 600; padding: 7px; background: #eef2ff; "
            "color: #1e293b; border: 1px solid #c7d2fe; border-radius: 4px;"
        )
        self.table = QTableWidget(0, 7)
        self.table.setObjectName("interval-statistics-panel-table")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()

        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.xlsx_button = QPushButton()
        self.xlsx_button.clicked.connect(lambda: self.export_requested.emit("xlsx"))
        self.csv_button = QPushButton()
        self.csv_button.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self.clear_requested.emit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.xlsx_button)
        buttons.addWidget(self.csv_button)
        buttons.addStretch(1)
        buttons.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)
        self.set_language(language)
        self._set_actions_enabled(False)

    @property
    def statistics(self) -> tuple[CurveIntervalStatistics, ...]:
        return self._statistics

    @property
    def interval_label(self) -> str:
        return self._interval_label

    @property
    def dataset_name(self) -> str:
        return self._dataset_name

    def set_report(
        self,
        *,
        dataset_name: str,
        interval_label: str,
        statistics: tuple[CurveIntervalStatistics, ...],
        display_names: dict[str, str] | None = None,
    ) -> None:
        self._dataset_name = dataset_name
        self._interval_label = interval_label
        self._statistics = statistics
        self.summary.setText(
            self._t(
                "statistics.panel_summary",
                dataset=dataset_name,
                interval=interval_label,
                count=len(statistics),
            )
        )
        self.table.setRowCount(len(statistics))
        labels = display_names or {}
        for row, item in enumerate(statistics):
            readable = labels.get(item.mnemonic, item.mnemonic)
            parameter = readable if readable == item.mnemonic else f"{readable}\n{item.mnemonic}"
            values = (
                parameter,
                item.unit or "—",
                str(item.valid_count),
                f"{item.coverage_percent:.1f}",
                self._format_number(item.minimum),
                self._format_number(item.maximum),
                self._format_number(item.mean),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column >= 2:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, cell)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self._set_actions_enabled(bool(statistics))

    def clear_report(self) -> None:
        self._statistics = ()
        self._dataset_name = ""
        self._interval_label = "—"
        self.table.setRowCount(0)
        self.summary.setText(self._t("statistics.panel_hint"))
        self._set_actions_enabled(False)

    def copy_to_clipboard(self) -> None:
        if not self._statistics:
            return
        QApplication.clipboard().setText(
            statistics_tsv(
                self._statistics,
                interval_label=self._interval_label,
                dataset_name=self._dataset_name,
            )
        )

    def set_language(self, language: AppLanguage) -> None:
        self._language = language
        self._localizer = Localizer.create(language)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("statistics.parameter"),
                self._t("statistics.unit"),
                self._t("statistics.points"),
                self._t("statistics.coverage"),
                self._t("statistics.minimum"),
                self._t("statistics.maximum"),
                self._t("statistics.mean"),
            ]
        )
        self.copy_button.setText(self._t("statistics.copy"))
        self.xlsx_button.setText(self._t("statistics.export_xlsx"))
        self.csv_button.setText(self._t("statistics.export_csv"))
        self.clear_button.setText(self._t("statistics.clear"))
        if self._statistics:
            self.summary.setText(
                self._t(
                    "statistics.panel_summary",
                    dataset=self._dataset_name,
                    interval=self._interval_label,
                    count=len(self._statistics),
                )
            )
        else:
            self.summary.setText(self._t("statistics.panel_hint"))

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.xlsx_button.setEnabled(enabled)
        self.csv_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

    def _t(self, key: str, **values: object) -> str:
        return self._localizer.text(key, **values)

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:.8g}" if np.isfinite(value) else "—"
