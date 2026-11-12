"""Explicit preview of selected GIS observations and geology in a gas interval."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QSize, Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_input_inventory import GIS_SAMPLE_FAMILIES
from geoworkbench.services.gis_interval_sample_review import (
    MAX_GIS_INTERVAL_CURVES, GisSourceIntervalBatchItem,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.interpretation_geology_interval_evidence import (
    GasGeologyIntervalEvidence, correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.interpretation_gis_interval_evidence import GasGeologyGisIntervalEvidence
from geoworkbench.services.interpretation_gis_interval_evidence_html import (
    geology_gis_interval_evidence_html,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.gis_interval_compare_dialog import register_gis_interval_worker
from geoworkbench.ui.gis_interval_compare_worker import GisIntervalCompareWorker
from geoworkbench.ui.window_geometry import fit_window_to_screen


_TEXT = {
    AppLanguage.RU: (
        "Газ, геология и ГИС (MD)",
        "Выберите до восьми кривых. Просмотр не подтверждает данные для отчёта.",
        "Показать наблюдения", "Выберите от одной до восьми кривых.",
        "Источник или интервал изменился. Откройте просмотр заново.",
        "Не удалось проверить исходные данные.",
    ),
    AppLanguage.KK: (
        "Газ, геология және ГИС (MD)",
        "Сегізге дейін қисық таңдаңыз. Қарау есеп үшін деректерді растамайды.",
        "Бақылауларды көрсету", "Бірден сегізге дейін қисық таңдаңыз.",
        "Дереккөз немесе аралық өзгерді. Қарауды қайта ашыңыз.",
        "Бастапқы деректерді тексеру мүмкін болмады.",
    ),
    AppLanguage.EN: (
        "Gas, geology and GIS (MD)",
        "Select up to eight curves. Preview does not approve data for a report.",
        "Show observations", "Select one to eight curves.",
        "The source or interval changed. Reopen the preview.",
        "Could not review the source data.",
    ),
}


class GisGeologyEvidenceDialog(QDialog):
    """Read-only preview with explicit curve selection and fresh candidate guard."""

    def __init__(
        self, session: ProjectSession, dataset: Dataset, bounds: tuple[float, float],
        validate_bounds: Callable[[], tuple[float, float] | None],
        parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.dataset = dataset
        self.bounds = bounds
        self.validate_bounds = validate_bounds
        self.language = language
        self.words = _TEXT[language]
        self.localizer = Localizer.create(language)
        self._worker: GisIntervalCompareWorker | None = None
        self._worker_cancel_connection = None
        self._geology: GasGeologyIntervalEvidence | None = None
        self._well = session.current_well
        self._keys: tuple[str, ...] = ()
        self._cancel_requested = False
        self._close_after_worker = False
        self.setObjectName("gis-geology-evidence-dialog")
        self.setWindowTitle(self.words[0])
        layout = QVBoxLayout(self)
        notice = QLabel(f"{bounds[0]:.17g}–{bounds[1]:.17g} m MD · {self.words[1]}", self)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.curves = QListWidget(self)
        self.curves.setObjectName("gis-geology-evidence-curves")
        self.curves.setMaximumHeight(160)
        for key, curve in dataset.curves.items():
            semantic = curve.metadata.semantic
            if semantic is None or semantic.family not in GIS_SAMPLE_FAMILIES:
                continue
            item = QListWidgetItem(f"{key} ({curve.metadata.original_mnemonic})")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.curves.addItem(item)
        layout.addWidget(self.curves)
        self.review = QPushButton(self.words[2], self)
        self.review.setObjectName("gis-geology-evidence-review")
        self.review.clicked.connect(self._review)
        layout.addWidget(self.review)
        self.status = QLabel(self)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setObjectName("gis-geology-evidence-progress")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel = QPushButton(self._t("cancel"), self)
        self.cancel.setObjectName("gis-geology-evidence-cancel")
        self.cancel.clicked.connect(self._cancel_review)
        self.cancel.hide()
        layout.addWidget(self.cancel)
        self.viewer = QTextBrowser(self)
        self.viewer.setObjectName("gis-geology-evidence-content")
        self.viewer.setOpenLinks(False)
        layout.addWidget(self.viewer, 1)
        self.curves.itemChanged.connect(self._clear)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(1100, 720), minimum=QSize(520, 360))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"gis_compare.{key}", **values)

    def _clear(self, _item: QListWidgetItem | None = None) -> None:
        self.viewer.clear()
        self.status.clear()
        if self._worker is not None:
            self._cancel_review()

    def _selected_keys(self) -> tuple[str, ...]:
        return tuple(
            self.curves.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.curves.count())
            if self.curves.item(row).checkState() == Qt.CheckState.Checked
        )

    def _source_current(self) -> bool:
        return (
            self.session.current_dataset is self.dataset
            and self.session.current_well is self._well
            and self.validate_bounds() == self.bounds
        )

    def _read_geology(self) -> GasGeologyIntervalEvidence:
        # Session and well observations are accessed only on the GUI thread.
        return correlate_gas_interval_with_well_geology(
            self.session, top_depth=self.bounds[0], bottom_depth=self.bounds[1],
        )

    def _review(self) -> None:
        if self._worker is not None:
            return
        self._clear()
        keys = self._selected_keys()
        if (
            not 1 <= len(keys) <= MAX_GIS_INTERVAL_CURVES
            or any(not isinstance(key, str) or not key.strip() for key in keys)
            or len(set(keys)) != len(keys)
        ):
            self.status.setText(self.words[3])
            return
        try:
            if not self._source_current():
                self.status.setText(self.words[4])
                return
            self._geology = self._read_geology()
        except (ValueError, RuntimeError, TypeError, OverflowError):
            self.status.setText(self.words[5])
            return
        self._keys = keys
        self._cancel_requested = False
        self._close_after_worker = False
        self._set_running(True)
        self.status.setText(self._t("preparing"))
        worker = GisIntervalCompareWorker(self.dataset, keys, *self.bounds)
        self._worker = worker
        # Use the established lifetime registry and shutdown cancellation.
        worker.progress.connect(self._progress, Qt.ConnectionType.QueuedConnection)
        worker.completed.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._failed, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._worker_finished, Qt.ConnectionType.QueuedConnection)
        register_gis_interval_worker(worker)
        self._worker_cancel_connection = self.destroyed.connect(worker.cancellation_callback())
        worker.start()

    def _set_running(self, running: bool) -> None:
        self.curves.setEnabled(not running)
        self.review.setEnabled(not running)
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
        try:
            geology = self._geology
            if (
                geology is None or not self._source_current()
                or self._selected_keys() != self._keys
                or not isinstance(snapshot, GisIntervalSnapshot)
                or snapshot.source is not self.dataset or snapshot.keys != self._keys
                or snapshot.dataset_id != geology.dataset_id
                or snapshot.active_index_id != geology.depth_axis_id
                or not isinstance(payload, tuple)
                or any(not isinstance(item, GisSourceIntervalBatchItem) for item in payload)
                or tuple(item.curve_key for item in payload) != self._keys
                or self._read_geology() != geology
                # Check numeric arrays again at queued GUI delivery, not only
                # identity or the worker's earlier freshness check.
                or not snapshot.matches(lambda: False)
            ):
                self.status.setText(self.words[4])
                return
            html = geology_gis_interval_evidence_html(
                GasGeologyGisIntervalEvidence(geology, payload), self.language,
            )
        except (ValueError, RuntimeError, TypeError, OverflowError):
            self.status.setText(self.words[4])
            return
        if self._cancel_requested or self._worker is None or self._geology is not geology:
            self.status.setText(self._t("cancelled"))
            return
        self.viewer.setHtml(html)
        self.status.setText(self._t("complete"))

    @Slot(str)
    def _failed(self, reason: str) -> None:
        if self._cancel_requested or reason == "cancelled":
            self.status.setText(self._t("cancelled"))
        else:
            self.status.setText(self.words[4 if reason == "changed" else 5])

    @Slot()
    def _cancel_review(self) -> None:
        if self._worker is not None:
            self._cancel_requested = True
            self.viewer.clear()
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
        self._geology = None
        self._keys = ()
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
