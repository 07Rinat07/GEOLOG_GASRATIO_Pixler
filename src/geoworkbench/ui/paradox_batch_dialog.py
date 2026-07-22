from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.paradox.batch import BatchItemResult, convert_batch
from geoworkbench.importers.paradox.profiles import load_profile, schema_signature
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
    ) -> None:
        super().__init__()
        self.sources = sources
        self.output = output
        self.profile_path = profile_path
        self.modes = modes
        self.name_mask = name_mask
        self.overwrite = overwrite
        self.localizer = Localizer.create(language)
        self.cancel_requested = False

    @Slot()
    def run(self) -> None:
        try:
            profile = load_profile(self.profile_path) if self.profile_path is not None else None

            def plan_factory(source: Path, table):
                if profile is None:
                    return None
                if schema_signature(table) != profile.schema_signature:
                    raise ValueError(
                        self.localizer.text(
                            "paradox.batch_profile_mismatch", file=source.name
                        )
                    )
                return profile.plan

            factory = plan_factory if profile is not None else None
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
        self._cancel_pending = False
        self.setWindowTitle(self._t("paradox.batch_title"))
        self.resize(980, 640)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.output = QLineEdit(str(self.sources[0].parent if self.sources else Path.cwd()))
        choose_output = QPushButton(self._t("paradox.choose_folder"))
        choose_output.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output, 1)
        output_row.addWidget(choose_output)
        form.addRow(self._t("paradox.output_folder"), output_row)

        self.profile = QLineEdit()
        self.profile.setPlaceholderText(self._t("paradox.profile_optional"))
        choose_profile = QPushButton(self._t("paradox.choose_profile"))
        choose_profile.clicked.connect(self._choose_profile)
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile, 1)
        profile_row.addWidget(choose_profile)
        form.addRow(self._t("paradox.import_profile"), profile_row)

        self.name_mask = QLineEdit("{source_name}_{mode}.las")
        form.addRow(self._t("paradox.name_mask"), self.name_mask)

        mode_row = QHBoxLayout()
        self.depth_mode = QCheckBox(self._t("paradox.batch_depth"))
        self.depth_mode.setChecked(True)
        self.time_mode = QCheckBox(self._t("paradox.batch_time"))
        self.time_mode.setChecked(True)
        mode_row.addWidget(self.depth_mode)
        mode_row.addWidget(self.time_mode)
        mode_row.addStretch(1)
        form.addRow(self._t("paradox.export_modes"), mode_row)

        self.overwrite = QCheckBox(self._t("paradox.overwrite"))
        form.addRow(self.overwrite)
        root.addLayout(form)

        source_row = QHBoxLayout()
        add_folder = QPushButton(self._t("paradox.add_folder"))
        add_folder.clicked.connect(self._add_folder)
        self.recursive = QCheckBox(self._t("paradox.recursive"))
        source_row.addWidget(add_folder)
        source_row.addWidget(self.recursive)
        source_row.addStretch(1)
        root.addLayout(source_row)

        self.summary = QLabel()
        root.addWidget(self.summary)
        self._update_source_summary()

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        root.addWidget(self.progress)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("paradox.source_file"),
                self._t("paradox.target_file"),
                self._t("paradox.status"),
                self._t("paradox.records"),
                self._t("paradox.channels"),
                self._t("paradox.message"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.start = buttons.addButton(
            self._t("paradox.start_batch"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.start.clicked.connect(self._start)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.cancel"))
        root.addWidget(buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

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
        candidates = [
            path.resolve()
            for path in iterator
            if path.is_file() and path.suffix.casefold() == ".db"
        ]
        existing = set(self.sources)
        self.sources.extend(path for path in sorted(candidates) if path not in existing)
        self.sources = list(dict.fromkeys(self.sources))
        self._update_source_summary()

    def _update_source_summary(self) -> None:
        self.summary.setText(self._t("paradox.batch_files", count=len(self.sources)))

    def _start(self) -> None:
        if not self.sources:
            QMessageBox.warning(
                self, self._t("paradox.batch_title"), self._t("paradox.no_batch_files")
            )
            return
        modes = tuple(
            mode
            for enabled, mode in (
                (self.depth_mode.isChecked(), "depth"),
                (self.time_mode.isChecked(), "time"),
            )
            if enabled
        )
        if not modes:
            QMessageBox.warning(
                self, self._t("paradox.batch_title"), self._t("paradox.select_batch_mode")
            )
            return
        output = Path(self.output.text()).expanduser()
        profile_path = (
            Path(self.profile.text()).expanduser() if self.profile.text().strip() else None
        )
        self._cancel_pending = False
        self.start.setEnabled(False)
        self.progress.setRange(0, max(1, len(self.sources) * len(modes)))
        self.progress.setValue(0)
        worker = _BatchWorker(
            tuple(self.sources),
            output,
            profile_path,
            modes,
            self.name_mask.text().strip() or "{source_name}_{mode}.las",
            self.overwrite.isChecked(),
            self.localizer.language,
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
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(str, int, int)
    def _progress(self, name: str, current: int, total: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(current)
        self.summary.setText(
            self._t("paradox.batch_progress", file=name, current=current, total=total)
        )

    @Slot(object)
    def _done(self, payload: object) -> None:
        if self._cancel_pending:
            return
        results = tuple(payload) if isinstance(payload, (tuple, list)) else ()
        self.progress.setRange(0, max(1, len(results)))
        self.progress.setValue(len(results))
        self.table.setRowCount(len(results))
        for row, item in enumerate(results):
            assert isinstance(item, BatchItemResult)
            values = (
                item.source.name,
                item.target.name if item.target else "",
                item.status.value,
                item.records,
                item.channels,
                item.message,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.start.setEnabled(True)
        self.summary.setText(self._t("paradox.batch_done", count=len(results)))

    @Slot(str)
    def _failed(self, message: str) -> None:
        if self._cancel_pending:
            return
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.start.setEnabled(True)
        QMessageBox.critical(self, self._t("paradox.batch_title"), message)

    def reject(self) -> None:
        if self._cancel_pending:
            return
        self._cancel_pending = True
        if self._worker is not None:
            self._worker.cancel_requested = True
        if self._thread is not None and self._thread.isRunning():
            self.summary.setText(self._t("paradox.cancelling"))
            self._thread.finished.connect(lambda: QDialog.reject(self))
            return
        super().reject()
