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
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.acquisition.wits0 import Wits0Profile
from geoworkbench.domain.models import IndexType
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.uom_dictionary import QuantityClass
from geoworkbench.services.wits0_import_review import (
    Wits0ChannelKey,
    Wits0CustomProfile,
    Wits0DiscoverySnapshot,
    Wits0ImportReview,
    Wits0ImportReviewCommit,
    Wits0ImportReviewController,
    Wits0ImportReviewValidationError,
    next_wits0_custom_profile_revision,
)


class Wits0ImportReviewDialog(QDialog):
    """Interactive review of an immutable WITS0 discovery snapshot."""

    def __init__(
        self,
        snapshot: Wits0DiscoverySnapshot,
        profile: Wits0Profile,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        controller: Wits0ImportReviewController | None = None,
        custom_profile: Wits0CustomProfile | None = None,
        dataset_name: str = "WITS0 Live",
        profile_directory: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.snapshot = snapshot
        self.profile = profile
        self.controller = controller or Wits0ImportReviewController()
        self.plan = self.controller.initial_plan(
            snapshot,
            dataset_name=dataset_name,
            custom_profile=custom_profile,
        )
        self.commit_result: Wits0ImportReviewCommit | None = None
        self.profile_directory = Path(profile_directory) if profile_directory is not None else None
        self._updating = False

        self.setWindowTitle(self._t("wits0_review.title"))
        self.resize(1280, 820)
        root = QVBoxLayout(self)
        root.addWidget(self._build_summary_group())
        root.addWidget(self._build_index_group())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_channel_table())
        splitter.addWidget(self._build_channel_editor())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        root.addWidget(self._build_qc_group())

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self._accept_review)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._load_plan()
        self._refresh_review()

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0_review.discovery_group"), self)
        layout = QGridLayout(group)
        values = (
            ("wits0_review.profile", f"{self.profile.title} v{self.profile.version}"),
            ("wits0_review.frames", str(self.snapshot.frame_count)),
            ("wits0_review.channels", str(len(self.snapshot.channels))),
            ("wits0_review.fingerprint", self.snapshot.fingerprint),
        )
        for row, (key, text) in enumerate(values):
            value = QLabel(text, group)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setToolTip(text)
            layout.addWidget(QLabel(self._t(key), group), row, 0)
            layout.addWidget(value, row, 1)
        layout.setColumnStretch(1, 1)
        return group

    def _build_index_group(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0_review.schema_group"), self)
        layout = QGridLayout(group)
        self.dataset_name = QLineEdit(group)
        self.index_candidate = QComboBox(group)
        for candidate in self.controller.index_candidates(self.snapshot):
            label = self._t(
                "wits0_review.index_candidate",
                mnemonic=candidate.mnemonic,
                role=candidate.role.value,
                source=candidate.candidate_id,
                count=candidate.observation_count,
            )
            self.index_candidate.addItem(label, candidate.candidate_id)
        self.index_mnemonic = QLineEdit(group)
        self.index_type = QComboBox(group)
        for item in IndexType:
            self.index_type.addItem(item.value, item)
        self.index_unit = QLineEdit(group)
        self.timezone = QLineEdit(group)
        self.custom_profile_id = QLineEdit(group)
        self.custom_profile_revision = QLabel("1", group)

        rows = (
            ("wits0_review.dataset_name", self.dataset_name),
            ("wits0_review.active_index", self.index_candidate),
            ("wits0_review.index_mnemonic", self.index_mnemonic),
            ("wits0_review.index_type", self.index_type),
            ("wits0_review.index_unit", self.index_unit),
            ("wits0_review.timezone", self.timezone),
            ("wits0_review.custom_profile_id", self.custom_profile_id),
            ("wits0_review.custom_profile_revision", self.custom_profile_revision),
        )
        for row, (key, widget) in enumerate(rows):
            layout.addWidget(QLabel(self._t(key), group), row, 0)
            layout.addWidget(widget, row, 1)
        layout.setColumnStretch(1, 1)

        self.dataset_name.editingFinished.connect(self._store_schema_fields)
        self.index_candidate.currentIndexChanged.connect(self._index_candidate_changed)
        self.index_mnemonic.editingFinished.connect(self._store_schema_fields)
        self.index_type.currentIndexChanged.connect(self._store_schema_fields)
        self.index_unit.editingFinished.connect(self._store_schema_fields)
        self.timezone.editingFinished.connect(self._store_schema_fields)
        self.custom_profile_id.editingFinished.connect(self._store_schema_fields)
        return group

    def _build_channel_table(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(self._t("wits0_review.channel_table"), panel))
        self.table = QTableWidget(panel)
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("wits0_review.column.include"),
                self._t("wits0_review.column.id"),
                self._t("wits0_review.column.source"),
                self._t("wits0_review.column.name"),
                self._t("wits0_review.column.type"),
                self._t("wits0_review.column.source_uom"),
                self._t("wits0_review.column.canonical"),
                self._t("wits0_review.column.kind"),
                self._t("wits0_review.column.canonical_uom"),
                self._t("wits0_review.column.confidence"),
                self._t("wits0_review.column.values"),
                self._t("wits0_review.column.samples"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selected_channel_changed)
        self.table.itemChanged.connect(self._include_changed)
        layout.addWidget(self.table, 1)
        return panel

    def _build_channel_editor(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0_review.channel_editor"), self)
        form = QFormLayout(group)
        self.channel_id = QLabel("—", group)
        self.channel_source = QLabel("—", group)
        self.channel_enabled = QCheckBox(self._t("wits0_review.channel_enabled"), group)
        self.channel_canonical = QLineEdit(group)
        self.channel_kind = QLineEdit(group)
        self.channel_quantity = QComboBox(group)
        for quantity in QuantityClass:
            self.channel_quantity.addItem(quantity.value, quantity)
        self.channel_source_uom = QLineEdit(group)
        self.channel_canonical_uom = QLineEdit(group)
        self.channel_samples = QLabel("—", group)
        self.channel_samples.setWordWrap(True)
        form.addRow(self._t("wits0_review.source_id"), self.channel_id)
        form.addRow(self._t("wits0_review.source_mnemonic"), self.channel_source)
        form.addRow(self.channel_enabled)
        form.addRow(self._t("wits0_review.canonical_mnemonic"), self.channel_canonical)
        form.addRow(self._t("wits0_review.canonical_kind"), self.channel_kind)
        form.addRow(self._t("wits0_review.quantity_class"), self.channel_quantity)
        form.addRow(self._t("wits0_review.source_uom"), self.channel_source_uom)
        form.addRow(self._t("wits0_review.canonical_uom"), self.channel_canonical_uom)
        form.addRow(self._t("wits0_review.samples"), self.channel_samples)
        note = QLabel(self._t("wits0_review.uom_note"), group)
        note.setWordWrap(True)
        form.addRow(note)
        self.channel_enabled.toggled.connect(self._store_channel_editor)
        self.channel_canonical.editingFinished.connect(self._store_channel_editor)
        self.channel_kind.editingFinished.connect(self._store_channel_editor)
        self.channel_quantity.currentIndexChanged.connect(self._store_channel_editor)
        self.channel_source_uom.editingFinished.connect(self._store_channel_editor)
        self.channel_canonical_uom.editingFinished.connect(self._store_channel_editor)
        return group

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0_review.qc_group"), self)
        layout = QVBoxLayout(group)
        self.review_summary = QLabel(group)
        self.review_summary.setWordWrap(True)
        layout.addWidget(self.review_summary)
        self.issue_list = QListWidget(group)
        self.issue_list.setMaximumHeight(145)
        layout.addWidget(self.issue_list)
        return group

    def _load_plan(self) -> None:
        self._updating = True
        self.dataset_name.setText(self.plan.dataset_name)
        candidate_row = self.index_candidate.findData(self.plan.index_candidate_id)
        self.index_candidate.setCurrentIndex(max(0, candidate_row))
        self.index_mnemonic.setText(self.plan.index_mnemonic)
        type_row = self.index_type.findData(self.plan.index_type)
        self.index_type.setCurrentIndex(max(0, type_row))
        self.index_unit.setText(self.plan.index_unit or "")
        self.timezone.setText(self.plan.timezone or "")
        self.custom_profile_id.setText(self.plan.custom_profile_id)
        revision = self.plan.custom_profile_revision
        if self.profile_directory is not None:
            revision = next_wits0_custom_profile_revision(
                self.profile_directory,
                self.plan.custom_profile_id,
            )
            self.plan = replace(self.plan, custom_profile_revision=revision)
        self.custom_profile_revision.setText(str(revision))
        self._updating = False

    def _store_schema_fields(self) -> None:
        if self._updating:
            return
        index_type = self.index_type.currentData()
        custom_profile_id = self.custom_profile_id.text().strip()
        revision = self.plan.custom_profile_revision
        if self.profile_directory is not None and custom_profile_id:
            revision = next_wits0_custom_profile_revision(
                self.profile_directory,
                custom_profile_id,
            )
        self.plan = replace(
            self.plan,
            dataset_name=self.dataset_name.text().strip(),
            index_candidate_id=str(self.index_candidate.currentData()),
            index_mnemonic=self.index_mnemonic.text().strip(),
            index_type=index_type if isinstance(index_type, IndexType) else IndexType(str(index_type)),
            index_unit=self.index_unit.text().strip() or None,
            timezone=self.timezone.text().strip() or None,
            custom_profile_id=custom_profile_id,
            custom_profile_revision=revision,
        )
        self.custom_profile_revision.setText(str(revision))
        self._refresh_review()

    def _index_candidate_changed(self) -> None:
        if self._updating:
            return
        candidate_id = str(self.index_candidate.currentData())
        candidate = next(
            (
                item
                for item in self.controller.index_candidates(self.snapshot)
                if item.candidate_id == candidate_id
            ),
            None,
        )
        if candidate is not None:
            self._updating = True
            self.index_mnemonic.setText(candidate.mnemonic)
            row = self.index_type.findData(candidate.index_type)
            self.index_type.setCurrentIndex(max(0, row))
            self.index_unit.setText(candidate.canonical_uom or "")
            self.timezone.setText("UTC" if candidate.source_kind == "header_datetime" else "")
            self._updating = False
        self._store_schema_fields()

    def _populate_table(self, review: Wits0ImportReview) -> None:
        selected = self._selected_key()
        self._updating = True
        self.table.setRowCount(len(review.channels))
        for row, channel in enumerate(review.channels):
            include = QTableWidgetItem()
            include.setData(Qt.ItemDataRole.UserRole, channel.key.source_id)
            include.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            include.setCheckState(
                Qt.CheckState.Checked
                if channel.import_enabled
                else Qt.CheckState.Unchecked
            )
            self.table.setItem(row, 0, include)
            values = (
                channel.key.source_id,
                channel.source_mnemonic,
                channel.source_name,
                channel.value_kind,
                channel.source_uom or "—",
                channel.canonical_mnemonic,
                channel.canonical_kind,
                channel.canonical_uom or "—",
                f"{channel.confidence:.2f}",
                f"{channel.valid_count}/{channel.observed_count}",
                ", ".join(channel.samples) or "—",
            )
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, channel.key.source_id)
                self.table.setItem(row, column, item)
            if selected == channel.key:
                self.table.selectRow(row)
        self.table.resizeColumnsToContents()
        if selected is None and review.channels:
            self.table.selectRow(0)
        self._updating = False
        self._selected_channel_changed()

    def _refresh_review(self) -> None:
        if self._updating:
            return
        try:
            review = self.controller.preview(self.snapshot, self.profile, self.plan)
        except ValueError as exc:
            self.review_summary.setText(self._t("wits0_review.invalid_plan", error=str(exc)))
            self.issue_list.clear()
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self._populate_table(review)
        self.issue_list.clear()
        for issue in review.issues:
            self.issue_list.addItem(f"[{issue.severity.value}] {issue.code}: {issue.message}")
        for channel in review.channels:
            for issue in channel.issues:
                self.issue_list.addItem(
                    f"[{issue.severity.value}] {channel.key.source_id} {issue.code}: {issue.message}"
                )
        enabled = sum(item.import_enabled for item in review.channels)
        self.review_summary.setText(
            self._t(
                "wits0_review.summary",
                channels=len(review.channels),
                enabled=enabled,
                candidates=len(review.index_candidates),
                warnings=review.warning_count,
                errors=review.error_count,
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            review.error_count == 0 and review.schema_preview is not None
        )

    def _selected_key(self) -> Wits0ChannelKey | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return Wits0ChannelKey.parse(str(value)) if value else None

    def _selected_channel_changed(self) -> None:
        key = self._selected_key()
        override = next((item for item in self.plan.channels if item.key == key), None)
        channel = self.snapshot.channel(key) if key is not None else None
        self._updating = True
        enabled = override is not None and channel is not None
        for widget in (
            self.channel_enabled,
            self.channel_canonical,
            self.channel_kind,
            self.channel_quantity,
            self.channel_source_uom,
            self.channel_canonical_uom,
        ):
            widget.setEnabled(enabled)
        if override is None or channel is None:
            self.channel_id.setText("—")
            self.channel_source.setText("—")
            self.channel_enabled.setChecked(False)
            self.channel_canonical.clear()
            self.channel_kind.clear()
            self.channel_source_uom.clear()
            self.channel_canonical_uom.clear()
            self.channel_samples.setText("—")
        else:
            self.channel_id.setText(channel.key.source_id)
            self.channel_source.setText(channel.source_mnemonic)
            self.channel_enabled.setChecked(override.import_enabled)
            self.channel_canonical.setText(override.canonical_mnemonic)
            self.channel_kind.setText(override.canonical_kind)
            row = self.channel_quantity.findData(override.quantity_class)
            self.channel_quantity.setCurrentIndex(max(0, row))
            self.channel_source_uom.setText(override.source_uom or "")
            self.channel_canonical_uom.setText(override.canonical_uom or "")
            self.channel_samples.setText(", ".join(channel.samples) or "—")
        self._updating = False

    def _store_channel_editor(self) -> None:
        if self._updating:
            return
        key = self._selected_key()
        if key is None:
            return
        quantity = self.channel_quantity.currentData()
        replacement = None
        for item in self.plan.channels:
            if item.key == key:
                replacement = replace(
                    item,
                    import_enabled=self.channel_enabled.isChecked(),
                    canonical_mnemonic=self.channel_canonical.text().strip(),
                    canonical_kind=self.channel_kind.text().strip(),
                    quantity_class=(
                        quantity if isinstance(quantity, QuantityClass) else QuantityClass(str(quantity))
                    ),
                    source_uom=self.channel_source_uom.text().strip() or None,
                    canonical_uom=self.channel_canonical_uom.text().strip() or None,
                )
                break
        if replacement is None:
            return
        self.plan = replace(
            self.plan,
            channels=tuple(
                replacement if item.key == key else item for item in self.plan.channels
            ),
        )
        self._refresh_review()

    def _include_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != 0:
            return
        key_value = item.data(Qt.ItemDataRole.UserRole)
        if not key_value:
            return
        key = Wits0ChannelKey.parse(str(key_value))
        enabled = item.checkState() is Qt.CheckState.Checked
        self.plan = replace(
            self.plan,
            channels=tuple(
                replace(channel, import_enabled=enabled) if channel.key == key else channel
                for channel in self.plan.channels
            ),
        )
        self._refresh_review()

    def _accept_review(self) -> None:
        self._store_schema_fields()
        try:
            self.commit_result = self.controller.commit(
                self.snapshot,
                self.profile,
                self.plan,
            )
        except (ValueError, Wits0ImportReviewValidationError) as exc:
            QMessageBox.critical(self, self._t("wits0_review.title"), str(exc))
            return
        self.accept()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
