from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.data_inspector_controller import DataInspectorController
from geoworkbench.project.curve_metadata_controller import CurveMetadataController
from geoworkbench.project.header_editing_controller import (
    HeaderEditingController,
    HeaderSection,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class DataInspectorDialog(QDialog):
    def __init__(
        self,
        controller: DataInspectorController,
        header_controller: HeaderEditingController | None = None,
        curve_metadata_controller: CurveMetadataController | None = None,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.controller = controller
        self.header_controller = header_controller or HeaderEditingController(controller.session)
        self.curve_metadata_controller = curve_metadata_controller or CurveMetadataController(
            controller.session
        )
        self.setWindowTitle(self._t("data.window_title"))
        self.resize(980, 620)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.summary_text = QPlainTextEdit()
        self.summary_text.setObjectName("data-summary")
        self.summary_text.setReadOnly(True)
        self.tabs.addTab(self.summary_text, self._t("data.summary"))

        indexes_page = QWidget()
        indexes_layout = QVBoxLayout(indexes_page)
        self.index_table = QTableWidget(0, 11)
        self.index_table.setObjectName("data-indexes")
        self.index_table.setHorizontalHeaderLabels(
            [
                self._t("data.active"), self._t("data.mnemonic"), self._t("data.type"),
                self._t("data.role"), self._t("data.unit"), self._t("data.points"),
                self._t("data.start"), self._t("data.stop"), self._t("data.confidence"),
                self._t("data.date_format"), self._t("data.timezone"),
            ]
        )
        self.index_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.index_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.index_table.itemSelectionChanged.connect(self._show_index_details)
        indexes_layout.addWidget(self.index_table)
        actions = QHBoxLayout()
        activate_button = QPushButton(self._t("data.activate_index"))
        activate_button.clicked.connect(self._activate_selected_index)
        actions.addWidget(activate_button)
        actions.addStretch()
        indexes_layout.addLayout(actions)
        self.index_details = QPlainTextEdit()
        self.index_details.setObjectName("index-details")
        self.index_details.setReadOnly(True)
        self.index_details.setMaximumHeight(150)
        indexes_layout.addWidget(QLabel(self._t("data.evidence_warnings")))
        indexes_layout.addWidget(self.index_details)
        self.tabs.addTab(indexes_page, self._t("data.indexes"))

        curves_page = QWidget()
        curves_layout = QVBoxLayout(curves_page)
        self.curve_table = QTableWidget(0, 6)
        self.curve_table.setObjectName("data-curves")
        self.curve_table.setHorizontalHeaderLabels(
            [self._t("data.mnemonic"), self._t("data.unit"), self._t("data.description"),
             self._t("data.points"), self._t("data.missing"), "Curve ID"]
        )
        self.curve_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.curve_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.curve_table.itemSelectionChanged.connect(self._load_curve_metadata)
        curves_layout.addWidget(self.curve_table)
        curve_editor = QHBoxLayout()
        self.curve_mnemonic = QLineEdit()
        self.curve_mnemonic.setObjectName("curve-mnemonic")
        self.curve_mnemonic.setPlaceholderText(self._t("data.mnemonic"))
        self.curve_unit = QLineEdit()
        self.curve_unit.setObjectName("curve-unit")
        self.curve_unit.setPlaceholderText(self._t("data.unit"))
        self.curve_description = QLineEdit()
        self.curve_description.setObjectName("curve-description")
        self.curve_description.setPlaceholderText(self._t("data.description"))
        curve_editor.addWidget(self.curve_mnemonic)
        curve_editor.addWidget(self.curve_unit)
        curve_editor.addWidget(self.curve_description, 1)
        curves_layout.addLayout(curve_editor)
        curve_actions = QHBoxLayout()
        for label, handler in (
            (self._t("data.add_curve"), self._add_curve),
            (self._t("common.update"), self._update_curve_metadata),
            (self._t("data.remove_curve"), self._remove_curve),
            (self._t("common.undo"), self._undo_curve_metadata),
            (self._t("common.redo"), self._redo_curve_metadata),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            curve_actions.addWidget(button)
        curve_actions.addStretch()
        curves_layout.addLayout(curve_actions)
        self.tabs.addTab(curves_page, self._t("data.curves"))

        self.issue_table = QTableWidget(0, 3)
        self.issue_table.setObjectName("import-issues")
        self.issue_table.setHorizontalHeaderLabels(
            [self._t("data.severity"), self._t("data.code"), self._t("data.message")]
        )
        self.tabs.addTab(self.issue_table, self._t("data.import_diagnostics"))

        self.source_text = QPlainTextEdit()
        self.source_text.setObjectName("las-source-profile")
        self.source_text.setReadOnly(True)
        self.tabs.addTab(self.source_text, self._t("data.las_source"))

        header_page = QWidget()
        header_layout = QVBoxLayout(header_page)
        section_row = QHBoxLayout()
        section_row.addWidget(QLabel(self._t("data.section")))
        self.header_section = QComboBox()
        self.header_section.setObjectName("header-section")
        self.header_section.addItem("WELL", HeaderSection.WELL)
        self.header_section.addItem("PARAMETER", HeaderSection.PARAMETER)
        self.header_section.addItem("VERSION", HeaderSection.VERSION)
        self.header_section.currentIndexChanged.connect(self._refresh_header)
        section_row.addWidget(self.header_section)
        section_row.addStretch()
        header_layout.addLayout(section_row)
        self.depth_header_summary = QPlainTextEdit()
        self.depth_header_summary.setObjectName("depth-header-summary")
        self.depth_header_summary.setReadOnly(True)
        self.depth_header_summary.setMaximumHeight(125)
        header_layout.addWidget(self.depth_header_summary)
        depth_actions = QHBoxLayout()
        synchronize_button = QPushButton(self._t("data.sync_depth"))
        synchronize_button.setObjectName("synchronize-depth-header")
        synchronize_button.clicked.connect(self._synchronize_depth_header)
        depth_actions.addWidget(synchronize_button)
        depth_actions.addWidget(QLabel("NULL"))
        self.null_value = QDoubleSpinBox()
        self.null_value.setObjectName("header-null-value")
        self.null_value.setDecimals(8)
        self.null_value.setRange(-1e100, 1e100)
        depth_actions.addWidget(self.null_value)
        null_button = QPushButton(self._t("data.apply_null"))
        null_button.setObjectName("apply-header-null")
        null_button.clicked.connect(self._set_null_value)
        depth_actions.addWidget(null_button)
        depth_actions.addStretch()
        header_layout.addLayout(depth_actions)
        self.header_table = QTableWidget(0, 3)
        self.header_table.setObjectName("las-header")
        self.header_table.setHorizontalHeaderLabels(
            [self._t("data.mnemonic"), self._t("data.value"), self._t("data.control")]
        )
        self.header_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.header_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.header_table.itemSelectionChanged.connect(self._load_header_entry)
        header_layout.addWidget(self.header_table)
        editor_row = QHBoxLayout()
        self.header_mnemonic = QLineEdit()
        self.header_mnemonic.setObjectName("header-mnemonic")
        self.header_mnemonic.setPlaceholderText(self._t("data.mnemonic"))
        self.header_value = QLineEdit()
        self.header_value.setObjectName("header-value")
        self.header_value.setPlaceholderText(self._t("data.value"))
        editor_row.addWidget(self.header_mnemonic)
        editor_row.addWidget(self.header_value, 1)
        header_layout.addLayout(editor_row)
        header_actions = QHBoxLayout()
        for label, handler in (
            (self._t("common.add"), self._add_header_entry),
            (self._t("common.update"), self._update_header_entry),
            (self._t("common.remove"), self._remove_header_entry),
            (self._t("common.undo"), self._undo_header),
            (self._t("common.redo"), self._redo_header),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            header_actions.addWidget(button)
        header_actions.addStretch()
        header_layout.addLayout(header_actions)
        header_layout.addWidget(
            QLabel(
                self._t("data.header_hint")
            )
        )
        self.tabs.addTab(header_page, self._t("data.las_header"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh(self) -> None:
        summary = self.controller.summary()
        headers = "\n".join(f"  {key}: {value}" for key, value in summary.headers) or "  —"
        self.summary_text.setPlainText(
            f"{self._t('data.well')}: {summary.well_name}\n"
            f"Dataset: {summary.dataset_name}\n"
            f"{self._t('data.source')}: {summary.source_path or '—'}\n"
            f"{self._t('data.samples')}: {summary.sample_count}\n"
            f"{self._t('data.curves')}: {summary.curve_count}\n"
            f"{self._t('data.indexes')}: {summary.index_count}\n"
            f"{self._t('data.active_index')}: {summary.active_index_id}\n\n"
            f"{self._t('data.well_headers')}:\n{headers}"
        )

        indexes = self.controller.indexes()
        self.index_table.setRowCount(len(indexes))
        for row, index in enumerate(indexes):
            index_values = (
                "●" if index.active else "",
                index.mnemonic,
                index.index_type.value,
                index.role.value,
                index.unit or "—",
                str(index.sample_count),
                index.start or "—",
                index.stop or "—",
                f"{index.confidence:.0%}",
                index.datetime_format or "—",
                index.timezone or self._t("common.unset"),
            )
            for column, value in enumerate(index_values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, index.index_id)
                self.index_table.setItem(row, column, item)
        self.index_table.resizeColumnsToContents()

        curves = self.controller.curves()
        self.curve_table.setRowCount(len(curves))
        for row, curve in enumerate(curves):
            curve_values = (
                curve.mnemonic,
                curve.unit or "—",
                curve.description or "—",
                str(curve.sample_count),
                str(curve.missing_count),
                curve.curve_id,
            )
            for column, value in enumerate(curve_values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, curve.curve_id)
                self.curve_table.setItem(row, column, item)
        self.curve_table.resizeColumnsToContents()

        issues = self.controller.import_issues()
        self.issue_table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for column, value in enumerate((issue.severity.value, issue.code, issue.message)):
                self.issue_table.setItem(row, column, QTableWidgetItem(value))
        self.issue_table.resizeColumnsToContents()
        source = self.controller.source_inspection()
        if source is None:
            self.source_text.setPlainText(self._t("data.no_las_report"))
        else:
            sections = ", ".join(source.sections) or "—"
            self.source_text.setPlainText(
                f"{self._t('data.source_path')}: {source.path}\n"
                f"{self._t('data.las_version')}: {source.version or '—'}\n"
                f"WRAP: {source.wrap or '—'}\n"
                f"NULL: {self._number(source.null_value)}\n"
                f"{self._t('data.encoding')}: {source.encoding}\n"
                f"{self._t('data.newlines')}: {source.newline_style}\n"
                f"{self._t('data.size')}: {source.size_bytes} {self._t('data.bytes')}\n"
                f"SHA-256: {source.sha256}\n"
                f"{self._t('data.sections')}: {sections}\n"
                f"{self._t('data.lossless_artifact')}: {source.artifact_status}\n"
                f"{self._t('data.diagnostics')}: "
                f"info={source.info_count}, warning={source.warning_count}, error={source.error_count}"
            )
        self._refresh_header()

    def _current_header_section(self) -> HeaderSection:
        value = self.header_section.currentData()
        return value if isinstance(value, HeaderSection) else HeaderSection.WELL

    def _selected_curve_id(self) -> str | None:
        row = self.curve_table.currentRow()
        item = self.curve_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, str) else None

    def _load_curve_metadata(self) -> None:
        row = self.curve_table.currentRow()
        mnemonic = self.curve_table.item(row, 0) if row >= 0 else None
        unit = self.curve_table.item(row, 1) if row >= 0 else None
        description = self.curve_table.item(row, 2) if row >= 0 else None
        self.curve_mnemonic.setText(mnemonic.text() if mnemonic is not None else "")
        self.curve_unit.setText("" if unit is None or unit.text() == "—" else unit.text())
        self.curve_description.setText(
            "" if description is None or description.text() == "—" else description.text()
        )

    def _update_curve_metadata(self) -> None:
        curve_id = self._selected_curve_id()
        if curve_id is None:
            QMessageBox.information(
                self, self._t("data.curves"), self._t("data.select_curve")
            )
            return
        self._run_curve_metadata_action(
            lambda: self.curve_metadata_controller.update(
                curve_id,
                mnemonic=self.curve_mnemonic.text(),
                unit=self.curve_unit.text(),
                description=self.curve_description.text(),
            )
        )

    def _add_curve(self) -> None:
        self._run_curve_metadata_action(
            lambda: self.curve_metadata_controller.create(
                mnemonic=self.curve_mnemonic.text(),
                unit=self.curve_unit.text(),
                description=self.curve_description.text(),
            )
        )

    def _remove_curve(self) -> None:
        curve_id = self._selected_curve_id()
        if curve_id is None:
            QMessageBox.information(
                self, self._t("data.curves"), self._t("data.select_curve")
            )
            return
        answer = QMessageBox.question(
            self,
            self._t("data.remove_curve_title"),
            self._t("data.remove_curve_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        self._run_curve_metadata_action(
            lambda: self.curve_metadata_controller.remove(curve_id)
        )

    def _undo_curve_metadata(self) -> None:
        self._run_curve_metadata_action(self.curve_metadata_controller.undo)

    def _redo_curve_metadata(self) -> None:
        self._run_curve_metadata_action(self.curve_metadata_controller.redo)

    def _run_curve_metadata_action(self, action) -> None:
        try:
            action()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("data.curves"), str(exc))
            return
        self._refresh()

    def _refresh_header(self) -> None:
        summary = self.header_controller.depth_summary()
        issues = "\n".join(f"• {issue}" for issue in summary.issues) or self._t("data.no_issues")
        self.depth_header_summary.setPlainText(
            f"{self._t('data.depth_calculation')}: "
            f"STRT={self._number(summary.calculated_start)}, "
            f"STOP={self._number(summary.calculated_stop)}, "
            f"STEP={self._number(summary.calculated_step)}\n"
            f"{self._t('data.direction')}: "
            f"{self._t(f'depth.direction.{summary.direction.value}')}; "
            f"{self._t('data.uniform_step')}: "
            f"{self._t('common.yes') if summary.uniform else self._t('common.no')}\n{issues}"
        )
        if summary.null_value is not None:
            self.null_value.setValue(summary.null_value)
        else:
            self.null_value.setValue(-9999.25)
        entries = self.header_controller.entries(self._current_header_section())
        self.header_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.header_table.setItem(row, 0, QTableWidgetItem(entry.mnemonic))
            self.header_table.setItem(row, 1, QTableWidgetItem(entry.value))
            self.header_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    self._t("data.protected") if entry.protected else self._t("data.editor")
                ),
            )
        self.header_table.resizeColumnsToContents()

    def _load_header_entry(self) -> None:
        row = self.header_table.currentRow()
        mnemonic = self.header_table.item(row, 0) if row >= 0 else None
        value = self.header_table.item(row, 1) if row >= 0 else None
        self.header_mnemonic.setText(mnemonic.text() if mnemonic is not None else "")
        self.header_value.setText(value.text() if value is not None else "")

    def _add_header_entry(self) -> None:
        self._run_header_action(
            lambda: self.header_controller.add(
                self._current_header_section(),
                self.header_mnemonic.text(),
                self.header_value.text(),
            )
        )

    def _update_header_entry(self) -> None:
        row = self.header_table.currentRow()
        original = self.header_table.item(row, 0) if row >= 0 else None
        if original is None:
            QMessageBox.information(
                self, self._t("data.las_header"), self._t("data.select_entry")
            )
            return
        self._run_header_action(
            lambda: self.header_controller.update(
                self._current_header_section(),
                original.text(),
                self.header_mnemonic.text(),
                self.header_value.text(),
            )
        )

    def _remove_header_entry(self) -> None:
        row = self.header_table.currentRow()
        item = self.header_table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(
                self, self._t("data.las_header"), self._t("data.select_entry")
            )
            return
        self._run_header_action(
            lambda: self.header_controller.remove(self._current_header_section(), item.text())
        )

    def _undo_header(self) -> None:
        self._run_header_action(self.header_controller.undo)

    def _redo_header(self) -> None:
        self._run_header_action(self.header_controller.redo)

    def _synchronize_depth_header(self) -> None:
        self._run_header_action(self.header_controller.synchronize_depth_fields)

    def _set_null_value(self) -> None:
        self._run_header_action(
            lambda: self.header_controller.set_null_value(self.null_value.value())
        )

    def _run_header_action(self, action) -> None:
        try:
            action()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("data.las_header"), str(exc))
            return
        self._refresh()

    @staticmethod
    def _number(value: float | None) -> str:
        return "—" if value is None else f"{value:.10g}"

    def _selected_index_id(self) -> str | None:
        row = self.index_table.currentRow()
        item = self.index_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, str) else None

    def _show_index_details(self) -> None:
        index_id = self._selected_index_id()
        inspection = next(
            (item for item in self.controller.indexes() if item.index_id == index_id),
            None,
        )
        if inspection is None:
            self.index_details.clear()
            return
        evidence = "\n".join(f"• {item}" for item in inspection.evidence) or self._t("data.none_bullet")
        warnings = "\n".join(f"• {item}" for item in inspection.warnings) or self._t("data.none_bullet")
        self.index_details.setPlainText(
            f"{self._t('data.evidence')}:\n{evidence}\n\n"
            f"{self._t('data.warnings')}:\n{warnings}"
        )

    def _activate_selected_index(self) -> None:
        index_id = self._selected_index_id()
        if index_id is None:
            QMessageBox.information(
                self, self._t("data.indexes"), self._t("data.select_index")
            )
            return
        try:
            self.controller.set_active_index(index_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("data.indexes"), str(exc))
            return
        self._refresh()
