from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.witsml import (
    WitsmlChannelSetData,
    WitsmlDataError,
    WitsmlDataPackage,
    read_witsml_channel_sets,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.uom_dictionary import QuantityClass
from geoworkbench.services.witsml_import_review import (
    WitsmlChannelOverride,
    WitsmlImportCommit,
    WitsmlImportReviewController,
    WitsmlImportReviewPlan,
    WitsmlImportValidationError,
)


class WitsmlImportDialog(QDialog):
    """Interactive WITSML ChannelSet data-array review and atomic commit."""

    def __init__(
        self,
        source: str | Path | None = None,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        package: WitsmlDataPackage | None = None,
    ) -> None:
        super().__init__(parent)
        if source is None and package is None:
            raise ValueError("source or package is required")
        if source is not None:
            self.source = Path(source)
        else:
            assert package is not None
            self.source = package.source
        self.localizer = Localizer.create(language)
        self.controller = WitsmlImportReviewController()
        self.package: WitsmlDataPackage | None = package
        self.plan: WitsmlImportReviewPlan | None = None
        self.accepted_commit: WitsmlImportCommit | None = None
        self.failure: Exception | None = None
        self._updating = False

        self.setWindowTitle(self._t("witsml_import.title"))
        self.resize(1280, 820)
        root = QVBoxLayout(self)

        self.summary = QLabel(self._t("witsml_import.loading", file=self.source.name), self)
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        form = QFormLayout()
        self.channel_set_combo = QComboBox(self)
        self.dataset_name = QLineEdit(self)
        self.index_combo = QComboBox(self)
        self.sort_index = QCheckBox(self._t("witsml_import.sort_index"), self)
        self.drop_invalid = QCheckBox(self._t("witsml_import.drop_invalid"), self)
        self.drop_invalid.setChecked(True)
        form.addRow(self._t("witsml_import.channel_set"), self.channel_set_combo)
        form.addRow(self._t("witsml_import.dataset_name"), self.dataset_name)
        form.addRow(self._t("witsml_import.active_index"), self.index_combo)
        form.addRow("", self.sort_index)
        form.addRow("", self.drop_invalid)
        root.addLayout(form)

        self.table = QTableWidget(self)
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("witsml_import.column_enabled"),
                self._t("witsml_import.column_source"),
                self._t("witsml_import.column_type"),
                self._t("witsml_import.column_source_uom"),
                self._t("witsml_import.column_canonical"),
                self._t("witsml_import.column_quantity"),
                self._t("witsml_import.column_target_uom"),
                self._t("witsml_import.column_counts"),
                self._t("witsml_import.column_status"),
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        for column in (0, 1, 2, 3, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (4, 5, 6, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.diagnostics = QPlainTextEdit(self)
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumBlockCount(5_000)
        root.addWidget(self.diagnostics, 0)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self._accept_import)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.channel_set_combo.currentIndexChanged.connect(self._channel_set_changed)
        self.index_combo.currentIndexChanged.connect(self._index_changed)
        self.dataset_name.textChanged.connect(self._preview)
        self.sort_index.toggled.connect(self._preview)
        self.drop_invalid.toggled.connect(self._preview)
        if package is None:
            self._load()
        else:
            self._populate_package(package)

    @property
    def accepted_dataset(self):
        return self.accepted_commit.dataset if self.accepted_commit is not None else None

    def _load(self) -> None:
        try:
            package = read_witsml_channel_sets(self.source)
        except WitsmlDataError as exc:
            self.failure = exc
            self.summary.setText(self._t("witsml_import.failed", error=str(exc)))
            self.diagnostics.setPlainText(str(exc))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self._populate_package(package)

    def _populate_package(self, package: WitsmlDataPackage) -> None:
        self.package = package
        self._updating = True
        for channel_set in package.channel_sets:
            label = self._t(
                "witsml_import.channel_set_label",
                title=channel_set.title,
                rows=len(channel_set.rows),
                channels=len(channel_set.channels),
                indexes=len(channel_set.indexes),
            )
            self.channel_set_combo.addItem(label, channel_set.key)
        self._updating = False
        self.summary.setText(
            self._t(
                "witsml_import.summary",
                file=self.source.name,
                sets=len(package.channel_sets),
                diagnostics=len(package.issues),
            )
        )
        self._channel_set_changed(0)

    def _current_channel_set(self) -> WitsmlChannelSetData | None:
        if self.package is None:
            return None
        key = self.channel_set_combo.currentData()
        return next((item for item in self.package.channel_sets if item.key == key), None)

    def _channel_set_changed(self, _index: int) -> None:
        if self._updating:
            return
        channel_set = self._current_channel_set()
        if channel_set is None:
            return
        self.plan = self.controller.initial_plan(channel_set)
        self._updating = True
        self.dataset_name.setText(self.plan.dataset_name)
        self.index_combo.clear()
        for index in channel_set.indexes:
            self.index_combo.addItem(
                f"{index.mnemonic} — {index.index_type} [{index.uom or '—'}]",
                index.key,
            )
        selected = self.index_combo.findData(self.plan.active_index_key)
        self.index_combo.setCurrentIndex(max(selected, 0))
        self.sort_index.setChecked(self.plan.sort_by_index)
        self.drop_invalid.setChecked(self.plan.drop_invalid_index_rows)
        self._updating = False
        self._rebuild_table(channel_set)
        self._preview()

    def _index_changed(self, _index: int) -> None:
        if self._updating or self.plan is None:
            return
        channel_set = self._current_channel_set()
        key = self.index_combo.currentData()
        if channel_set is None or not isinstance(key, str):
            return
        try:
            self.plan = self.controller.plan_for_index(channel_set, self._collect_plan(), key)
        except (ValueError, TypeError):
            return
        self._updating = True
        self.sort_index.setChecked(self.plan.sort_by_index)
        self._updating = False
        self._preview()

    def _rebuild_table(self, channel_set: WitsmlChannelSetData) -> None:
        assert self.plan is not None
        self.table.setRowCount(len(channel_set.channels))
        overrides = {item.channel_key: item for item in self.plan.channels}
        for row, channel in enumerate(channel_set.channels):
            override = overrides[channel.key]
            enabled = QCheckBox(self.table)
            enabled.setChecked(override.import_enabled)
            enabled.stateChanged.connect(self._preview)
            enabled.setProperty("channelKey", channel.key)
            self.table.setCellWidget(row, 0, enabled)

            source_item = QTableWidgetItem(channel.mnemonic)
            source_item.setData(Qt.ItemDataRole.UserRole, channel.key)
            source_item.setToolTip(channel.title or channel.description or "")
            self.table.setItem(row, 1, source_item)
            self.table.setItem(row, 2, QTableWidgetItem(channel.data_type))
            self.table.setItem(row, 3, QTableWidgetItem(channel.uom or "—"))

            canonical = QLineEdit(override.canonical_mnemonic or channel.mnemonic, self.table)
            canonical.textChanged.connect(self._preview)
            self.table.setCellWidget(row, 4, canonical)

            quantity = QComboBox(self.table)
            for item in QuantityClass:
                quantity.addItem(item.value, item)
            selected = quantity.findData(override.quantity_class)
            quantity.setCurrentIndex(max(selected, 0))
            quantity.currentIndexChanged.connect(self._preview)
            self.table.setCellWidget(row, 5, quantity)

            target_uom = QLineEdit(override.canonical_uom or channel.uom or "", self.table)
            target_uom.textChanged.connect(self._preview)
            self.table.setCellWidget(row, 6, target_uom)
            self.table.setItem(row, 7, QTableWidgetItem("—"))
            self.table.setItem(row, 8, QTableWidgetItem("—"))
        self.table.resizeRowsToContents()

    def _collect_plan(self) -> WitsmlImportReviewPlan:
        channel_set = self._current_channel_set()
        if channel_set is None:
            raise RuntimeError("No WITSML ChannelSet is selected")
        return self._collect_plan_without_recursive_preview(channel_set)

    def _preview(self, *_args: object) -> None:
        if self._updating or self.plan is None:
            return
        channel_set = self._current_channel_set()
        if channel_set is None:
            return
        try:
            plan = self._collect_plan_without_recursive_preview(channel_set)
            review = self.controller.preview(channel_set, plan)
        except Exception as exc:  # noqa: BLE001 - present draft errors in the dialog
            self.diagnostics.setPlainText(str(exc))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self.plan = plan
        review_by_key = {item.channel_key: item for item in review.channels}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 1)
            key = key_item.data(Qt.ItemDataRole.UserRole) if key_item is not None else None
            if not isinstance(key, str):
                continue
            item = review_by_key.get(key)
            if item is None:
                continue
            counts_item = self.table.item(row, 7)
            if counts_item is not None:
                counts_item.setText(
                    f"{item.valid_count}/{item.null_count}/{item.invalid_count}"
                )
            messages = "; ".join(issue.message for issue in item.issues)
            status_item = self.table.item(row, 8)
            if status_item is not None:
                status_item.setText(messages or self._t("witsml_import.ok"))
        lines = [
            self._t(
                "witsml_import.review_summary",
                rows=review.import_row_count,
                skipped=review.skipped_row_count,
                warnings=review.warning_count,
                errors=review.error_count,
            )
        ]
        lines.extend(
            f"[{issue.severity.value.upper()}] {issue.message}" for issue in review.issues
        )
        for channel in review.channels:
            lines.extend(
                f"[{issue.severity.value.upper()}] {channel.mnemonic}: {issue.message}"
                for issue in channel.issues
            )
        self.diagnostics.setPlainText("\n".join(lines))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(review.error_count == 0)

    def _collect_plan_without_recursive_preview(
        self,
        channel_set: WitsmlChannelSetData,
    ) -> WitsmlImportReviewPlan:
        assert self.plan is not None
        automatic = {
            item.channel_key: item
            for item in self.controller.preview(channel_set, self.plan).channels
        }
        overrides: list[WitsmlChannelOverride] = []
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 1)
            key = key_item.data(Qt.ItemDataRole.UserRole) if key_item is not None else None
            if not isinstance(key, str):
                continue
            enabled = self.table.cellWidget(row, 0)
            canonical = self.table.cellWidget(row, 4)
            quantity = self.table.cellWidget(row, 5)
            target_uom = self.table.cellWidget(row, 6)
            baseline = automatic[key]
            overrides.append(
                WitsmlChannelOverride(
                    channel_key=key,
                    import_enabled=isinstance(enabled, QCheckBox) and enabled.isChecked(),
                    canonical_mnemonic=(canonical.text() if isinstance(canonical, QLineEdit) else baseline.canonical_mnemonic),
                    canonical_kind=baseline.canonical_kind,
                    quantity_class=(quantity.currentData() if isinstance(quantity, QComboBox) else baseline.quantity_class),
                    canonical_uom=(target_uom.text() if isinstance(target_uom, QLineEdit) else baseline.canonical_uom),
                )
            )
        return replace(
            self.plan,
            dataset_name=self.dataset_name.text().strip() or self.plan.dataset_name,
            active_index_key=str(self.index_combo.currentData() or self.plan.active_index_key),
            channels=tuple(overrides),
            sort_by_index=self.sort_index.isChecked(),
            drop_invalid_index_rows=self.drop_invalid.isChecked(),
        )

    def _accept_import(self) -> None:
        channel_set = self._current_channel_set()
        if channel_set is None or self.plan is None:
            return
        try:
            plan = self._collect_plan_without_recursive_preview(channel_set)
            self.plan = plan
            self.accepted_commit = self.controller.commit(channel_set, plan)
        except WitsmlImportValidationError as exc:
            self.failure = exc
            QMessageBox.critical(self, self._t("witsml_import.title"), str(exc))
            self._preview()
            return
        except Exception as exc:  # noqa: BLE001 - keep project unchanged on any failure
            self.failure = exc
            QMessageBox.critical(self, self._t("witsml_import.title"), str(exc))
            return
        self.accept()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
