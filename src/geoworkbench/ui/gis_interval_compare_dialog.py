"""Explicit, read-only comparison of original GIS observations in one MD window."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_input_inventory import GIS_SAMPLE_FAMILIES
from geoworkbench.services.gis_interval_sample_review import (
    MAX_GIS_INTERVAL_CURVES, GisSourceIntervalBatchItem, review_gis_source_interval_batch,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


class GisIntervalCompareDialog(QDialog):
    def __init__(
        self, dataset: Dataset, parent: QWidget | None = None, *,
        top: str = "", bottom: str = "", language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.localizer = Localizer.create(language)
        self.setObjectName("gis-interval-compare-dialog")
        self.setWindowTitle(self._t("title"))
        layout = QVBoxLayout(self)
        intro = QLabel(self._t("intro", limit=MAX_GIS_INTERVAL_CURVES), self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        bounds = QFormLayout()
        self.top = QLineEdit(top, self)
        self.bottom = QLineEdit(bottom, self)
        for field in (self.top, self.bottom):
            field.setMaxLength(200)
            field.textChanged.connect(self._clear_results)
        bounds.addRow(self._t("top"), self.top)
        bounds.addRow(self._t("bottom"), self.bottom)
        layout.addLayout(bounds)
        candidates = [
            (key, curve) for key, curve in dataset.curves.items()
            if curve.metadata.semantic is not None and curve.metadata.semantic.family in GIS_SAMPLE_FAMILIES
        ]
        self.table = QTableWidget(len(candidates), 9, self)
        self.table.setObjectName("gis-interval-compare-table")
        self.table.setHorizontalHeaderLabels([
            self._t("select"), self._t("curve"), self._t("unit"), self._t("source"),
            self._t("finite"), self._t("missing"), self._t("depths"), self._t("values"), self._t("status"),
        ])
        for row, (key, curve) in enumerate(candidates):
            selected = QTableWidgetItem()
            selected.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            selected.setCheckState(Qt.CheckState.Unchecked)
            selected.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(row, 0, selected)
            self._set_cell(row, 1, f"{key} ({curve.metadata.original_mnemonic})")
            self._set_cell(row, 2, curve.metadata.unit or "?")
            self._set_cell(row, 3, curve.metadata.source_dataset_id or "?")
            for column in range(4, 9):
                self._set_cell(row, column, "—")
        self.table.itemChanged.connect(self._selection_changed)
        header = self.table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.status = QLabel(self)
        self.status.setObjectName("gis-interval-compare-status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.review = QPushButton(self._t("review"), self)
        self.review.setObjectName("gis-interval-compare-review")
        self.review.clicked.connect(self._review)
        layout.addWidget(self.review)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.localizer.text("common.close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(980, 580), minimum=QSize(520, 360))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"gis_compare.{key}", **values)

    def _set_cell(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table.setItem(row, column, item)

    def _selection_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._clear_results()

    def _clear_results(self) -> None:
        if not hasattr(self, "table"):
            return
        for row in range(self.table.rowCount()):
            choice = self.table.item(row, 0)
            key = choice.data(Qt.ItemDataRole.UserRole) if choice is not None else None
            curve = self.dataset.curves.get(key) if isinstance(key, str) else None
            self._set_cell(row, 2, (curve.metadata.unit or "?") if curve is not None else "—")
            self._set_cell(row, 3, (curve.metadata.source_dataset_id or "?") if curve is not None else "—")
            for column in range(4, 9):
                self._set_cell(row, column, "—")
        if hasattr(self, "status"):
            self.status.clear()

    def _review(self) -> None:
        self._clear_results()
        selected: list[str] = []
        for row in range(self.table.rowCount()):
            choice = self.table.item(row, 0)
            if choice is None:
                self.status.setText(self._t("invalid"))
                return
            if choice.checkState() == Qt.CheckState.Checked:
                key = choice.data(Qt.ItemDataRole.UserRole)
                if not isinstance(key, str):
                    self.status.setText(self._t("invalid"))
                    return
                selected.append(key)
        keys = tuple(selected)
        if not 1 <= len(keys) <= MAX_GIS_INTERVAL_CURVES:
            self.status.setText(self._t("selection_required", limit=MAX_GIS_INTERVAL_CURVES))
            return
        self.status.setText(self._t("working"))
        self.status.repaint()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            results = review_gis_source_interval_batch(
                self.dataset, curve_keys=keys,
                top_md_m=float(self.top.text().strip().replace(",", ".")),
                bottom_md_m=float(self.bottom.text().strip().replace(",", ".")),
            )
        except (ValueError, TypeError, OverflowError):
            self.status.setText(self._t("invalid"))
            return
        finally:
            QApplication.restoreOverrideCursor()
        by_key = {item.curve_key: item for item in results}
        for row in range(self.table.rowCount()):
            choice = self.table.item(row, 0)
            key = choice.data(Qt.ItemDataRole.UserRole) if choice is not None else None
            if key in by_key:
                self._show_item(row, by_key[key])
        self.status.setText(self._t("complete"))

    def _show_item(self, row: int, item: GisSourceIntervalBatchItem) -> None:
        if item.source is not None:
            self._set_cell(row, 2, item.source.unit or "?")
            self._set_cell(row, 3, item.source.source_dataset_id or "?")
        if item.review is None:
            reasons = []
            for issue in item.issues:
                if issue == "curve_not_found":
                    reasons.append(self._t("source_missing"))
                else:
                    code = issue.split(":", 1)[-1]
                    reasons.append(self.localizer.catalog.get(f"gis_inventory.issue.{code}", self._t("invalid")))
            self._set_cell(row, 8, "; ".join(reasons))
            return
        review = item.review
        self._set_cell(row, 4, f"{review.finite_count} / {review.sample_count}")
        self._set_cell(row, 5, str(review.missing_count))
        if review.finite_md_bounds is not None:
            first, last = review.finite_md_bounds
            self._set_cell(row, 6, f"{first:.9g}–{last:.9g}")
        if review.finite_value_bounds is not None:
            minimum, maximum = review.finite_value_bounds
            self._set_cell(row, 7, f"{minimum:.9g}–{maximum:.9g}")
        status = "no_samples" if review.sample_count == 0 else (
            "no_values" if review.finite_count == 0 else "reviewed"
        )
        self._set_cell(row, 8, self._t(status))
