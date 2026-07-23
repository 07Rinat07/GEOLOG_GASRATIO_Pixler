from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset, IndexRole, IndexType
from geoworkbench.services.import_jobs import ImportSourceKind
from geoworkbench.services.import_review import (
    DatasetImportReview,
    ImportChannelOverride,
    ImportReviewController,
    ImportReviewPlan,
    ImportReviewSeverity,
    ImportReviewValidationError,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.uom_dictionary import QuantityClass


class ImportReviewDialog(QDialog):
    """Interactive adapter for the headless Import Review transaction."""

    def __init__(
        self,
        dataset: Dataset,
        source: Path,
        source_kind: ImportSourceKind,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        controller: ImportReviewController | None = None,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.source = source
        self.source_kind = source_kind
        self.localizer = Localizer.create(language)
        self.controller = controller or ImportReviewController()
        self._initial_plan = self.controller.initial_plan(dataset)
        self._channel_overrides = {
            item.curve_id: item for item in self._initial_plan.channels
        }
        self._updating = False
        self.accepted_dataset: Dataset | None = None
        self.setWindowTitle(self._t("import_review.title", file=source.name))
        self.resize(1180, 760)

        root = QVBoxLayout(self)
        root.addWidget(self._build_source_header())
        root.addWidget(self._build_index_group())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_channel_table())
        splitter.addWidget(self._build_channel_editor())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        root.addWidget(self._build_qc_group())
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._accept_review)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("import_review.accept")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        root.addWidget(self.buttons)

        self._load_initial_state()
        self._refresh_review()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _build_source_header(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        source_label = self._t(f"import.source_{self.source_kind.value}")
        self.source_summary = QLabel(
            self._t(
                "import_review.source_summary",
                source=source_label,
                file=self.source.name,
                dataset=self.dataset.name,
                rows=len(self.dataset.active_index.values),
                channels=len(self.dataset.curves),
            )
        )
        self.source_summary.setWordWrap(True)
        layout.addWidget(self.source_summary, 1)
        return panel

    def _build_index_group(self) -> QGroupBox:
        group = QGroupBox(self._t("import_review.index_group"))
        form = QFormLayout(group)
        self.active_index = QComboBox()
        self.index_mnemonic = QLineEdit()
        self.index_role = QComboBox()
        self.index_type = QComboBox()
        self.index_unit = QLineEdit()
        self.null_value = QLineEdit()
        self.null_value.setPlaceholderText(self._t("import_review.null_placeholder"))
        for role in IndexRole:
            self.index_role.addItem(self._t(f"import_review.index_role.{role.value}"), role)
        for index_type in IndexType:
            self.index_type.addItem(
                self._t(f"import_review.index_type.{index_type.value}"), index_type
            )
        form.addRow(self._t("import_review.active_index"), self.active_index)
        form.addRow(self._t("import_review.index_mnemonic"), self.index_mnemonic)
        form.addRow(self._t("import_review.index_role"), self.index_role)
        form.addRow(self._t("import_review.index_type"), self.index_type)
        form.addRow(self._t("import_review.index_unit"), self.index_unit)
        form.addRow(self._t("import_review.null_value"), self.null_value)
        note = QLabel(self._t("import_review.null_note"))
        note.setWordWrap(True)
        form.addRow(note)
        self.active_index.currentIndexChanged.connect(self._active_index_changed)
        self.index_mnemonic.editingFinished.connect(self._refresh_review)
        self.index_role.currentIndexChanged.connect(self._refresh_review)
        self.index_type.currentIndexChanged.connect(self._refresh_review)
        self.index_unit.editingFinished.connect(self._refresh_review)
        self.null_value.editingFinished.connect(self._refresh_review)
        return group

    def _build_channel_table(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self._t("import_review.channels"))
        layout.addWidget(title)
        self.channel_table = QTableWidget()
        self.channel_table.setColumnCount(9)
        self.channel_table.setHorizontalHeaderLabels(
            [
                self._t("import_review.column.include"),
                self._t("import_review.column.source"),
                self._t("import_review.column.canonical"),
                self._t("import_review.column.kind"),
                self._t("import_review.column.quantity"),
                self._t("import_review.column.uom"),
                self._t("import_review.column.confidence"),
                self._t("import_review.column.valid"),
                self._t("import_review.column.null"),
            ]
        )
        self.channel_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.channel_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.channel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channel_table.itemSelectionChanged.connect(self._selected_channel_changed)
        self.channel_table.itemChanged.connect(self._include_changed)
        layout.addWidget(self.channel_table)
        return panel

    def _build_channel_editor(self) -> QGroupBox:
        group = QGroupBox(self._t("import_review.channel_editor"))
        form = QFormLayout(group)
        self.channel_enabled = QCheckBox(self._t("import_review.channel_enabled"))
        self.channel_source = QLabel("—")
        self.channel_canonical = QLineEdit()
        self.channel_kind = QLineEdit()
        self.channel_quantity = QComboBox()
        self.channel_unit = QLineEdit()
        self.channel_unit_note = QLabel(self._t("import_review.unit_note"))
        self.channel_unit_note.setWordWrap(True)
        self.reset_channel = QPushButton(self._t("import_review.reset_channel"))
        for quantity in QuantityClass:
            self.channel_quantity.addItem(
                self._t(f"import_review.quantity.{quantity.value}"), quantity
            )
        form.addRow(self._t("import_review.source_mnemonic"), self.channel_source)
        form.addRow(self.channel_enabled)
        form.addRow(self._t("import_review.canonical_mnemonic"), self.channel_canonical)
        form.addRow(self._t("import_review.canonical_kind"), self.channel_kind)
        form.addRow(self._t("import_review.quantity_class"), self.channel_quantity)
        form.addRow(self._t("import_review.channel_unit"), self.channel_unit)
        form.addRow(self.channel_unit_note)
        form.addRow(self.reset_channel)
        self.channel_enabled.toggled.connect(self._store_channel_editor)
        self.channel_canonical.editingFinished.connect(self._store_channel_editor)
        self.channel_kind.editingFinished.connect(self._store_channel_editor)
        self.channel_quantity.currentIndexChanged.connect(self._store_channel_editor)
        self.channel_unit.editingFinished.connect(self._store_channel_editor)
        self.reset_channel.clicked.connect(self._reset_selected_channel)
        return group

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox(self._t("import_review.qc_group"))
        layout = QVBoxLayout(group)
        self.review_summary = QLabel()
        self.review_summary.setWordWrap(True)
        layout.addWidget(self.review_summary)
        self.issue_list = QListWidget()
        self.issue_list.setMaximumHeight(150)
        layout.addWidget(self.issue_list)
        return group

    def _load_initial_state(self) -> None:
        self._updating = True
        self.active_index.clear()
        for index in self.dataset.indexes.values():
            self.active_index.addItem(
                f"{index.mnemonic} — {index.role.value}/{index.index_type.value}",
                index.index_id,
            )
        selected = self.active_index.findData(self._initial_plan.active_index_id)
        self.active_index.setCurrentIndex(max(0, selected))
        self._load_index_fields(self._initial_plan.active_index_id)
        self._updating = False

    def _load_index_fields(self, index_id: str) -> None:
        index = self.dataset.indexes[index_id]
        self.index_mnemonic.setText(index.mnemonic)
        self._select_combo_data(self.index_role, index.role)
        self._select_combo_data(self.index_type, index.index_type)
        self.index_unit.setText(index.unit or "")

    def _active_index_changed(self) -> None:
        if self._updating:
            return
        index_id = self.active_index.currentData()
        if isinstance(index_id, str) and index_id in self.dataset.indexes:
            self._updating = True
            self._load_index_fields(index_id)
            self._updating = False
        self._refresh_review()

    def _current_plan(self) -> ImportReviewPlan:
        null_text = self.null_value.text().strip()
        null_value = float(null_text.replace(",", ".")) if null_text else None
        role = self.index_role.currentData()
        index_type = self.index_type.currentData()
        return ImportReviewPlan(
            active_index_id=str(self.active_index.currentData()),
            index_mnemonic=self.index_mnemonic.text().strip(),
            index_role=role if isinstance(role, IndexRole) else str(role),
            index_type=index_type if isinstance(index_type, IndexType) else str(index_type),
            index_unit=self.index_unit.text().strip() or None,
            null_value=null_value,
            channels=tuple(
                self._channel_overrides[curve_id]
                for curve_id in self.dataset.curves
            ),
        )

    def _refresh_review(self) -> None:
        if self._updating:
            return
        try:
            review = self.controller.preview(self.dataset, self._current_plan())
        except ValueError as exc:
            self.review_summary.setText(
                self._t("import_review.invalid_plan", error=str(exc))
            )
            self.issue_list.clear()
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self._populate_table(review)
        self._populate_issues(review)
        self.review_summary.setText(
            self._t(
                "import_review.summary",
                rows=review.row_count,
                channels=len(review.channels),
                valid_index=review.index_valid_count,
                null_index=review.index_null_count,
                duplicates=review.index_duplicate_count,
                gaps=review.index_gap_count,
                warnings=review.warning_count,
                errors=review.error_count,
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            review.error_count == 0
        )

    def _populate_table(self, review: DatasetImportReview) -> None:
        selected_id = self._selected_curve_id()
        self._updating = True
        self.channel_table.setRowCount(len(review.channels))
        for row, channel in enumerate(review.channels):
            override = self._channel_overrides[channel.curve_id]
            include = QTableWidgetItem()
            include.setData(Qt.ItemDataRole.UserRole, channel.curve_id)
            include.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            include.setCheckState(
                Qt.CheckState.Checked
                if override.import_enabled
                else Qt.CheckState.Unchecked
            )
            values = (
                channel.original_mnemonic,
                channel.canonical_mnemonic,
                channel.canonical_kind,
                channel.quantity_class,
                channel.source_uom or "—",
                f"{channel.confidence:.2f}",
                str(channel.valid_count),
                str(channel.null_count),
            )
            self.channel_table.setItem(row, 0, include)
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, channel.curve_id)
                self.channel_table.setItem(row, column, item)
            if selected_id == channel.curve_id:
                self.channel_table.selectRow(row)
        self.channel_table.resizeColumnsToContents()
        if selected_id is None and review.channels:
            self.channel_table.selectRow(0)
        self._updating = False
        self._selected_channel_changed()

    def _populate_issues(self, review: DatasetImportReview) -> None:
        self.issue_list.clear()
        for issue in review.issues:
            self.issue_list.addItem(
                self._issue_text(issue.severity, issue.code, issue.message)
            )
        for channel in review.channels:
            for issue in channel.issues:
                self.issue_list.addItem(
                    f"{channel.original_mnemonic}: "
                    + self._issue_text(issue.severity, issue.code, issue.message)
                )
        if self.issue_list.count() == 0:
            self.issue_list.addItem(self._t("import_review.no_issues"))

    def _issue_text(
        self,
        severity: ImportReviewSeverity,
        code: str,
        fallback: str,
    ) -> str:
        label = self._t(f"import_review.severity.{severity.value}")
        message = self.localizer.catalog.get(f"import_review.issue.{code}", fallback)
        return f"{label}: {message}"

    def _include_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != 0:
            return
        curve_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(curve_id, str):
            return
        override = self._channel_overrides[curve_id]
        self._channel_overrides[curve_id] = replace(
            override,
            import_enabled=item.checkState() == Qt.CheckState.Checked,
        )
        self._refresh_review()

    def _selected_curve_id(self) -> str | None:
        row = self.channel_table.currentRow()
        item = self.channel_table.item(row, 0) if row >= 0 else None
        curve_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return curve_id if isinstance(curve_id, str) else None

    def _selected_channel_changed(self) -> None:
        curve_id = self._selected_curve_id()
        enabled = curve_id is not None
        for widget in (
            self.channel_enabled,
            self.channel_canonical,
            self.channel_kind,
            self.channel_quantity,
            self.channel_unit,
            self.reset_channel,
        ):
            widget.setEnabled(enabled)
        if curve_id is None:
            self.channel_source.setText("—")
            return
        curve = self.dataset.curves[curve_id]
        override = self._channel_overrides[curve_id]
        self._updating = True
        self.channel_source.setText(curve.metadata.original_mnemonic)
        self.channel_enabled.setChecked(override.import_enabled)
        self.channel_canonical.setText(override.canonical_mnemonic or "")
        self.channel_kind.setText(override.canonical_kind or "")
        quantity = override.quantity_class or QuantityClass.UNKNOWN
        self._select_combo_data(self.channel_quantity, quantity)
        self.channel_unit.setText(override.unit or "")
        self._updating = False

    def _store_channel_editor(self) -> None:
        if self._updating:
            return
        curve_id = self._selected_curve_id()
        if curve_id is None:
            return
        quantity = self.channel_quantity.currentData()
        self._channel_overrides[curve_id] = ImportChannelOverride(
            curve_id=curve_id,
            import_enabled=self.channel_enabled.isChecked(),
            canonical_mnemonic=self.channel_canonical.text().strip() or None,
            canonical_kind=self.channel_kind.text().strip() or None,
            quantity_class=(
                quantity if isinstance(quantity, QuantityClass) else str(quantity)
            ),
            unit=self.channel_unit.text().strip() or None,
        )
        self._refresh_review()

    def _reset_selected_channel(self) -> None:
        curve_id = self._selected_curve_id()
        if curve_id is None:
            return
        initial = next(
            item for item in self._initial_plan.channels if item.curve_id == curve_id
        )
        self._channel_overrides[curve_id] = initial
        self._selected_channel_changed()
        self._refresh_review()

    def _accept_review(self) -> None:
        try:
            committed = self.controller.commit(self.dataset, self._current_plan())
        except ImportReviewValidationError as exc:
            self._populate_issues(exc.review)
            self.review_summary.setText(
                self._t("import_review.blocked", errors=exc.review.error_count)
            )
            return
        except ValueError as exc:
            self.review_summary.setText(
                self._t("import_review.invalid_plan", error=str(exc))
            )
            return
        self.accepted_dataset = committed.dataset
        self.accept()

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
