"""Explicit, read-only comparison of original GIS observations in one MD window."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QCoreApplication, QMetaObject, QObject, QSize, Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QLabel, QLineEdit, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_input_inventory import GIS_SAMPLE_FAMILIES
from geoworkbench.services.gis_interval_sample_review import (
    MAX_GIS_INTERVAL_CURVES, GisSourceIntervalBatchItem,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.gis_interval_compare_worker import GisIntervalCompareWorker
from geoworkbench.ui.window_geometry import fit_window_to_screen


# Keep a worker alive even if an application shutdown destroys the parent dialog.
_LIVE_WORKERS: set[GisIntervalCompareWorker] = set()


def _stop_workers_on_exit() -> None:
    # Join numeric workers before their GUI-owned signal bridges are destroyed.
    workers = tuple(_LIVE_WORKERS)
    for worker in workers:
        worker.request_cancel()
    for worker in workers:
        worker.wait()


class _GisWorkerRegistry(QObject):
    """Own worker cleanup on the GUI thread, not inside the worker thread."""

    @Slot()
    def retire(self) -> None:
        worker = self.sender()
        if not isinstance(worker, GisIntervalCompareWorker) or worker not in _LIVE_WORKERS:
            return
        # Terminal delivery can precede the final return from Thread.run.
        # Join before releasing the GUI-owned signal bridge.
        worker.wait()
        _LIVE_WORKERS.discard(worker)
        worker.deleteLater()


_WORKER_REGISTRY: _GisWorkerRegistry | None = None


def register_gis_interval_worker(worker: GisIntervalCompareWorker) -> None:
    """Keep any GIS interval review worker alive through dialog destruction."""
    global _WORKER_REGISTRY
    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("GIS review requires a Qt application")
    if _WORKER_REGISTRY is None:
        _WORKER_REGISTRY = _GisWorkerRegistry(app)
        app.aboutToQuit.connect(_stop_workers_on_exit)
    worker.setParent(_WORKER_REGISTRY)
    _LIVE_WORKERS.add(worker)
    # Registration follows the dialog's terminal slot. Both now run on the
    # GUI thread. Retire only after the dialog releases its worker reference;
    # deleteLater leaves the signal emitter alive until its timer slot returns.
    worker.finished.connect(_WORKER_REGISTRY.retire, Qt.ConnectionType.DirectConnection)


class GisIntervalCompareDialog(QDialog):
    def __init__(
        self, dataset: Dataset, parent: QWidget | None = None, *,
        top: str = "", bottom: str = "", language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.localizer = Localizer.create(language)
        self._worker: GisIntervalCompareWorker | None = None
        self._worker_cancel_connection: QMetaObject.Connection | None = None
        self._cancel_requested = False
        self._close_after_worker = False
        self._missing_details: dict[int, str] = {}
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
        self.missing_details = QLabel(self._t("missing_select"), self)
        self.missing_details.setObjectName("gis-interval-missing-details")
        self.missing_details.setTextFormat(Qt.TextFormat.PlainText)
        self.missing_details.setWordWrap(True)
        layout.addWidget(self.missing_details)
        self.table.currentCellChanged.connect(self._update_missing_details)
        self.status = QLabel(self)
        self.status.setObjectName("gis-interval-compare-status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setObjectName("gis-interval-compare-progress")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.review = QPushButton(self._t("review"), self)
        self.review.setObjectName("gis-interval-compare-review")
        self.review.clicked.connect(self._review)
        layout.addWidget(self.review)
        self.cancel = QPushButton(self._t("cancel"), self)
        self.cancel.setObjectName("gis-interval-compare-cancel")
        self.cancel.clicked.connect(self._cancel_review)
        self.cancel.hide()
        layout.addWidget(self.cancel)
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
        self._missing_details.clear()
        if hasattr(self, "missing_details"):
            self.missing_details.setText(self._t("missing_select"))
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
        if self._worker is not None:
            return
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
        try:
            top = float(self.top.text().strip().replace(",", "."))
            bottom = float(self.bottom.text().strip().replace(",", "."))
            if not (isfinite(top) and isfinite(bottom) and top < bottom and isfinite(bottom - top)):
                raise ValueError("Invalid interval")
        except (ValueError, TypeError, OverflowError):
            self.status.setText(self._t("invalid"))
            return
        self._cancel_requested = False
        self._close_after_worker = False
        self._set_running(True)
        self.status.setText(self._t("preparing"))
        worker = GisIntervalCompareWorker(self.dataset, keys, top, bottom)
        self._worker = worker
        # The worker's timer emits exclusively on the owning GUI thread.
        # Deliver synchronously so terminal slots finish before retirement;
        # no queued Python payload or stale dialog callback survives completion.
        worker.progress.connect(self._progress, Qt.ConnectionType.DirectConnection)
        worker.completed.connect(self._completed, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(self._failed, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(self._worker_finished, Qt.ConnectionType.DirectConnection)
        register_gis_interval_worker(worker)
        self._worker_cancel_connection = self.destroyed.connect(worker.cancellation_callback())
        worker.start()

    def _set_running(self, running: bool) -> None:
        for widget in (self.top, self.bottom, self.table, self.review):
            widget.setEnabled(not running)
        self.cancel.setVisible(running)
        self.cancel.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)

    @Slot(str, int, int)
    def _progress(self, stage: str, current: int, total: int) -> None:
        if self._cancel_requested:
            return
        if stage == "reviewing" and total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self.status.setText(self._t("progress", current=current, total=total))
        elif stage in {"preparing", "checking", "verifying"}:
            self.progress.setRange(0, 0)
            self.status.setText(self._t(stage))

    @Slot(object, object)
    def _completed(self, snapshot: object, payload: object) -> None:
        if self._cancel_requested:
            self.status.setText(self._t("cancelled"))
            return
        if (
            not isinstance(snapshot, GisIntervalSnapshot) or snapshot.source is not self.dataset
            or not isinstance(payload, tuple)
            or any(not isinstance(item, GisSourceIntervalBatchItem) for item in payload)
            # The worker checked arrays before emitting. Qt may deliver this
            # signal after an in-place edit; identity checks alone miss it.
            or not snapshot.matches(lambda: False)
        ):
            self.status.setText(self._t("changed"))
            return
        results = payload
        by_key = {item.curve_key: item for item in results}
        first_reviewed_row = None
        for row in range(self.table.rowCount()):
            choice = self.table.item(row, 0)
            key = choice.data(Qt.ItemDataRole.UserRole) if choice is not None else None
            if key in by_key:
                self._show_item(row, by_key[key])
                if first_reviewed_row is None and by_key[key].review is not None:
                    first_reviewed_row = row
        if first_reviewed_row is not None:
            self.table.setCurrentCell(first_reviewed_row, 5)
        self._update_missing_details()
        self.status.setText(self._t("complete"))

    def _update_missing_details(self, *_args: int) -> None:
        self.missing_details.setText(
            self._missing_details.get(self.table.currentRow(), self._t("missing_select"))
        )

    @Slot(str)
    def _failed(self, reason: str) -> None:
        self.status.setText(self._t(reason if reason in {"cancelled", "changed"} else "failed"))

    @Slot()
    def _cancel_review(self) -> None:
        if self._worker is not None:
            self._cancel_requested = True
            self.cancel.setEnabled(False)
            self.status.setText(self._t("cancelling"))
            self._worker.request_cancel()

    @Slot()
    def _worker_finished(self) -> None:
        worker = self._worker
        if worker is not None:
            # Do not allow a new review or dialog disposal before native exit.
            worker.wait()
        if self._worker_cancel_connection is not None:
            QObject.disconnect(self._worker_cancel_connection)
            self._worker_cancel_connection = None
        self._worker = None
        self._set_running(False)
        if self._close_after_worker:
            self._close_after_worker = False
            self.reject()

    def reject(self) -> None:
        if self._worker is not None:
            self._close_after_worker = True
            self._cancel_review()
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._worker is not None:
            self._close_after_worker = True
            self._cancel_review()
            event.ignore()
            return
        super().closeEvent(event)

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
        if review.sample_count == 0:
            detail = self._t("missing_no_rows", curve=item.curve_key)
        elif review.missing_count == 0:
            detail = self._t("missing_none", curve=item.curve_key)
        else:
            depths = ", ".join(f"{depth:.9g}" for depth in review.missing_md_preview)
            detail = self._t(
                "missing_preview", curve=item.curve_key, depths=depths,
                shown=len(review.missing_md_preview), total=review.missing_count,
            )
        self._missing_details[row] = detail
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
