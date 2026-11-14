"""Explicit preview of selected GIS observations and geology in a gas interval."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractListModel, QMetaObject, QModelIndex, QObject, QPersistentModelIndex,
    QSize, Qt, QTimer, Slot,
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListView,
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
from geoworkbench.services.interpretation_gis_evidence_handoff import (
    ConfirmedGisGeologySelection, GisEvidenceTarget,
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


class _CurveSelectionModel(QAbstractListModel):
    """Checkable curve rows stored as Python values, not native-owned items."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, Qt.CheckState]] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        key, label, state = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return label
        if role == Qt.ItemDataRole.UserRole:
            return key
        if role == Qt.ItemDataRole.CheckStateRole:
            return state.value
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable

    def setData(
        self, index: QModelIndex | QPersistentModelIndex, value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if (
            role != Qt.ItemDataRole.CheckStateRole or not index.isValid()
            or not 0 <= index.row() < len(self._rows)
        ):
            return False
        if isinstance(value, Qt.CheckState):
            state = value
        elif isinstance(value, int):
            try:
                state = Qt.CheckState(value)
            except ValueError:
                return False
        else:
            return False
        if state not in (Qt.CheckState.Checked, Qt.CheckState.Unchecked):
            return False
        row = index.row()
        key, label, previous = self._rows[row]
        if state != previous:
            self._rows[row] = (key, label, state)
            changed = self.index(row, 0)
            self.dataChanged.emit(changed, changed, [Qt.ItemDataRole.CheckStateRole])
        return True

    def append_curve(self, key: str, label: str) -> None:
        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append((key, label, Qt.CheckState.Unchecked))
        self.endInsertRows()

    def selected_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _, state in self._rows if state == Qt.CheckState.Checked)


class _CurveSelectionRow:
    """Value-row handle; never creates a C++ list-item wrapper."""

    def __init__(self, model: _CurveSelectionModel, row: int) -> None:
        self._model = model
        self._row = row

    def data(self, role: int) -> object:
        return self._model.data(self._model.index(self._row, 0), role)

    def checkState(self) -> Qt.CheckState:  # noqa: N802 - curve row interface
        value = self.data(Qt.ItemDataRole.CheckStateRole)
        if not isinstance(value, int):
            raise RuntimeError("Curve row no longer exists")
        return Qt.CheckState(value)

    def setCheckState(self, state: Qt.CheckState) -> None:  # noqa: N802
        self._model.setData(self._model.index(self._row, 0), state, Qt.ItemDataRole.CheckStateRole)


class _CurveSelectionView(QListView):
    """Keep the existing checkable-list interface without QListWidgetItem ownership."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # Shiboken crashes releasing QListWidgetItem wrappers both in
        # DeferredDelete and direct QWidget deallocation. Store row data
        # in a normal model so there are no C++ item wrappers to release.
        self._choices = _CurveSelectionModel(self)
        self.setModel(self._choices)

    def count(self) -> int:
        return self._choices.rowCount()

    def item(self, row: int) -> _CurveSelectionRow:
        if not 0 <= row < self.count():
            raise IndexError(row)
        return _CurveSelectionRow(self._choices, row)

    def append_curve(self, key: str, label: str) -> None:
        self._choices.append_curve(key, label)

    def selected_keys(self) -> tuple[str, ...]:
        return self._choices.selected_keys()


class GisGeologyEvidenceDialog(QDialog):
    """Read-only preview with explicit curve selection and fresh candidate guard."""

    def __init__(
        self, session: ProjectSession, dataset: Dataset, bounds: tuple[float, float],
        validate_bounds: Callable[[], tuple[float, float] | None],
        parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU,
        confirm_html: Callable[
            [GasGeologyGisIntervalEvidence, GisIntervalSnapshot],
            ConfirmedGisGeologySelection,
        ] | None = None,
        confirm_word: Callable[
            [GasGeologyGisIntervalEvidence, GisIntervalSnapshot],
            ConfirmedGisGeologySelection,
        ] | None = None,
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
        self._worker_cancel_connection: QMetaObject.Connection | None = None
        self._geology: GasGeologyIntervalEvidence | None = None
        self._well = session.current_well
        self._keys: tuple[str, ...] = ()
        self._confirm_html = confirm_html
        self._confirm_word = confirm_word
        self._reviewed: tuple[GasGeologyGisIntervalEvidence, GisIntervalSnapshot] | None = None
        self.confirmed_html_selection: ConfirmedGisGeologySelection | None = None
        self.confirmed_word_selection: ConfirmedGisGeologySelection | None = None
        self._cancel_requested = False
        self._close_after_worker = False
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._finish_deferred_close)
        self.setObjectName("gis-geology-evidence-dialog")
        self.setWindowTitle(self.words[0])
        layout = QVBoxLayout(self)
        notice = QLabel(f"{bounds[0]:.17g}–{bounds[1]:.17g} m MD · {self.words[1]}", self)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.curves = _CurveSelectionView(self)
        self.curves.setObjectName("gis-geology-evidence-curves")
        self.curves.setMaximumHeight(160)
        for key, curve in dataset.curves.items():
            semantic = curve.metadata.semantic
            if semantic is None or semantic.family not in GIS_SAMPLE_FAMILIES:
                continue
            self.curves.append_curve(key, f"{key} ({curve.metadata.original_mnemonic})")
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
        self.curves.model().dataChanged.connect(self._clear)
        captions = {
            AppLanguage.RU: "Подтвердить наблюдения для HTML",
            AppLanguage.KK: "Бақылауларды HTML үшін растау",
            AppLanguage.EN: "Confirm observations for HTML",
        }
        self.confirm_html_button = QPushButton(captions[language], self)
        self.confirm_html_button.setObjectName("gis-geology-confirm-html")
        self.confirm_html_button.setEnabled(False)
        self.confirm_html_button.setVisible(confirm_html is not None)
        self.confirm_html_button.clicked.connect(self._confirm_reviewed_html)
        layout.addWidget(self.confirm_html_button)
        word_captions = {
            AppLanguage.RU: "Подтвердить наблюдения для Word",
            AppLanguage.KK: "Бақылауларды Word үшін растау",
            AppLanguage.EN: "Confirm observations for Word",
        }
        self.confirm_word_button = QPushButton(word_captions[language], self)
        self.confirm_word_button.setObjectName("gis-geology-confirm-word")
        self.confirm_word_button.setEnabled(False)
        self.confirm_word_button.setVisible(confirm_word is not None)
        self.confirm_word_button.clicked.connect(self._confirm_reviewed_word)
        layout.addWidget(self.confirm_word_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close")
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(1100, 720), minimum=QSize(520, 360))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"gis_compare.{key}", **values)

    def _clear(self) -> None:
        self._reviewed = None
        self.confirmed_html_selection = None
        self.confirmed_word_selection = None
        self.confirm_html_button.setEnabled(False)
        self.confirm_word_button.setEnabled(False)
        self.viewer.clear()
        self.status.clear()
        if self._worker is not None:
            self._cancel_review()

    def _selected_keys(self) -> tuple[str, ...]:
        return self.curves.selected_keys()

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
        if self._worker is not None or self._close_after_worker:
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
            evidence = GasGeologyGisIntervalEvidence(geology, payload)
            html = geology_gis_interval_evidence_html(evidence, self.language)
        except (ValueError, RuntimeError, TypeError, OverflowError):
            self.status.setText(self.words[4])
            return
        if self._cancel_requested or self._worker is None or self._geology is not geology:
            self.status.setText(self._t("cancelled"))
            return
        self._reviewed = (evidence, snapshot)
        self.viewer.setHtml(html)
        self.status.setText(self._t("complete"))

    def _confirm_reviewed_html(self) -> None:
        self._confirm_reviewed("html")

    def _confirm_reviewed_word(self) -> None:
        self._confirm_reviewed("word")

    def _confirm_reviewed(self, target: GisEvidenceTarget) -> None:
        # Keep the original reviewed arrays and exact output target. Never
        # promote an HTML approval into a Word approval (or vice versa).
        confirm = self._confirm_html if target == "html" else self._confirm_word
        if (
            self._worker is not None or self._reviewed is None
            or confirm is None or self._close_after_worker or self._cancel_requested
        ):
            return
        evidence, snapshot = self._reviewed
        self.confirmed_html_selection = None
        self.confirmed_word_selection = None
        try:
            if not self._source_current() or self._selected_keys() != snapshot.keys:
                raise ValueError("Changed preview selection")
            selection = confirm(evidence, snapshot)
            if selection.target != target:
                raise ValueError("Confirmed GIS evidence has a different output target")
            if target == "html":
                self.confirmed_html_selection = selection
            else:
                self.confirmed_word_selection = selection
        except (ValueError, RuntimeError, TypeError, OverflowError):
            self._clear()
            self.status.setText(self.words[4])
            return
        self.accept()

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
            self._reviewed = None
            self.confirmed_html_selection = None
            self.confirmed_word_selection = None
            self.confirm_html_button.setEnabled(False)
            self.confirm_word_button.setEnabled(False)
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
        can_confirm = (
            self._reviewed is not None
            and not self._cancel_requested and not self._close_after_worker
            and all(item.review is not None and not item.issues for item in self._reviewed[0].gis)
            and any(item.review is not None and item.review.finite_count > 0
                    for item in self._reviewed[0].gis)
        )
        self.confirm_html_button.setEnabled(self._confirm_html is not None and can_confirm)
        self.confirm_word_button.setEnabled(self._confirm_word is not None and can_confirm)
        if self._close_after_worker:
            # The worker is still emitting finished: the registry and other
            # direct observers have not returned yet. Closing a modal dialog
            # here can re-enter its owner and destroy Qt receivers mid-signal.
            # A dialog-owned timer runs after this terminal delivery.
            self._close_timer.start(0)

    @Slot()
    def _finish_deferred_close(self) -> None:
        if self._worker is None and self._close_after_worker:
            self._close_after_worker = False
            super().reject()

    def reject(self) -> None:
        if self._worker is not None:
            self._close_after_worker = True
            self._cancel_review()
            return
        if self._close_after_worker:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._worker is not None:
            self._close_after_worker = True
            self._cancel_review()
            event.ignore()
            return
        if self._close_after_worker:
            event.ignore()
            return
        super().closeEvent(event)
