"""Read-only inspection of original GIS source quality; no calculations or writes."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_input_inventory import inventory_gis_inputs
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


class GisInputInventoryDialog(QDialog):
    """Present a fresh source snapshot, preserving source depth/value order."""

    def __init__(
        self, dataset: Dataset, parent: QWidget | None = None,
        *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.inventory = inventory_gis_inputs(dataset)
        self.setObjectName("gis-input-inventory-dialog")
        self.setWindowTitle(self._t("title"))
        root = QVBoxLayout(self)
        self.intro = QLabel(self._t("intro"), self)
        self.intro.setWordWrap(True)
        root.addWidget(self.intro)

        depths = np.asarray(dataset.active_index.values)
        if self.inventory.axis_issues or depths.ndim != 1 or not depths.size:
            direction = "unknown"
        elif depths.size == 1:
            direction = "single"
        else:
            direction = "descending" if depths[0] > depths[-1] else "ascending"
        self.axis_label = QLabel(self)
        self.axis_label.setTextFormat(Qt.TextFormat.PlainText)
        self.axis_label.setWordWrap(True)
        self.axis_label.setText(self._t(
            "axis", axis=self.inventory.axis_id,
            unit=self.inventory.axis_unit or "?",
            direction=self._t(f"direction_{direction}"),
            qc=self._issues(self.inventory.axis_issues),
        ))
        root.addWidget(self.axis_label)

        self.table = QTableWidget(len(self.inventory.curves), 6, self)
        self.table.setObjectName("gis-input-inventory-table")
        self.table.setHorizontalHeaderLabels([
            self._t("curve"), self._t("unit"), self._t("samples"),
            self._t("bounds"), self._t("source"), self._t("qc"),
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setSortingEnabled(False)
        for row_index, curve in enumerate(self.inventory.curves):
            bounds = curve.sample_md_bounds
            cells = (
                f"{curve.curve_key} ({curve.original_mnemonic})",
                curve.unit or "?",
                str(curve.finite_sample_count),
                f"{bounds[0]:.9g} – {bounds[1]:.9g}" if bounds else "—",
                curve.source_dataset_id,
                self._issues(curve.issues),
            )
            for column, value in enumerate(cells):
                self.table.setItem(row_index, column, QTableWidgetItem(value))
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.details = QTableWidget(0, 2, self)
        self.details.setObjectName("gis-input-inventory-details")
        self.details.setHorizontalHeaderLabels([self._t("detail_field"), self._t("detail_value")])
        self.details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.details.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.details.verticalHeader().hide()
        self.details.setWordWrap(True)
        hint = QLabel(self._t("details_hint"), self)
        hint.setWordWrap(True)
        root.addWidget(hint)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)
        self.table.itemSelectionChanged.connect(self._show_curve_details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(900, 560), minimum=QSize(500, 340))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"gis_inventory.{key}", **values)

    def _show_curve_details(self) -> None:
        self.details.setRowCount(0)
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1 or not 0 <= rows[0].row() < len(self.inventory.curves):
            return
        # Use the same immutable snapshot as the QC table, not a newer live binding.
        curve = self.inventory.curves[rows[0].row()]
        fields = (
            ("dataset_id", self.inventory.dataset_id),
            ("axis_id", self.inventory.axis_id),
            ("curve_id", curve.curve_id),
            ("curve_key", curve.curve_key),
            ("original_mnemonic", curve.original_mnemonic),
            ("canonical_mnemonic", curve.canonical_mnemonic),
            ("family", curve.family),
            ("source", curve.source_dataset_id),
            ("provenance", curve.provenance),
            ("version", str(curve.version)),
            ("semantic_evidence", "\n".join(curve.semantic_evidence)),
        )
        self.details.setRowCount(len(fields))
        for row, (key, value) in enumerate(fields):
            self.details.setItem(row, 0, QTableWidgetItem(self._t(key)))
            self.details.setItem(row, 1, QTableWidgetItem(value or self._t("not_recorded")))
        self.details.resizeRowsToContents()

    def _issues(self, issues: tuple[str, ...]) -> str:
        if not issues:
            return self._t("ok")
        return "; ".join(
            self.localizer.catalog.get(f"gis_inventory.issue.{issue}", issue)
            for issue in issues
        )
