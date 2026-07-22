from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
from geoworkbench.importers.paradox.importer import default_mappings, import_paradox
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
from geoworkbench.services.localization import AppLanguage, Localizer


class _ReaderWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)

    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source
        self.cancel_requested = False

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
        self.cancel_requested = False

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
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.language = language
        self.localizer = Localizer.create(language)
        self.table: ParadoxTable | None = None
        self.quality = None
        self.import_result: ParadoxImportResult | None = None
        self.requested_action = "open"
        self._profile_name: str | None = None
        self._thread: QThread | None = None
        self._worker: _ReaderWorker | None = None
        self._import_worker: _ImportWorker | None = None
        self._pending_action = "open"
        self._cancel_pending = False
        self.setWindowTitle(self._t("paradox.title"))
        self.resize(1180, 760)

        root = QVBoxLayout(self)
        self.status = QLabel(self._t("paradox.reading"))
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        root.addWidget(self.progress)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_file_tab()
        self._build_channels_tab()
        self._build_preview_tab()
        self._build_issues_tab()

        actions = QHBoxLayout()
        self.load_profile_button = QPushButton(self._t("paradox.load_profile"))
        self.load_profile_button.clicked.connect(self._load_profile)
        self.load_profile_button.setEnabled(False)
        actions.addWidget(self.load_profile_button)
        self.profile_button = QPushButton(self._t("paradox.save_profile"))
        self.profile_button.clicked.connect(self._save_profile)
        self.profile_button.setEnabled(False)
        actions.addWidget(self.profile_button)
        self.load_dictionary_button = QPushButton(self._t("paradox.load_dictionary"))
        self.load_dictionary_button.clicked.connect(self._load_dictionary)
        self.load_dictionary_button.setEnabled(False)
        actions.addWidget(self.load_dictionary_button)
        self.save_dictionary_button = QPushButton(self._t("paradox.save_dictionary"))
        self.save_dictionary_button.clicked.connect(self._save_dictionary)
        self.save_dictionary_button.setEnabled(False)
        actions.addWidget(self.save_dictionary_button)
        actions.addStretch(1)
        self.save_las_button = QPushButton(self._t("paradox.save_las"))
        self.save_las_button.clicked.connect(lambda: self._finish("save_las"))
        self.save_las_button.setEnabled(False)
        actions.addWidget(self.save_las_button)
        self.open_button = QPushButton(self._t("paradox.open_editor"))
        self.open_button.clicked.connect(lambda: self._finish("open"))
        self.open_button.setEnabled(False)
        actions.addWidget(self.open_button)
        cancel = QPushButton(self._t("common.cancel"))
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        root.addLayout(actions)

        self._start_reader()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

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
        options.addRow(self._t("paradox.detected_type"), self.classification)
        options.addRow(self._t("paradox.depth_channel"), self.depth_field)
        options.addRow(self._t("paradox.time_channel"), self.time_field)
        options.addRow(self._t("paradox.active_index"), self.active_role)
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
        self.channels.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.channels.horizontalHeader().setStretchLastSection(True)
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
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(str, int, int)
    def _on_progress(self, phase: str, current: int, total: int) -> None:
        labels = {
            "header": self._t("paradox.phase_header"),
            "schema": self._t("paradox.phase_schema"),
            "records": self._t("paradox.phase_records"),
            "analysis": self._t("paradox.phase_analysis"),
            "create": self._t("paradox.phase_create"),
        }
        self.status.setText(labels.get(phase, phase))
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)

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
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status.setText(self._t("paradox.ready"))
        self._populate()
        self.open_button.setEnabled(True)
        self.save_las_button.setEnabled(True)
        self.profile_button.setEnabled(True)
        self.load_profile_button.setEnabled(True)
        self.load_dictionary_button.setEnabled(True)
        self.save_dictionary_button.setEnabled(True)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status.setText(message)
        QMessageBox.critical(self, self._t("paradox.title"), message)

    def _populate(self) -> None:
        assert self.table is not None and self.quality is not None
        table = self.table
        quality = self.quality
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
        self._populate_index_combo(self.depth_field, quality.depth_candidates, "depth")
        self._populate_index_combo(self.time_field, quality.time_candidates, "time")
        self.active_role.setCurrentIndex(1 if quality.depth_candidates else 2)

        mappings = default_mappings(table, language=self.localizer.language.value)
        self.channels.setRowCount(len(table.fields))
        warning_fields = {issue.field_name for issue in quality.issues if issue.field_name}
        for row, (field, mapping) in enumerate(zip(table.fields, mappings, strict=True)):
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
            column = table.columns[field.name]
            self.channels.setItem(
                row,
                6,
                QTableWidgetItem(f"{column.filled_count}/{table.rows_read}"),
            )
            self.channels.setItem(row, 7, QTableWidgetItem(_display(column.minimum)))
            self.channels.setItem(row, 8, QTableWidgetItem(_display(column.maximum)))
            self.channels.setItem(
                row,
                9,
                QTableWidgetItem(
                    self._t("paradox.has_warnings")
                    if field.name in warning_fields
                    else ""
                ),
            )

        self._populate_preview()

        self.issues.setRowCount(len(quality.issues))
        for row, issue in enumerate(quality.issues):
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
        if self.table is None:
            return
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
            elapsed, datetimes, representation = convert_time_values(sample)
            converted_text = []
            for position, elapsed_value in enumerate(elapsed):
                if datetimes is not None and not np.isnat(datetimes[position]):
                    converted_text.append(np.datetime_as_string(datetimes[position], unit="s"))
                else:
                    converted_text.append(_display(float(elapsed_value)))
        extra = 1 if converted_text is not None else 0
        self.preview.setColumnCount(len(field_names) + extra)
        headers = list(field_names)
        if converted_text is not None:
            headers.append(self._t("paradox.converted_time"))
        self.preview.setHorizontalHeaderLabels(headers)
        self.preview.setRowCount(len(row_indexes))
        for preview_row, source_row in enumerate(row_indexes):
            for column, field_name in enumerate(field_names):
                value = self.table.columns[field_name].values[source_row]
                self.preview.setItem(preview_row, column, QTableWidgetItem(_display(value)))
            if converted_text is not None:
                self.preview.setItem(
                    preview_row,
                    len(field_names),
                    QTableWidgetItem(converted_text[preview_row]),
                )
        depth_name = self.depth_field.currentData() or self._t("paradox.not_selected")
        selected_time = time_name or self._t("paradox.not_selected")
        self.preview_summary.setText(
            self._t(
                "paradox.preview_summary",
                depth=depth_name,
                time=selected_time,
                rows=len(row_indexes),
            )
        )
        self.preview.resizeColumnsToContents()

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
            checked = self.channels.item(row, 0).checkState() == Qt.CheckState.Checked
            mappings.append(
                ChannelMapping(
                    source_name=self.channels.item(row, 1).text(),
                    mnemonic=self.channels.item(row, 2).text().strip(),
                    description=self.channels.item(row, 3).text().strip(),
                    unit=self.channels.item(row, 4).text().strip(),
                    import_enabled=checked,
                )
            )
        return ParadoxImportPlan(
            classification=self.classification.currentData(),
            depth_field=self.depth_field.currentData(),
            time_field=self.time_field.currentData(),
            active_role=self.active_role.currentData(),
            null_value=self.null_value.value(),
            sort_by_index=self.sort_index.isChecked(),
            mappings=tuple(mappings),
            profile_name=self._profile_name,
            duplicate_depth_policy=self.duplicate_policy.currentData(),
            drop_empty_channels=self.drop_empty_channels.isChecked(),
            language=self.localizer.language.value,
        )

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
        self._start_import(plan, action)

    def _start_import(self, plan: ParadoxImportPlan, action: str) -> None:
        assert self.table is not None
        self._pending_action = action
        self.open_button.setEnabled(False)
        self.save_las_button.setEnabled(False)
        self.profile_button.setEnabled(False)
        self.load_profile_button.setEnabled(False)
        self.load_dictionary_button.setEnabled(False)
        self.save_dictionary_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status.setText(self._t("paradox.phase_create"))
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
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.accept()

    @Slot(str)
    def _on_import_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status.setText(message)
        self.open_button.setEnabled(self.table is not None)
        self.save_las_button.setEnabled(self.table is not None)
        self.profile_button.setEnabled(self.table is not None)
        self.load_profile_button.setEnabled(self.table is not None)
        self.load_dictionary_button.setEnabled(self.table is not None)
        self.save_dictionary_button.setEnabled(self.table is not None)
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
            self.channels.item(row, 0).setCheckState(
                Qt.CheckState.Checked if mapping.import_enabled else Qt.CheckState.Unchecked
            )
            self.channels.item(row, 2).setText(mapping.mnemonic)
            self.channels.item(row, 3).setText(mapping.description)
            self.channels.item(row, 4).setText(mapping.unit)

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
            self.channels.item(row, 2).setText(definition.mnemonic)
            self.channels.item(row, 3).setText(definition.localized_name(language_code))
            self.channels.item(row, 4).setText(definition.unit)
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
            source = self.channels.item(row, 1).text().strip()
            mnemonic = self.channels.item(row, 2).text().strip() or source
            description = self.channels.item(row, 3).text().strip() or f"Source channel {source}"
            unit = self.channels.item(row, 4).text().strip()
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
        if self._cancel_pending:
            return
        self._cancel_pending = True
        if self._worker is not None:
            self._worker.cancel_requested = True
        if self._import_worker is not None:
            self._import_worker.cancel_requested = True
        if self._thread is not None and self._thread.isRunning():
            self.status.setText(self._t("paradox.cancelling"))
            self._thread.finished.connect(self._reject_after_worker)
            return
        super().reject()

    @Slot()
    def _reject_after_worker(self) -> None:
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
