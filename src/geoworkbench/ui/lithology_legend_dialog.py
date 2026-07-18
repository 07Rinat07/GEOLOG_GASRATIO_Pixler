from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.tablet.lithology_legend import LithologyLegendEntry
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.lithotype_catalog_dialog import LithologyPatternPreview


class LithologyLegendDialog(QDialog):
    def __init__(
        self,
        entries: tuple[LithologyLegendEntry, ...],
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("legend.window_title"))
        self.resize(620, 420)
        root = QVBoxLayout(self)
        if not entries:
            empty = QLabel(self._t("legend.empty"))
            empty.setObjectName("lithology-legend-empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(empty)
        else:
            self.table = QTableWidget(len(entries), 4)
            self.table.setObjectName("lithology-legend-table")
            self.table.setHorizontalHeaderLabels(
                [
                    self._t("legend.symbol"),
                    self._t("legend.code"),
                    self._t("legend.rock"),
                    self._t("legend.id"),
                ]
            )
            for row, entry in enumerate(entries):
                preview = LithologyPatternPreview()
                preview.set_pattern(entry.color, entry.pattern_key)
                preview.setMinimumHeight(38)
                self.table.setCellWidget(row, 0, preview)
                self.table.setItem(row, 1, QTableWidgetItem(entry.code))
                self.table.setItem(row, 2, QTableWidgetItem(entry.name))
                self.table.setItem(row, 3, QTableWidgetItem(entry.lithotype_id))
                self.table.setRowHeight(row, 42)
            self.table.resizeColumnsToContents()
            root.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self._t("common.close")
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
