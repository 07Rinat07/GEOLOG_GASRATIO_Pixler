from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.paradox.batch import (
    BatchItemResult,
    BatchStatus,
    _target_name,
    convert_batch,
)
from geoworkbench.importers.paradox.models import ParadoxImportPlan
from geoworkbench.importers.paradox.profiles import load_profile, schema_signature
from geoworkbench.ui.paradox_import_dialog import ParadoxImportDialog
from geoworkbench.services.localization import AppLanguage, Localizer


class _BatchWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)

    def __init__(
        self,
        sources: tuple[Path, ...],
        output: Path,
        profile_path: Path | None,
        modes: tuple[str, ...],
        name_mask: str,
        overwrite: bool,
        language: AppLanguage,
        manual_plans: dict[Path, ParadoxImportPlan] | None = None,
    ) -> None:
        super().__init__()
        self.sources = sources
        self.output = output
        self.profile_path = profile_path
        self.modes = modes
        self.name_mask = name_mask
        self.overwrite = overwrite
        self.localizer = Localizer.create(language)
        self.manual_plans = {
            path.expanduser().resolve(): plan
            for path, plan in (manual_plans or {}).items()
        }
        self.cancel_requested = False

    @Slot()
    def run(self) -> None:
        try:
            # Protect the user from a very common destructive-looking setup:
            # several source/mode operations resolving to the same output name.
            # The backend validates this again even though the dialog previews it.
            targets: dict[Path, tuple[Path, str]] = {}
            for mode in self.modes:
                for source in self.sources:
                    target = (self.output / _target_name(self.name_mask, source, mode)).resolve()
                    previous = targets.get(target)
                    if previous is not None:
                        raise ValueError(
                            self.localizer.text(
                                "paradox.batch_duplicate_targets",
                                target=target.name,
                                first=previous[0].name,
                                second=source.name,
                            )
                        )
                    targets[target] = (source, mode)

            profile = load_profile(self.profile_path) if self.profile_path is not None else None

            def plan_factory(source: Path, table):
                resolved = source.expanduser().resolve()
                manual = self.manual_plans.get(resolved)
                if manual is not None:
                    return manual
                if profile is None:
                    return None
                if schema_signature(table) != profile.schema_signature:
                    raise ValueError(
                        self.localizer.text(
                            "paradox.batch_profile_mismatch", file=source.name
                        )
                    )
                return profile.plan

            factory = plan_factory if profile is not None or self.manual_plans else None
            total = max(1, len(self.sources) * len(self.modes))
            results: list[BatchItemResult] = []
            offset = 0
            for mode in self.modes:
                converted = convert_batch(
                    self.sources,
                    self.output,
                    mode=mode,
                    overwrite=self.overwrite,
                    plan_factory=factory,
                    name_mask=self.name_mask,
                    progress=lambda name, current, count, base=offset: self.progress.emit(
                        name, base + current, total
                    ),
                    cancelled=lambda: self.cancel_requested,
                    language=self.localizer.language.value,
                    translate=self.localizer.text,
                )
                results.extend(converted)
                offset += len(self.sources)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(tuple(results))


class ParadoxBatchDialog(QDialog):
    """User-facing DB -> LAS batch workflow.

    Conversion itself writes LAS files immediately.  There is intentionally no
    second Save button: the dialog explains the destination, previews every
    target path and exposes explicit post-run actions for opening the folder or
    importing the generated LAS into the current application.
    """

    open_las_requested = Signal(object)

    def __init__(
        self,
        sources: tuple[Path, ...],
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.sources = list(dict.fromkeys(path.expanduser().resolve() for path in sources))
        self.localizer = Localizer.create(language)
        self._thread: QThread | None = None
        self._worker: _BatchWorker | None = None
        self._running = False
        self._cancel_requested = False
        self._close_after_cancel = False
        self._results: tuple[BatchItemResult, ...] = ()
        self._result_by_row: dict[int, BatchItemResult] = {}
        self._result_mode_by_row: dict[int, str] = {}
        self._active_modes: tuple[str, ...] = ()
        self._manual_plans: dict[Path, ParadoxImportPlan] = {}

        self.setWindowTitle(self._t("paradox.batch_title"))
        self.resize(1100, 720)
        self.setMinimumSize(860, 580)

        root = QVBoxLayout(self)

        self.instructions = QLabel(self._t("paradox.batch_instructions"))
        self.instructions.setWordWrap(True)
        self.instructions.setFrameShape(QFrame.Shape.StyledPanel)
        self.instructions.setContentsMargins(12, 10, 12, 10)
        root.addWidget(self.instructions)

        form = QFormLayout()

        self.output = QLineEdit(str(self.sources[0].parent if self.sources else Path.cwd()))
        self.output.setToolTip(self._t("paradox.output_folder_help"))
        self.choose_output_button = QPushButton(self._t("paradox.choose_folder"))
        self.choose_output_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output, 1)
        output_row.addWidget(self.choose_output_button)
        form.addRow(self._t("paradox.output_folder"), output_row)

        self.profile = QLineEdit()
        self.profile.setPlaceholderText(self._t("paradox.profile_optional"))
        self.choose_profile_button = QPushButton(self._t("paradox.choose_profile"))
        self.choose_profile_button.clicked.connect(self._choose_profile)
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile, 1)
        profile_row.addWidget(self.choose_profile_button)
        form.addRow(self._t("paradox.import_profile"), profile_row)

        self.profile_help = QLabel(self._t("paradox.profile_help"))
        self.profile_help.setWordWrap(True)
        self.profile_help.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("", self.profile_help)

        self.name_mask = QLineEdit("{source_name}_{mode}.las")
        self.name_mask.setToolTip(self._t("paradox.name_mask_help"))
        self.reset_mask_button = QPushButton(self._t("paradox.use_recommended_mask"))
        self.reset_mask_button.clicked.connect(
            lambda: self.name_mask.setText("{source_name}_{mode}.las")
        )
        mask_row = QHBoxLayout()
        mask_row.addWidget(self.name_mask, 1)
        mask_row.addWidget(self.reset_mask_button)
        form.addRow(self._t("paradox.name_mask"), mask_row)

        mode_row = QHBoxLayout()
        self.depth_mode = QCheckBox(self._t("paradox.batch_depth"))
        self.depth_mode.setChecked(True)
        self.depth_mode.setToolTip(self._t("paradox.batch_depth_help"))
        self.time_mode = QCheckBox(self._t("paradox.batch_time"))
        self.time_mode.setChecked(False)
        self.time_mode.setToolTip(self._t("paradox.batch_time_help"))
        mode_row.addWidget(self.depth_mode)
        mode_row.addWidget(self.time_mode)
        mode_row.addStretch(1)
        form.addRow(self._t("paradox.export_modes"), mode_row)

        self.overwrite = QCheckBox(self._t("paradox.overwrite"))
        self.overwrite.setToolTip(self._t("paradox.overwrite_help"))
        form.addRow("", self.overwrite)
        root.addLayout(form)

        source_row = QHBoxLayout()
        self.add_files_button = QPushButton(self._t("paradox.add_files"))
        self.add_files_button.clicked.connect(self._add_files)
        self.add_folder_button = QPushButton(self._t("paradox.add_folder"))
        self.add_folder_button.clicked.connect(self._add_folder)
        self.remove_sources_button = QPushButton(self._t("paradox.remove_selected"))
        self.remove_sources_button.clicked.connect(self._remove_selected_sources)
        self.clear_sources_button = QPushButton(self._t("paradox.clear_sources"))
        self.clear_sources_button.clicked.connect(self._clear_sources)
        self.recursive = QCheckBox(self._t("paradox.recursive"))
        source_row.addWidget(self.add_files_button)
        source_row.addWidget(self.add_folder_button)
        source_row.addWidget(self.remove_sources_button)
        source_row.addWidget(self.clear_sources_button)
        source_row.addWidget(self.recursive)
        source_row.addStretch(1)
        root.addLayout(source_row)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.plan_hint = QLabel()
        self.plan_hint.setWordWrap(True)
        self.plan_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.plan_hint)

        progress_row = QHBoxLayout()
        self.phase_label = QLabel(self._t("paradox.batch_ready"))
        progress_row.addWidget(self.phase_label, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m   (%p%)")
        progress_row.addWidget(self.progress, 2)
        root.addLayout(progress_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("paradox.source_file"),
                self._t("paradox.mode"),
                self._t("paradox.target_file"),
                self._t("paradox.status"),
                self._t("paradox.records"),
                self._t("paradox.channels"),
                self._t("paradox.message"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 310)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._open_selected_las())
        root.addWidget(self.table, 1)

        self.details = QLabel(self._t("paradox.select_row_for_details"))
        self.details.setWordWrap(True)
        self.details.setFrameShape(QFrame.Shape.StyledPanel)
        self.details.setContentsMargins(8, 6, 8, 6)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.details)

        self.finish_hint = QLabel()
        self.finish_hint.setWordWrap(True)
        self.finish_hint.setFrameShape(QFrame.Shape.StyledPanel)
        self.finish_hint.setContentsMargins(10, 8, 10, 8)
        self.finish_hint.hide()
        root.addWidget(self.finish_hint)

        actions = QHBoxLayout()
        self.open_folder_button = QPushButton(self._t("paradox.open_result_folder"))
        self.open_folder_button.clicked.connect(self._open_result_folder)
        self.open_las_button = QPushButton(self._t("paradox.open_selected_las"))
        self.open_las_button.clicked.connect(self._open_selected_las)
        self.open_las_button.setEnabled(False)
        self.configure_source_button = QPushButton(
            self._t("paradox.configure_selected_source")
        )
        self.configure_source_button.clicked.connect(self._configure_selected_source)
        self.configure_source_button.setEnabled(False)
        self.configure_source_button.setToolTip(
            self._t("paradox.configure_selected_source_hint")
        )
        self.retry_failed_button = QPushButton(self._t("paradox.retry_failed"))
        self.retry_failed_button.clicked.connect(self._retry_failed)
        self.retry_failed_button.hide()
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.open_las_button)
        actions.addWidget(self.configure_source_button)
        actions.addWidget(self.retry_failed_button)
        actions.addStretch(1)

        self.start = QPushButton(self._t("paradox.convert_and_save"))
        self.start.setDefault(True)
        self.start.clicked.connect(self._start)
        self.cancel_operation_button = QPushButton(self._t("paradox.stop_conversion"))
        self.cancel_operation_button.clicked.connect(
            lambda: self._request_cancel(close_after=False)
        )
        self.cancel_operation_button.hide()
        self.close_button = QPushButton(self._t("common.close"))
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.start)
        actions.addWidget(self.cancel_operation_button)
        actions.addWidget(self.close_button)
        root.addLayout(actions)

        self._configuration_widgets = (
            self.output,
            self.choose_output_button,
            self.profile,
            self.choose_profile_button,
            self.name_mask,
            self.reset_mask_button,
            self.depth_mode,
            self.time_mode,
            self.overwrite,
            self.add_files_button,
            self.add_folder_button,
            self.remove_sources_button,
            self.clear_sources_button,
            self.recursive,
        )

        self.output.textChanged.connect(self._configuration_changed)
        self.name_mask.textChanged.connect(self._configuration_changed)
        self.depth_mode.toggled.connect(self._configuration_changed)
        self.time_mode.toggled.connect(self._configuration_changed)
        self.overwrite.toggled.connect(self._configuration_changed)
        self.profile.textChanged.connect(self._configuration_changed)

        self._refresh_plan_preview()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _mode_label(self, mode: str) -> str:
        return self._t("paradox.batch_depth" if mode == "depth" else "paradox.batch_time")

    def _selected_modes(self) -> tuple[str, ...]:
        return tuple(
            mode
            for enabled, mode in (
                (self.depth_mode.isChecked(), "depth"),
                (self.time_mode.isChecked(), "time"),
            )
            if enabled
        )

    def _configuration_changed(self, *_args: object) -> None:
        if self._running:
            return
        self._results = ()
        self._result_by_row.clear()
        self._result_mode_by_row.clear()
        self.finish_hint.hide()
        self.retry_failed_button.hide()
        self.configure_source_button.setEnabled(False)
        self.start.setText(self._t("paradox.convert_and_save"))
        self._refresh_plan_preview()

    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, self._t("paradox.output_folder"), self.output.text()
        )
        if selected:
            self.output.setText(selected)

    def _choose_profile(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self._t("paradox.choose_profile"),
            self.profile.text(),
            "Paradox import profile (*.json);;JSON (*.json)",
        )
        if selected:
            self.profile.setText(selected)

    def _add_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            self._t("paradox.add_files"),
            str(self.sources[0].parent if self.sources else Path.cwd()),
            "Paradox DB (*.db *.DB)",
        )
        if not selected:
            return
        self._add_sources(Path(item).resolve() for item in selected)

    def _add_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._t("paradox.add_folder"),
            str(self.sources[0].parent if self.sources else Path.cwd()),
        )
        if not selected:
            return
        directory = Path(selected)
        iterator = directory.rglob("*") if self.recursive.isChecked() else directory.iterdir()
        self._add_sources(
            path.resolve()
            for path in iterator
            if path.is_file() and path.suffix.casefold() == ".db"
        )

    def _add_sources(self, paths) -> None:
        existing = set(self.sources)
        additions = [path for path in paths if path not in existing]
        self.sources.extend(sorted(additions))
        self.sources = list(dict.fromkeys(self.sources))
        self._configuration_changed()

    def _selected_source_paths(self) -> set[Path]:
        result: set[Path] = set()
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            if item is None:
                continue
            value = item.data(Qt.ItemDataRole.UserRole)
            if value:
                result.add(Path(str(value)))
        return result

    def _remove_selected_sources(self) -> None:
        selected = self._selected_source_paths()
        if not selected:
            QMessageBox.information(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.select_sources_to_remove"),
            )
            return
        self.sources = [source for source in self.sources if source not in selected]
        self._configuration_changed()

    def _clear_sources(self) -> None:
        if not self.sources:
            return
        self.sources.clear()
        self._configuration_changed()

    def _target_plan(self) -> tuple[tuple[Path, str, Path], ...]:
        if not self.sources:
            raise ValueError(self._t("paradox.no_batch_files"))
        modes = self._selected_modes()
        if not modes:
            raise ValueError(self._t("paradox.select_batch_mode"))
        output_text = self.output.text().strip()
        if not output_text:
            raise ValueError(self._t("paradox.output_required"))
        output = Path(output_text).expanduser().resolve()
        mask = self.name_mask.text().strip() or "{source_name}_{mode}.las"
        plan: list[tuple[Path, str, Path]] = []
        targets: dict[Path, tuple[Path, str]] = {}
        for mode in modes:
            for source in self.sources:
                target = (output / _target_name(mask, source, mode)).resolve()
                previous = targets.get(target)
                if previous is not None:
                    raise ValueError(
                        self._t(
                            "paradox.batch_duplicate_targets",
                            target=target.name,
                            first=previous[0].name,
                            second=source.name,
                        )
                    )
                targets[target] = (source, mode)
                plan.append((source, mode, target))
        return tuple(plan)

    def _refresh_plan_preview(self) -> None:
        self.summary.setText(self._t("paradox.batch_files", count=len(self.sources)))
        self.phase_label.setText(self._t("paradox.batch_ready"))
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.table.clearContents()
        self.table.setRowCount(0)
        self.details.setText(self._t("paradox.select_row_for_details"))
        self.open_las_button.setEnabled(False)

        try:
            plan = self._target_plan()
        except ValueError as exc:
            self.plan_hint.setText(self._t("paradox.plan_error", message=str(exc)))
            self.start.setEnabled(False)
            # Still show one row per selected source so users can remove files.
            self.table.setRowCount(len(self.sources))
            for row, source in enumerate(self.sources):
                source_item = QTableWidgetItem(source.name)
                source_item.setData(Qt.ItemDataRole.UserRole, str(source))
                source_item.setToolTip(str(source))
                self.table.setItem(row, 0, source_item)
                self.table.setItem(row, 3, QTableWidgetItem(self._t("paradox.status_not_ready")))
                self.table.setItem(row, 6, QTableWidgetItem(str(exc)))
            return

        existing_count = sum(1 for _source, _mode, target in plan if target.exists())
        self.plan_hint.setText(
            self._t(
                "paradox.plan_summary",
                operations=len(plan),
                folder=str(Path(self.output.text()).expanduser().resolve()),
                existing=existing_count,
            )
        )
        self.start.setEnabled(True)
        self.table.setRowCount(len(plan))
        for row, (source, mode, target) in enumerate(plan):
            source_item = QTableWidgetItem(source.name)
            source_item.setData(Qt.ItemDataRole.UserRole, str(source))
            source_item.setToolTip(str(source))
            mode_item = QTableWidgetItem(self._mode_label(mode))
            mode_item.setData(Qt.ItemDataRole.UserRole, mode)
            target_item = QTableWidgetItem(str(target))
            target_item.setToolTip(str(target))
            target_item.setData(Qt.ItemDataRole.UserRole, str(target))
            if target.exists() and not self.overwrite.isChecked():
                status = self._t("paradox.status_will_skip")
                message = self._t("paradox.batch_exists")
            else:
                status = self._t("paradox.status_ready")
                message = self._t("paradox.ready_message")
            self.table.setItem(row, 0, source_item)
            self.table.setItem(row, 1, mode_item)
            self.table.setItem(row, 2, target_item)
            self.table.setItem(row, 3, QTableWidgetItem(status))
            self.table.setItem(row, 4, QTableWidgetItem("—"))
            self.table.setItem(row, 5, QTableWidgetItem("—"))
            message_item = QTableWidgetItem(message)
            message_item.setToolTip(message)
            self.table.setItem(row, 6, message_item)

    def _set_running(self, running: bool) -> None:
        self._running = running
        for widget in self._configuration_widgets:
            widget.setEnabled(not running)
        self.start.setEnabled(not running)
        self.cancel_operation_button.setVisible(running)
        self.cancel_operation_button.setEnabled(running)
        if running:
            self.open_las_button.setEnabled(False)
            self.configure_source_button.setEnabled(False)
        self.retry_failed_button.setEnabled(not running)
        self.close_button.setEnabled(True)
        self.close_button.setText(
            self._t("paradox.cancel_and_close") if running else self._t("common.close")
        )

    def _start(self) -> None:
        try:
            plan = self._target_plan()
        except ValueError as exc:
            QMessageBox.warning(self, self._t("paradox.batch_title"), str(exc))
            self._refresh_plan_preview()
            return

        profile_path = (
            Path(self.profile.text()).expanduser().resolve()
            if self.profile.text().strip()
            else None
        )
        if profile_path is not None and not profile_path.is_file():
            QMessageBox.warning(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.profile_not_found", file=str(profile_path)),
            )
            return

        output = Path(self.output.text()).expanduser().resolve()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.output_create_failed", message=str(exc)),
            )
            return

        modes = self._selected_modes()
        self._active_modes = modes
        self._results = ()
        self._result_by_row.clear()
        self._result_mode_by_row.clear()
        self.finish_hint.hide()
        self.retry_failed_button.hide()
        self._cancel_requested = False
        self._close_after_cancel = False
        self.start.setText(self._t("paradox.convert_and_save"))
        self._set_running(True)
        self.progress.setRange(0, max(1, len(plan)))
        self.progress.setValue(0)
        self.phase_label.setText(self._t("paradox.preparing_conversion"))
        self.summary.setText(self._t("paradox.batch_starting", count=len(plan)))

        worker = _BatchWorker(
            tuple(self.sources),
            output,
            profile_path,
            modes,
            self.name_mask.text().strip() or "{source_name}_{mode}.las",
            self.overwrite.isChecked(),
            self.localizer.language,
            dict(self._manual_plans),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._progress)
        worker.finished.connect(self._done)
        worker.failed.connect(self._failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(str, int, int)
    def _progress(self, name: str, current: int, total: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(current)
        self.phase_label.setText(
            self._t("paradox.batch_progress", file=name, current=current, total=total)
        )
        self.summary.setText(
            self._t("paradox.batch_progress_help", file=name, current=current, total=total)
        )

    def _status_text(self, status: BatchStatus) -> str:
        return self._t(f"paradox.status_{status.value}")

    def _status_icon(self, status: BatchStatus):
        icon_map = {
            BatchStatus.SUCCESS: QStyle.StandardPixmap.SP_DialogApplyButton,
            BatchStatus.WARNING: QStyle.StandardPixmap.SP_MessageBoxWarning,
            BatchStatus.ERROR: QStyle.StandardPixmap.SP_MessageBoxCritical,
            BatchStatus.SKIPPED: QStyle.StandardPixmap.SP_MessageBoxInformation,
            BatchStatus.CONFIGURATION_REQUIRED: QStyle.StandardPixmap.SP_MessageBoxWarning,
        }
        return self.style().standardIcon(icon_map[status])

    @Slot(object)
    def _done(self, payload: object) -> None:
        results = tuple(payload) if isinstance(payload, (tuple, list)) else ()
        self._results = tuple(item for item in results if isinstance(item, BatchItemResult))
        self._set_running(False)
        self.progress.setRange(0, max(1, len(self._results)))
        self.progress.setValue(len(self._results))
        self.phase_label.setText(self._t("paradox.batch_completed"))
        self.table.clearContents()
        self.table.setRowCount(len(self._results))
        self._result_by_row.clear()
        self._result_mode_by_row.clear()

        source_count = max(1, len(self.sources))
        for row, item in enumerate(self._results):
            mode_index = min(row // source_count, max(0, len(self._active_modes) - 1))
            mode = self._active_modes[mode_index] if self._active_modes else "depth"
            self._result_by_row[row] = item
            self._result_mode_by_row[row] = mode
            source_item = QTableWidgetItem(item.source.name)
            source_item.setData(Qt.ItemDataRole.UserRole, str(item.source))
            source_item.setToolTip(str(item.source))
            mode_item = QTableWidgetItem(self._mode_label(mode))
            mode_item.setData(Qt.ItemDataRole.UserRole, mode)
            target_text = str(item.target) if item.target else "—"
            target_item = QTableWidgetItem(target_text)
            target_item.setToolTip(target_text)
            if item.target is not None:
                target_item.setData(Qt.ItemDataRole.UserRole, str(item.target))
            status_item = QTableWidgetItem(self._status_text(item.status))
            status_item.setIcon(self._status_icon(item.status))
            message_item = QTableWidgetItem(item.message)
            message_item.setToolTip(item.message)
            values = (
                source_item,
                mode_item,
                target_item,
                status_item,
                QTableWidgetItem(str(item.records)),
                QTableWidgetItem(str(item.channels)),
                message_item,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, value)

        success = sum(item.status is BatchStatus.SUCCESS for item in self._results)
        warnings = sum(item.status is BatchStatus.WARNING for item in self._results)
        errors = sum(item.status is BatchStatus.ERROR for item in self._results)
        skipped = sum(item.status is BatchStatus.SKIPPED for item in self._results)
        configuration_required = sum(
            item.status is BatchStatus.CONFIGURATION_REQUIRED for item in self._results
        )
        created = success + warnings
        output = str(Path(self.output.text()).expanduser().resolve())
        self.summary.setText(
            self._t(
                "paradox.batch_done_summary",
                created=created,
                warnings=warnings,
                errors=errors,
                skipped=skipped,
            )
        )
        self.finish_hint.setText(
            self._t("paradox.batch_where_results", folder=output, created=created)
        )
        self.finish_hint.show()
        self.start.setText(self._t("paradox.convert_again"))
        self.retry_failed_button.setVisible(errors > 0 or configuration_required > 0)
        self.configure_source_button.setVisible(configuration_required > 0)
        self.open_folder_button.setEnabled(Path(output).is_dir())

        created_rows = [
            row
            for row, item in self._result_by_row.items()
            if item.status in {BatchStatus.SUCCESS, BatchStatus.WARNING}
            and item.target is not None
            and item.target.is_file()
        ]
        configuration_rows = [
            row
            for row, item in self._result_by_row.items()
            if item.status is BatchStatus.CONFIGURATION_REQUIRED
        ]
        if created_rows:
            self.table.selectRow(created_rows[0])
        elif configuration_rows:
            self.table.selectRow(configuration_rows[0])
            self.summary.setText(
                self._t(
                    "paradox.batch_configuration_summary",
                    count=len(configuration_rows),
                )
            )
        else:
            self._selection_changed()

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._set_running(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        if self._cancel_requested:
            self.phase_label.setText(self._t("paradox.batch_cancelled"))
            self.summary.setText(self._t("paradox.batch_cancelled"))
            self.start.setText(self._t("paradox.convert_again"))
            return
        self.phase_label.setText(self._t("paradox.status_error"))
        self.summary.setText(self._t("paradox.batch_failed_inline", message=message))
        self.start.setText(self._t("paradox.convert_again"))
        QMessageBox.critical(self, self._t("paradox.batch_title"), message)

    @Slot()
    def _thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        if self._close_after_cancel:
            QDialog.reject(self)

    def _selection_changed(self) -> None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        valid_targets: list[Path] = []
        for row in rows:
            result = self._result_by_row.get(row)
            if (
                result is not None
                and result.status in {BatchStatus.SUCCESS, BatchStatus.WARNING}
                and result.target is not None
                and result.target.is_file()
            ):
                valid_targets.append(result.target)
        self.open_las_button.setEnabled(bool(valid_targets) and not self._running)
        needs_configuration = any(
            self._result_by_row.get(row) is not None
            and self._result_by_row[row].status is BatchStatus.CONFIGURATION_REQUIRED
            for row in rows
        )
        self.configure_source_button.setEnabled(needs_configuration and not self._running)

        if not rows:
            self.details.setText(self._t("paradox.select_row_for_details"))
            return
        row = rows[0]
        source = self.table.item(row, 0).toolTip() if self.table.item(row, 0) else ""
        mode = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        target = self.table.item(row, 2).toolTip() if self.table.item(row, 2) else ""
        message = self.table.item(row, 6).toolTip() if self.table.item(row, 6) else ""
        self.details.setText(
            self._t(
                "paradox.row_details",
                source=source,
                mode=mode,
                target=target or "—",
                message=message or "—",
            )
        )

    def _configure_selected_source(self) -> None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        source: Path | None = None
        for row in rows:
            result = self._result_by_row.get(row)
            if (
                result is not None
                and result.status is BatchStatus.CONFIGURATION_REQUIRED
            ):
                source = result.source.expanduser().resolve()
                break
        if source is None:
            QMessageBox.information(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.select_source_to_configure"),
            )
            return

        dialog = ParadoxImportDialog(
            source,
            self,
            language=self.localizer.language,
            configuration_only=True,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.selected_plan
        if plan is None:
            QMessageBox.warning(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.configuration_not_applied"),
            )
            return
        self._manual_plans[source] = plan
        self.summary.setText(
            self._t("paradox.configuration_applied", file=source.name)
        )
        answer = QMessageBox.question(
            self,
            self._t("paradox.batch_title"),
            self._t("paradox.retry_after_configuration", file=source.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer is QMessageBox.StandardButton.Yes:
            self.sources = [source]
            self._results = ()
            self._result_by_row.clear()
            self._result_mode_by_row.clear()
            self.finish_hint.hide()
            self.retry_failed_button.hide()
            self.configure_source_button.setEnabled(False)
            self._refresh_plan_preview()
            self._start()

    def _selected_created_targets(self) -> tuple[Path, ...]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        targets: list[Path] = []
        for row in rows:
            result = self._result_by_row.get(row)
            if (
                result is not None
                and result.status in {BatchStatus.SUCCESS, BatchStatus.WARNING}
                and result.target is not None
                and result.target.is_file()
            ):
                targets.append(result.target)
        return tuple(dict.fromkeys(targets))

    def _open_selected_las(self) -> None:
        targets = self._selected_created_targets()
        if not targets:
            QMessageBox.information(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.select_created_las"),
            )
            return
        # End the modal dialog first, then synchronously ask MainWindow to
        # import the already validated LAS through the normal reader path.
        self.accept()
        self.open_las_requested.emit(targets)

    def _open_result_folder(self) -> None:
        folder = Path(self.output.text()).expanduser().resolve()
        if not folder.is_dir():
            QMessageBox.information(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.result_folder_not_created", folder=str(folder)),
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(
                self,
                self._t("paradox.batch_title"),
                self._t("paradox.open_folder_failed", folder=str(folder)),
            )

    def _retry_failed(self) -> None:
        failed_sources = list(
            dict.fromkeys(
                item.source
                for item in self._results
                if item.status in {
                    BatchStatus.ERROR,
                    BatchStatus.CONFIGURATION_REQUIRED,
                }
            )
        )
        if not failed_sources:
            return
        self.sources = failed_sources
        self._results = ()
        self._result_by_row.clear()
        self._result_mode_by_row.clear()
        self.finish_hint.hide()
        self.retry_failed_button.hide()
        self.start.setText(self._t("paradox.convert_and_save"))
        self._refresh_plan_preview()
        self.summary.setText(
            self._t("paradox.retry_ready", count=len(self.sources))
        )

    def _request_cancel(self, *, close_after: bool) -> None:
        if not self._running:
            if close_after:
                QDialog.reject(self)
            return
        if self._cancel_requested:
            self._close_after_cancel = self._close_after_cancel or close_after
            return
        self._cancel_requested = True
        self._close_after_cancel = close_after
        if self._worker is not None:
            self._worker.cancel_requested = True
        self.phase_label.setText(self._t("paradox.cancelling"))
        self.summary.setText(self._t("paradox.cancel_wait"))
        self.cancel_operation_button.setEnabled(False)
        self.close_button.setEnabled(False)

    def reject(self) -> None:
        if not self._running:
            super().reject()
            return
        answer = QMessageBox.question(
            self,
            self._t("paradox.batch_title"),
            self._t("paradox.confirm_cancel_close"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is QMessageBox.StandardButton.Yes:
            self._request_cancel(close_after=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._running:
            event.accept()
            return
        event.ignore()
        self.reject()
