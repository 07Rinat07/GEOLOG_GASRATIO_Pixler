from __future__ import annotations

from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.paradox.analysis import analyze_table, convert_time_values
from geoworkbench.importers.paradox.channel_dictionary import (
    ChannelDefinition,
    GeoScapeChannelDictionary,
)
from geoworkbench.importers.paradox.importer import (
    GEOSCAPE_STANDARD_DEPTH_STEP_M,
    default_mappings,
    import_paradox,
)
from geoworkbench.importers.paradox.models import (
    ChannelMapping,
    DatasetClassification,
    DuplicateDepthPolicy,
    ParadoxImportPlan,
    ParadoxImportResult,
    ParadoxTable,
    QualitySummary,
)
from geoworkbench.importers.paradox.profiles import (
    ImportProfile,
    load_profile,
    save_profile,
    schema_signature,
)
from geoworkbench.importers.paradox.reader import read_paradox
from geoworkbench.importers.paradox.progress import paradox_progress_state
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.time_display import format_datetime_value, format_elapsed_time


class _ReaderWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)

    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source
        self._cancel_event = Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        try:
            table = read_paradox(
                self.source,
                progress=lambda phase, current, total: self.progress.emit(phase, current, total),
                cancelled=lambda: self.cancel_requested,
            )
            if self.cancel_requested:
                raise RuntimeError("Импорт Paradox отменён пользователем")
            self.progress.emit("analysis", 0, 1)
            quality = analyze_table(table)
            self.progress.emit("analysis", 1, 1)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit((table, quality))


class _ImportWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)

    def __init__(
        self,
        source: Path,
        table: ParadoxTable,
        quality: QualitySummary,
        plan: ParadoxImportPlan,
    ) -> None:
        super().__init__()
        self.source = source
        self.table = table
        self.quality = quality
        self.plan = plan
        self._cancel_event = Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        try:
            result = import_paradox(
                self.source,
                self.plan,
                table=self.table,
                quality=self.quality,
                progress=lambda phase, current, total: self.progress.emit(phase, current, total),
                cancelled=lambda: self.cancel_requested,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class ParadoxImportDialog(QDialog):
    def __init__(
        self,
        source: Path,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        configuration_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.language = language
        self.localizer = Localizer.create(language)
        self.configuration_only = bool(configuration_only)
        self.selected_plan: ParadoxImportPlan | None = None
        self.table: ParadoxTable | None = None
        self.quality: QualitySummary | None = None
        self.import_result: ParadoxImportResult | None = None
        self.requested_action = "open"
        self._profile_name: str | None = None
        self._thread: QThread | None = None
        self._worker: _ReaderWorker | None = None
        self._import_worker: _ImportWorker | None = None
        self._pending_action = "open"
        self._cancel_pending = False
        self._busy = False
        self._phase = "header"
        self._started_at = monotonic()
        self._last_progress_at = self._started_at
        self._last_progress_text = ""
        self._population_stage = "idle"
        self._population_row = 0
        self._population_completed = 0
        self._population_total = 1
        self._population_mappings: tuple[ChannelMapping, ...] = ()
        self._population_warning_fields: set[str] = set()
        self._preview_row_indexes: list[int] = []
        self._preview_field_names: list[str] = []
        self._preview_converted_text: list[str] | None = None
        self.setWindowTitle(self._t("paradox.title"))
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setSizeGripEnabled(True)
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is None:
            self.resize(1100, 720)
        else:
            self.resize(
                max(820, min(1180, int(available.width() * 0.94))),
                max(580, min(760, int(available.height() * 0.90))),
            )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        status_box = QGroupBox(self._t("paradox.progress_group"))
        status_layout = QVBoxLayout(status_box)
        status_header = QHBoxLayout()
        self.status = QLabel(self._t("paradox.reading"))
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-weight:600;")
        status_header.addWidget(self.status, 1)
        self.phase_label = QLabel(self._t("paradox.phase_counter", current=1, total=6))
        self.phase_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_header.addWidget(self.phase_label)
        status_layout.addLayout(status_header)
        self.file_progress_label = QLabel(
            self._t("paradox.processing_file", file=self.source.name)
        )
        self.file_progress_label.setWordWrap(True)
        status_layout.addWidget(self.file_progress_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        status_layout.addWidget(self.progress)
        detail_row = QHBoxLayout()
        self.progress_detail = QLabel(self._t("paradox.progress_waiting"))
        self.progress_detail.setWordWrap(True)
        detail_row.addWidget(self.progress_detail, 1)
        self.elapsed_label = QLabel(self._t("paradox.elapsed", seconds="0.0"))
        self.elapsed_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        detail_row.addWidget(self.elapsed_label)
        status_layout.addLayout(detail_row)
        self.progress_hint = QLabel(self._t("paradox.progress_hint"))
        self.progress_hint.setWordWrap(True)
        self.progress_hint.setStyleSheet("color:#475569;")
        status_layout.addWidget(self.progress_hint)
        root.addWidget(status_box)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_file_tab()
        self._build_channels_tab()
        self._build_preview_tab()
        self._build_issues_tab()

        secondary_actions = QHBoxLayout()
        self.load_profile_button = QPushButton(self._t("paradox.load_profile"))
        self.load_profile_button.clicked.connect(self._load_profile)
        self.load_profile_button.setEnabled(False)
        self.load_profile_button.setToolTip(self._t("paradox.load_profile_hint"))
        secondary_actions.addWidget(self.load_profile_button)
        self.profile_button = QPushButton(self._t("paradox.save_profile"))
        self.profile_button.clicked.connect(self._save_profile)
        self.profile_button.setEnabled(False)
        self.profile_button.setToolTip(self._t("paradox.save_profile_hint"))
        secondary_actions.addWidget(self.profile_button)
        self.load_dictionary_button = QPushButton(self._t("paradox.load_dictionary"))
        self.load_dictionary_button.clicked.connect(self._load_dictionary)
        self.load_dictionary_button.setEnabled(False)
        self.load_dictionary_button.setToolTip(self._t("paradox.load_dictionary_hint"))
        secondary_actions.addWidget(self.load_dictionary_button)
        self.save_dictionary_button = QPushButton(self._t("paradox.save_dictionary"))
        self.save_dictionary_button.clicked.connect(self._save_dictionary)
        self.save_dictionary_button.setEnabled(False)
        self.save_dictionary_button.setToolTip(self._t("paradox.save_dictionary_hint"))
        secondary_actions.addWidget(self.save_dictionary_button)
        secondary_actions.addStretch(1)
        root.addLayout(secondary_actions)

        primary_actions = QHBoxLayout()
        self.cancel_button = QPushButton(self._t("common.cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setToolTip(self._t("paradox.cancel_hint"))
        primary_actions.addWidget(self.cancel_button)
        primary_actions.addStretch(1)
        self.save_las_button = QPushButton(self._t("paradox.save_las"))
        self.save_las_button.clicked.connect(lambda: self._finish("save_las"))
        self.save_las_button.setEnabled(False)
        self.save_las_button.setToolTip(self._t("paradox.save_las_hint"))
        primary_actions.addWidget(self.save_las_button)
        self.open_button = QPushButton(self._t("paradox.open_editor"))
        self.open_button.clicked.connect(lambda: self._finish("open"))
        self.open_button.setEnabled(False)
        self.open_button.setDefault(True)
        self.open_button.setToolTip(self._t("paradox.open_editor_hint"))
        if self.configuration_only:
            self.save_las_button.hide()
            self.open_button.setText(self._t("paradox.apply_batch_settings"))
            self.open_button.setToolTip(self._t("paradox.apply_batch_settings_hint"))
        primary_actions.addWidget(self.open_button)
        root.addLayout(primary_actions)

        self._population_timer = QTimer(self)
        self._population_timer.setSingleShot(True)
        self._population_timer.timeout.connect(self._populate_next_chunk)

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(250)
        self._heartbeat.timeout.connect(self._update_elapsed)
        self._heartbeat.start()
        self._set_busy(True)
        self._start_reader()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        enabled = not self._busy and self.table is not None
        for button in (
            self.open_button,
            self.save_las_button,
            self.profile_button,
            self.load_profile_button,
            self.load_dictionary_button,
            self.save_dictionary_button,
        ):
            button.setEnabled(enabled)
        self.tabs.setEnabled(not self._busy)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText(
            self._t("common.cancel") if self._busy else self._t("common.close")
        )

    @Slot()
    def _update_elapsed(self) -> None:
        elapsed = max(0.0, monotonic() - self._started_at)
        self.elapsed_label.setText(
            self._t("paradox.elapsed", seconds=f"{elapsed:.1f}")
        )
        if self._busy and monotonic() - self._last_progress_at > 4.0:
            self.progress_hint.setText(
                self._t("paradox.progress_slow_hint")
            )
        elif self._busy:
            self.progress_hint.setText(self._t("paradox.progress_hint"))

    def _set_progress_state(
        self,
        *,
        phase: str,
        current: int,
        total: int,
        overall: float,
        phase_number: int,
    ) -> None:
        labels = {
            "header": self._t("paradox.phase_header"),
            "schema": self._t("paradox.phase_schema"),
            "records": self._t("paradox.phase_records"),
            "analysis": self._t("paradox.phase_analysis"),
            "preview": self._t("paradox.phase_preview"),
            "create": self._t("paradox.phase_create"),
        }
        self._phase = phase
        self.status.setText(labels.get(phase, phase))
        self.phase_label.setText(
            self._t("paradox.phase_counter", current=phase_number, total=6)
        )
        value = max(0, min(1000, int(round(overall * 1000.0))))
        self.progress.setRange(0, 1000)
        self.progress.setValue(value)
        if total > 0:
            detail = self._t(
                "paradox.progress_count", current=current, total=total
            )
        else:
            detail = self._t("paradox.progress_working")
        self._last_progress_text = detail
        self.progress_detail.setText(detail)
        self._last_progress_at = monotonic()

    def _build_file_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        info_group = QGroupBox(self._t("paradox.file_info"))
        info = QFormLayout(info_group)
        self.info_path = QLabel(str(self.source))
        self.info_path.setWordWrap(True)
        self.info_format = QLabel("—")
        self.info_version = QLabel("—")
        self.info_size = QLabel("—")
        self.info_records = QLabel("—")
        self.info_fields = QLabel("—")
        self.info_bundle = QLabel("—")
        self.info_bundle.setWordWrap(True)
        info.addRow(self._t("paradox.path"), self.info_path)
        info.addRow(self._t("paradox.format"), self.info_format)
        info.addRow(self._t("paradox.version"), self.info_version)
        info.addRow(self._t("paradox.size"), self.info_size)
        info.addRow(self._t("paradox.records"), self.info_records)
        info.addRow(self._t("paradox.fields"), self.info_fields)
        info.addRow(self._t("paradox.bundle"), self.info_bundle)
        layout.addWidget(info_group)

        options_group = QGroupBox(self._t("paradox.data_type"))
        options = QFormLayout(options_group)
        self.classification = QComboBox()
        for kind, key in (
            (DatasetClassification.DEPTH, "paradox.type_depth"),
            (DatasetClassification.TIME, "paradox.type_time"),
            (DatasetClassification.TIME_WITH_DEPTH, "paradox.type_time_depth"),
            (DatasetClassification.MIXED, "paradox.type_mixed"),
            (DatasetClassification.UNDEFINED, "paradox.type_undefined"),
        ):
            self.classification.addItem(self._t(key), kind)
        self.depth_field = QComboBox()
        self.time_field = QComboBox()
        self.active_role = QComboBox()
        self.active_role.addItem(self._t("paradox.active_auto"), "auto")
        self.active_role.addItem(self._t("paradox.active_depth"), "depth")
        self.active_role.addItem(self._t("paradox.active_time"), "time")
        self.sort_index = QCheckBox(self._t("paradox.sort_index"))
        self.null_value = QDoubleSpinBox()
        self.null_value.setRange(-1_000_000_000_000.0, 1_000_000_000_000.0)
        self.null_value.setDecimals(6)
        self.null_value.setValue(-999.25)
        self.duplicate_policy = QComboBox()
        for policy, key in (
            (DuplicateDepthPolicy.KEEP_ALL, "paradox.duplicates_keep"),
            (DuplicateDepthPolicy.FIRST, "paradox.duplicates_first"),
            (DuplicateDepthPolicy.LAST, "paradox.duplicates_last"),
            (DuplicateDepthPolicy.MEAN, "paradox.duplicates_mean"),
            (DuplicateDepthPolicy.MEDIAN, "paradox.duplicates_median"),
        ):
            self.duplicate_policy.addItem(self._t(key), policy)
        self.drop_empty_channels = QCheckBox(self._t("paradox.drop_empty_channels"))
        self.actual_depth_step = QLabel("—")
        self.standard_depth_step = QLabel(f"{GEOSCAPE_STANDARD_DEPTH_STEP_M:g} m")
        self.standard_depth_step.setToolTip(self._t("paradox.standard_depth_step_hint"))
        options.addRow(self._t("paradox.detected_type"), self.classification)
        options.addRow(self._t("paradox.depth_channel"), self.depth_field)
        options.addRow(self._t("paradox.time_channel"), self.time_field)
        options.addRow(self._t("paradox.active_index"), self.active_role)
        options.addRow(self._t("paradox.actual_depth_step"), self.actual_depth_step)
        options.addRow(self._t("paradox.standard_depth_step"), self.standard_depth_step)
        options.addRow(self._t("paradox.null_value"), self.null_value)
        options.addRow(self._t("paradox.duplicate_depth"), self.duplicate_policy)
        options.addRow(self.sort_index)
        options.addRow(self.drop_empty_channels)
        self.depth_field.currentIndexChanged.connect(self._populate_preview)
        self.time_field.currentIndexChanged.connect(self._populate_preview)
        layout.addWidget(options_group)
        layout.addStretch(1)
        self.tabs.addTab(page, self._t("paradox.file_info"))

    def _build_channels_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.channels = QTableWidget(0, 10)
        self.channels.setHorizontalHeaderLabels(
            [
                self._t("paradox.import_column"),
                self._t("paradox.source_name"),
                self._t("paradox.mnemonic"),
                self._t("paradox.name"),
                self._t("paradox.unit"),
                self._t("paradox.field_type"),
                self._t("paradox.filled"),
                self._t("paradox.minimum"),
                self._t("paradox.maximum"),
                self._t("paradox.warnings"),
            ]
        )
        self.channels.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        channel_header = self.channels.horizontalHeader()
        channel_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        channel_header.setDefaultSectionSize(108)
        channel_header.setMinimumSectionSize(54)
        channel_header.resizeSection(0, 74)
        channel_header.resizeSection(1, 92)
        channel_header.resizeSection(2, 92)
        channel_header.resizeSection(3, 210)
        channel_header.resizeSection(4, 72)
        channel_header.resizeSection(5, 84)
        channel_header.setStretchLastSection(True)
        layout.addWidget(self.channels)
        self.tabs.addTab(page, self._t("paradox.channels"))

    def _build_preview_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.preview_summary = QLabel()
        self.preview_summary.setWordWrap(True)
        layout.addWidget(self.preview_summary)
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview)
        self.tabs.addTab(page, self._t("paradox.preview"))

    def _build_issues_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.issues = QTableWidget(0, 5)
        self.issues.setHorizontalHeaderLabels(
            [
                self._t("paradox.level"),
                self._t("paradox.issue"),
                self._t("paradox.record"),
                self._t("paradox.source_name"),
                self._t("paradox.offset"),
            ]
        )
        self.issues.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.issues)
        self.tabs.addTab(page, self._t("paradox.quality"))

    def _start_reader(self) -> None:
        thread = QThread(self)
        worker = _ReaderWorker(self.source)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda current=thread: self._clear_thread_reference(current, "reader"))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _clear_thread_reference(self, thread: QThread, kind: str) -> None:
        if self._thread is thread:
            self._thread = None
        if kind == "reader":
            self._worker = None
        elif kind == "import":
            self._import_worker = None

    @Slot(str, int, int)
    def _on_progress(self, phase: str, current: int, total: int) -> None:
        # One stable overall scale is easier to understand than a progress bar
        # that repeatedly jumps back to zero for every internal phase.
        state = paradox_progress_state(phase, current, total)
        self._set_progress_state(
            phase=state.phase,
            current=state.current,
            total=state.total,
            overall=state.overall_ratio,
            phase_number=state.phase_number,
        )

    @Slot(object)
    def _on_loaded(self, payload: object) -> None:
        if self._cancel_pending:
            return
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._on_failed(self._t("paradox.invalid_worker_result"))
            return
        table, quality = payload
        if not isinstance(table, ParadoxTable):
            self._on_failed(self._t("paradox.invalid_worker_result"))
            return
        self.table = table
        self.quality = quality
        self._set_progress_state(
            phase="preview", current=0, total=1, overall=0.86, phase_number=5
        )
        self.progress_detail.setText(self._t("paradox.preparing_tables"))
        self._begin_population()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        if self._cancel_pending:
            self.status.setText(self._t("paradox.cancelled"))
            return
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.status.setText(self._t("paradox.failed"))
        self.progress_detail.setText(message)
        self.progress_hint.setText(self._t("paradox.failed_hint"))
        self._set_busy(False)
        QMessageBox.critical(self, self._t("paradox.title"), message)

    def _begin_population(self) -> None:
        """Prepare the preview in short GUI-thread chunks.

        QTableWidget must be modified on the GUI thread, but filling thousands
        of cells in one slot makes Windows mark the whole application as not
        responding.  The timer-driven population below yields to the Qt event
        loop every few milliseconds, so repaint, close and cancellation stay
        available throughout preview construction.
        """

        assert self.table is not None and self.quality is not None
        table = self.table
        quality = self.quality
        self.channels.setUpdatesEnabled(False)
        self.preview.setUpdatesEnabled(False)
        self.issues.setUpdatesEnabled(False)
        self.channels.setSortingEnabled(False)

        self.info_format.setText("Borland Paradox DB")
        self.info_version.setText(table.header.version_label)
        self.info_size.setText(f"{table.source.stat().st_size:,} B")
        self.info_records.setText(str(table.rows_read))
        self.info_fields.setText(str(len(table.fields)))
        bundle_lines = [str(item) for item in table.bundle.files]
        if len(bundle_lines) == 1:
            bundle_lines.append(self._t("paradox.companions_missing"))
        self.info_bundle.setText("\n".join(bundle_lines))
        index = self.classification.findData(quality.classification)
        if index >= 0:
            self.classification.setCurrentIndex(index)

        self.depth_field.blockSignals(True)
        self.time_field.blockSignals(True)
        try:
            self._populate_index_combo(self.depth_field, quality.depth_candidates, "depth")
            self._populate_index_combo(self.time_field, quality.time_candidates, "time")
        finally:
            self.depth_field.blockSignals(False)
            self.time_field.blockSignals(False)
        self.active_role.setCurrentIndex(1 if quality.depth_candidates else 2)

        self._population_mappings = default_mappings(
            table, language=self.localizer.language.value
        )
        self._population_warning_fields = {
            issue.field_name for issue in quality.issues if issue.field_name
        }
        self.channels.setRowCount(len(table.fields))

        (
            self._preview_row_indexes,
            self._preview_field_names,
            self._preview_converted_text,
        ) = self._preview_data()
        extra = 1 if self._preview_converted_text is not None else 0
        self.preview.setColumnCount(len(self._preview_field_names) + extra)
        headers = list(self._preview_field_names)
        if self._preview_converted_text is not None:
            headers.append(self._t("paradox.converted_time"))
        self.preview.setHorizontalHeaderLabels(headers)
        self.preview.setRowCount(len(self._preview_row_indexes))

        self.issues.setRowCount(len(quality.issues))
        self._population_stage = "channels"
        self._population_row = 0
        self._population_completed = 0
        self._population_total = max(
            1,
            len(table.fields)
            + len(self._preview_row_indexes)
            + len(quality.issues),
        )
        self._population_timer.start(0)

    @Slot()
    def _populate_next_chunk(self) -> None:
        if self._cancel_pending:
            self._restore_population_updates()
            if self._thread is None or not self._thread.isRunning():
                self._reject_after_worker()
            return
        if self.table is None or self.quality is None:
            return

        deadline = monotonic() + 0.012
        try:
            while monotonic() < deadline:
                if self._population_stage == "channels":
                    if self._population_row >= len(self.table.fields):
                        self._population_stage = "preview"
                        self._population_row = 0
                        continue
                    self._populate_channel_row(self._population_row)
                elif self._population_stage == "preview":
                    if self._population_row >= len(self._preview_row_indexes):
                        self._population_stage = "issues"
                        self._population_row = 0
                        continue
                    self._populate_preview_row(self._population_row)
                elif self._population_stage == "issues":
                    if self._population_row >= len(self.quality.issues):
                        self._complete_population()
                        return
                    self._populate_issue_row(self._population_row)
                else:
                    self._complete_population()
                    return
                self._population_row += 1
                self._population_completed += 1
        except Exception as exc:
            self._restore_population_updates()
            self._on_failed(str(exc))
            return

        ratio = min(1.0, self._population_completed / self._population_total)
        self._set_progress_state(
            phase="preview",
            current=self._population_completed,
            total=self._population_total,
            overall=0.86 + 0.08 * ratio,
            phase_number=5,
        )
        self.progress_detail.setText(
            self._t(
                "paradox.progress_count",
                current=self._population_completed,
                total=self._population_total,
            )
        )
        self._population_timer.start(0)

    def _populate_channel_row(self, row: int) -> None:
        assert self.table is not None
        field = self.table.fields[row]
        mapping = self._population_mappings[row]
        check = QTableWidgetItem()
        check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        check.setCheckState(
            Qt.CheckState.Checked if mapping.import_enabled else Qt.CheckState.Unchecked
        )
        self.channels.setItem(row, 0, check)
        self.channels.setItem(row, 1, QTableWidgetItem(field.name))
        self.channels.setItem(row, 2, QTableWidgetItem(mapping.mnemonic))
        self.channels.setItem(row, 3, QTableWidgetItem(mapping.description))
        self.channels.setItem(row, 4, QTableWidgetItem(mapping.unit))
        self.channels.setItem(row, 5, QTableWidgetItem(field.type_name))
        column = self.table.columns[field.name]
        self.channels.setItem(
            row, 6, QTableWidgetItem(f"{column.filled_count}/{self.table.rows_read}")
        )
        self.channels.setItem(row, 7, QTableWidgetItem(_display(column.minimum)))
        self.channels.setItem(row, 8, QTableWidgetItem(_display(column.maximum)))
        self.channels.setItem(
            row,
            9,
            QTableWidgetItem(
                self._t("paradox.has_warnings")
                if field.name in self._population_warning_fields
                else ""
            ),
        )

    def _preview_data(self) -> tuple[list[int], list[str], list[str] | None]:
        assert self.table is not None
        total = self.table.rows_read
        row_indexes = list(range(min(20, total)))
        tail_start = max(len(row_indexes), total - 20)
        row_indexes.extend(range(tail_start, total))
        field_names = [field.name for field in self.table.fields]
        time_name = self.time_field.currentData()
        converted_text: list[str] | None = None
        if time_name in self.table.columns and row_indexes:
            raw = np.asarray(self.table.columns[str(time_name)].values, dtype=np.float64)
            sample = raw[np.asarray(row_indexes, dtype=np.int64)]
            elapsed, datetimes, _representation = convert_time_values(sample)
            converted_text = []
            for position, elapsed_value in enumerate(elapsed):
                if datetimes is not None and not np.isnat(datetimes[position]):
                    converted_text.append(format_datetime_value(datetimes[position]))
                else:
                    converted_text.append(format_elapsed_time(float(elapsed_value), "s"))
        return row_indexes, field_names, converted_text

    def _populate_preview_row(self, preview_row: int) -> None:
        assert self.table is not None
        source_row = self._preview_row_indexes[preview_row]
        for column, field_name in enumerate(self._preview_field_names):
            value = self.table.columns[field_name].values[source_row]
            self.preview.setItem(preview_row, column, QTableWidgetItem(_display(value)))
        if self._preview_converted_text is not None:
            self.preview.setItem(
                preview_row,
                len(self._preview_field_names),
                QTableWidgetItem(self._preview_converted_text[preview_row]),
            )

    def _populate_issue_row(self, row: int) -> None:
        assert self.quality is not None
        issue = self.quality.issues[row]
        for column, value in enumerate(
            (
                self._t(f"paradox.severity.{issue.severity.value}"),
                self._localized_issue_message(issue),
                issue.record_number,
                issue.field_name,
                issue.file_offset,
            )
        ):
            self.issues.setItem(row, column, QTableWidgetItem(_display(value)))

    def _restore_population_updates(self) -> None:
        self.channels.setUpdatesEnabled(True)
        self.preview.setUpdatesEnabled(True)
        self.issues.setUpdatesEnabled(True)
        self.channels.viewport().update()
        self.preview.viewport().update()
        self.issues.viewport().update()

    def _complete_population(self) -> None:
        self._population_stage = "done"
        self._restore_population_updates()
        self._update_depth_step_labels()
        self._apply_index_sort_recommendation()
        depth_name = self.depth_field.currentData() or self._t("paradox.not_selected")
        selected_time = self.time_field.currentData() or self._t("paradox.not_selected")
        self.preview_summary.setText(
            self._t(
                "paradox.preview_summary",
                depth=depth_name,
                time=selected_time,
                rows=len(self._preview_row_indexes),
            )
        )
        header = self.preview.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(92)
        header.setMinimumSectionSize(54)
        header.setStretchLastSection(False)
        self._set_progress_state(
            phase="preview",
            current=self._population_total,
            total=self._population_total,
            overall=0.94,
            phase_number=5,
        )
        self.status.setText(self._t("paradox.ready"))
        self.progress_detail.setText(self._t("paradox.ready_hint"))
        self.progress_hint.setText(self._t("paradox.ready_instructions"))
        self._set_busy(False)

    def _apply_index_sort_recommendation(self) -> None:
        if self.table is None:
            return
        role = str(self.active_role.currentData() or "auto")
        field_name = (
            self.time_field.currentData()
            if role == "time"
            else self.depth_field.currentData()
        )
        if field_name not in self.table.columns:
            return
        try:
            values = np.asarray(
                self.table.columns[str(field_name)].values, dtype=np.float64
            )
        except (TypeError, ValueError):
            return
        analysis = analyze_depth_axis(values)
        if analysis.direction is DepthDirection.MIXED:
            self.sort_index.setChecked(True)
            self.sort_index.setToolTip(self._t("paradox.sort_index_recommended"))

    def _localized_issue_message(self, issue) -> str:
        key = f"paradox.issue_code.{issue.code.replace('-', '_')}"
        if key not in self.localizer.catalog:
            return issue.message
        values = {
            "field": issue.field_name or "",
            "record": issue.record_number or "",
            "offset": issue.file_offset or "",
            "type": issue.field_type or "",
            **issue.details,
        }
        try:
            return self._t(key, **values)
        except (KeyError, ValueError):
            return issue.message

    @Slot()
    def _populate_preview(self) -> None:
        if self.table is None or self._busy:
            return
        self._update_depth_step_labels()
        row_indexes, field_names, converted_text = self._preview_data()
        self.preview.setUpdatesEnabled(False)
        try:
            extra = 1 if converted_text is not None else 0
            self.preview.clearContents()
            self.preview.setColumnCount(len(field_names) + extra)
            headers = list(field_names)
            if converted_text is not None:
                headers.append(self._t("paradox.converted_time"))
            self.preview.setHorizontalHeaderLabels(headers)
            self.preview.setRowCount(len(row_indexes))
            self._preview_row_indexes = row_indexes
            self._preview_field_names = field_names
            self._preview_converted_text = converted_text
            for preview_row in range(len(row_indexes)):
                self._populate_preview_row(preview_row)
        finally:
            self.preview.setUpdatesEnabled(True)
            self.preview.viewport().update()
        depth_name = self.depth_field.currentData() or self._t("paradox.not_selected")
        selected_time = self.time_field.currentData() or self._t("paradox.not_selected")
        self.preview_summary.setText(
            self._t(
                "paradox.preview_summary",
                depth=depth_name,
                time=selected_time,
                rows=len(row_indexes),
            )
        )
        header = self.preview.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(92)
        header.setMinimumSectionSize(54)
        header.setStretchLastSection(False)

    def _update_depth_step_labels(self) -> None:
        if self.table is None:
            return
        depth_name = self.depth_field.currentData()
        if depth_name not in self.table.columns:
            self.actual_depth_step.setText("—")
            self.actual_depth_step.setStyleSheet("")
            return
        values = np.asarray(self.table.columns[str(depth_name)].values, dtype=np.float64)
        finite = values[np.isfinite(values)]
        positive = np.diff(finite)
        positive = positive[positive > 0]
        if not positive.size:
            self.actual_depth_step.setText("—")
            self.actual_depth_step.setStyleSheet("")
            return
        actual = float(np.median(positive))
        matches = np.isclose(
            actual,
            GEOSCAPE_STANDARD_DEPTH_STEP_M,
            rtol=0.0,
            atol=1e-6,
        )
        self.actual_depth_step.setText(
            self._t(
                "paradox.actual_depth_step_value",
                step=f"{actual:g}",
                status=self._t(
                    "paradox.step_matches_standard"
                    if matches
                    else "paradox.step_differs_from_standard"
                ),
            )
        )
        self.actual_depth_step.setStyleSheet(
            "color:#166534; font-weight:600;"
            if matches
            else "color:#9a3412; font-weight:600;"
        )

    def _populate_index_combo(self, combo: QComboBox, candidates: tuple, role: str) -> None:
        combo.clear()
        combo.addItem(self._t("paradox.not_selected"), None)
        used: set[str] = set()
        for candidate in candidates:
            combo.addItem(
                f"{candidate.field_name} — {candidate.confidence:.0%}", candidate.field_name
            )
            used.add(candidate.field_name)
        assert self.table is not None
        for field in self.table.fields:
            if field.is_numeric and field.name not in used:
                combo.addItem(f"{field.name} — {self._t('paradox.manual')}", field.name)
        if combo.count() > 1:
            combo.setCurrentIndex(1)

    def import_plan(self) -> ParadoxImportPlan:
        assert self.table is not None
        mappings: list[ChannelMapping] = []
        for row in range(self.channels.rowCount()):
            checked = self._channel_item(row, 0).checkState() == Qt.CheckState.Checked
            mappings.append(
                ChannelMapping(
                    source_name=self._channel_item(row, 1).text(),
                    mnemonic=self._channel_item(row, 2).text().strip(),
                    description=self._channel_item(row, 3).text().strip(),
                    unit=self._channel_item(row, 4).text().strip(),
                    import_enabled=checked,
                )
            )
        return ParadoxImportPlan(
            classification=DatasetClassification(str(self.classification.currentData())),
            depth_field=self.depth_field.currentData(),
            time_field=self.time_field.currentData(),
            active_role=self.active_role.currentData(),
            null_value=self.null_value.value(),
            sort_by_index=self.sort_index.isChecked(),
            mappings=tuple(mappings),
            profile_name=self._profile_name,
            duplicate_depth_policy=DuplicateDepthPolicy(
                str(self.duplicate_policy.currentData())
            ),
            drop_empty_channels=self.drop_empty_channels.isChecked(),
            language=self.localizer.language.value,
        )

    def _channel_item(self, row: int, column: int) -> QTableWidgetItem:
        item = self.channels.item(row, column)
        if item is None:
            raise RuntimeError(
                f"Paradox channel table is incomplete at row {row}, column {column}"
            )
        return item

    def _finish(self, action: str) -> None:
        if self.table is None:
            return
        plan = self.import_plan()
        if plan.depth_field is None and plan.time_field is None:
            QMessageBox.warning(self, self._t("paradox.title"), self._t("paradox.select_index"))
            return
        if plan.active_role == "depth" and plan.depth_field is None:
            QMessageBox.warning(self, self._t("paradox.title"), self._t("paradox.select_depth"))
            return
        if plan.active_role == "time" and plan.time_field is None:
            QMessageBox.warning(self, self._t("paradox.title"), self._t("paradox.select_time"))
            return
        if action == "configure" or self.configuration_only:
            self.selected_plan = plan
            self.requested_action = "configure"
            self.accept()
            return
        self._start_import(plan, action)

    def _start_import(self, plan: ParadoxImportPlan, action: str) -> None:
        assert self.table is not None
        assert self.quality is not None
        self._pending_action = action
        self._cancel_pending = False
        self._started_at = monotonic()
        self._last_progress_at = self._started_at
        self._set_busy(True)
        self._set_progress_state(
            phase="create", current=0, total=max(1, len(self.table.fields)),
            overall=0.94, phase_number=6
        )
        self.progress_hint.setText(self._t("paradox.create_hint"))
        worker = _ImportWorker(self.source, self.table, self.quality, plan)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_imported)
        worker.failed.connect(self._on_import_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda current=thread: self._clear_thread_reference(current, "import"))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._import_worker = worker
        thread.start()

    @Slot(object)
    def _on_imported(self, result: object) -> None:
        if self._cancel_pending:
            return
        if not isinstance(result, ParadoxImportResult):
            self._on_import_failed(self._t("paradox.invalid_worker_result"))
            return
        self.import_result = result
        self.requested_action = self._pending_action
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000)
        self.status.setText(self._t("paradox.completed"))
        self.progress_detail.setText(self._t("paradox.completed_hint"))
        self._set_busy(False)
        self._heartbeat.stop()
        self.accept()

    @Slot(str)
    def _on_import_failed(self, message: str) -> None:
        if self._cancel_pending:
            self.status.setText(self._t("paradox.cancelled"))
            return
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.status.setText(self._t("paradox.failed"))
        self.progress_detail.setText(message)
        self.progress_hint.setText(self._t("paradox.failed_hint"))
        self._set_busy(False)
        QMessageBox.critical(self, self._t("paradox.title"), message)

    def _load_profile(self) -> None:
        if self.table is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("paradox.load_profile"),
            "",
            "Paradox import profile (*.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            profile = load_profile(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            QMessageBox.critical(self, self._t("paradox.load_profile"), str(exc))
            return
        current_signature = schema_signature(self.table)
        if profile.schema_signature != current_signature:
            QMessageBox.warning(
                self,
                self._t("paradox.load_profile"),
                self._t("paradox.profile_mismatch"),
            )
            return
        self._apply_profile(profile)
        self.status.setText(self._t("paradox.profile_loaded", name=profile.name))

    def _apply_profile(self, profile: ImportProfile) -> None:
        plan = profile.plan
        self._profile_name = profile.name
        classification_index = self.classification.findData(plan.classification)
        if classification_index >= 0:
            self.classification.setCurrentIndex(classification_index)
        for combo, value in (
            (self.depth_field, plan.depth_field),
            (self.time_field, plan.time_field),
        ):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        role_index = self.active_role.findData(plan.active_role)
        if role_index >= 0:
            self.active_role.setCurrentIndex(role_index)
        self.sort_index.setChecked(plan.sort_by_index)
        self.null_value.setValue(plan.null_value)
        duplicate_index = self.duplicate_policy.findData(plan.duplicate_depth_policy)
        if duplicate_index >= 0:
            self.duplicate_policy.setCurrentIndex(duplicate_index)
        self.drop_empty_channels.setChecked(plan.drop_empty_channels)
        mappings = {item.source_name: item for item in plan.mappings}
        for row in range(self.channels.rowCount()):
            source_item = self.channels.item(row, 1)
            if source_item is None:
                continue
            mapping = mappings.get(source_item.text())
            if mapping is None:
                continue
            self._channel_item(row, 0).setCheckState(
                Qt.CheckState.Checked if mapping.import_enabled else Qt.CheckState.Unchecked
            )
            self._channel_item(row, 2).setText(mapping.mnemonic)
            self._channel_item(row, 3).setText(mapping.description)
            self._channel_item(row, 4).setText(mapping.unit)

    def _load_dictionary(self) -> None:
        if self.table is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("paradox.load_dictionary"),
            "",
            "GeoScape channel dictionary (*.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            dictionary = GeoScapeChannelDictionary.load(path)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, self._t("paradox.load_dictionary"), str(exc))
            return
        applied = 0
        language_code = getattr(self.language, "value", str(self.language))
        for row in range(self.channels.rowCount()):
            source_item = self.channels.item(row, 1)
            if source_item is None:
                continue
            definition = dictionary.resolve(source_item.text())
            if definition is None:
                continue
            self._channel_item(row, 2).setText(definition.mnemonic)
            self._channel_item(row, 3).setText(definition.localized_name(language_code))
            self._channel_item(row, 4).setText(definition.unit)
            applied += 1
        self.status.setText(self._t("paradox.dictionary_loaded", count=applied))

    def _save_dictionary(self) -> None:
        if self.table is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("paradox.save_dictionary"),
            f"{self.source.stem}.channels.json",
            "GeoScape channel dictionary (*.json);;JSON (*.json)",
        )
        if not path:
            return
        dictionary = GeoScapeChannelDictionary({})
        for row in range(self.channels.rowCount()):
            source = self._channel_item(row, 1).text().strip()
            mnemonic = self._channel_item(row, 2).text().strip() or source
            description = (
                self._channel_item(row, 3).text().strip()
                or f"Source channel {source}"
            )
            unit = self._channel_item(row, 4).text().strip()
            dictionary.set_user(
                ChannelDefinition(
                    source=source,
                    mnemonic=mnemonic,
                    name_ru=description,
                    name_kk=description,
                    name_en=description,
                    unit=unit,
                    category="user",
                )
            )
        dictionary.export_user(path)
        self.status.setText(self._t("paradox.dictionary_saved", path=path))

    def _save_profile(self) -> None:
        if self.table is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("paradox.save_profile"),
            f"{self.source.stem}.paradox-profile.json",
            "JSON (*.json)",
        )
        if not path:
            return
        self._profile_name = Path(path).stem
        plan = self.import_plan()
        profile = ImportProfile(self._profile_name, schema_signature(self.table), plan)
        save_profile(profile, path)
        self.status.setText(self._t("paradox.profile_saved", path=path))

    def reject(self) -> None:
        if not self._busy:
            QDialog.reject(self)
            return
        if self._cancel_pending:
            return
        self._cancel_pending = True
        self._population_timer.stop()
        self._restore_population_updates()
        if self._worker is not None:
            self._worker.request_cancel()
        if self._import_worker is not None:
            self._import_worker.request_cancel()
        if self._thread is not None:
            try:
                self._thread.requestInterruption()
            except RuntimeError:
                self._thread = None
        self.status.setText(self._t("paradox.cancelling"))
        self.progress_detail.setText(self._t("paradox.cancel_wait"))
        self.progress_hint.setText(self._t("paradox.cancel_safe_hint"))
        self.cancel_button.setText(self._t("paradox.stopping"))
        self.cancel_button.setEnabled(False)
        thread = self._thread
        if thread is not None:
            try:
                running = thread.isRunning()
            except RuntimeError:
                self._thread = None
                running = False
            if running:
                thread.finished.connect(self._reject_after_worker)
                return
        self._reject_after_worker()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            event.ignore()
            self.reject()
            return
        event.accept()

    @Slot()
    def _reject_after_worker(self) -> None:
        self._busy = False
        self._population_timer.stop()
        self._heartbeat.stop()
        QDialog.reject(self)


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if not np.isfinite(value):
            return "NULL"
        return f"{value:.10g}"
    if isinstance(value, bytes):
        return value[:16].hex() + ("…" if len(value) > 16 else "")
    return str(value)
