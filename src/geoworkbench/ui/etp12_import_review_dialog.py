from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import IndexType
from geoworkbench.services.etp12_import_review import (
    Etp12ChannelOverride,
    Etp12DiscoverySnapshot,
    Etp12ImportReviewCommit,
    Etp12ImportReviewController,
    Etp12ImportReviewPlan,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.uom_dictionary import QuantityClass


class Etp12ImportReviewDialog(QDialog):
    """Operator confirmation boundary for live ETP channel mapping."""

    def __init__(
        self,
        snapshot: Etp12DiscoverySnapshot,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        controller: Etp12ImportReviewController | None = None,
        initial_plan: Etp12ImportReviewPlan | None = None,
    ) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self.controller = controller or Etp12ImportReviewController()
        self.localizer = Localizer.create(language)
        self.plan = initial_plan or self.controller.initial_plan(snapshot)
        self.commit_result: Etp12ImportReviewCommit | None = None
        self.setWindowTitle(self._t("etp12.review_title"))
        self.resize(1100, 720)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.dataset_name = QLineEdit(self.plan.dataset_name, self)
        self.index_type = QComboBox(self)
        for value in IndexType:
            self.index_type.addItem(value.value, value)
        self.index_type.setCurrentIndex(max(0, self.index_type.findData(self.plan.index_type)))
        self.index_mnemonic = QLineEdit(self.plan.index_mnemonic, self)
        self.index_source_uom = QLineEdit(self.plan.index_source_uom or "", self)
        self.index_target_uom = QLineEdit(self.plan.index_canonical_uom or "", self)
        form.addRow(self._t("etp12.review_dataset"), self.dataset_name)
        form.addRow(self._t("etp12.review_index_type"), self.index_type)
        form.addRow(self._t("etp12.review_index_mnemonic"), self.index_mnemonic)
        form.addRow(self._t("etp12.review_index_source_uom"), self.index_source_uom)
        form.addRow(self._t("etp12.review_index_target_uom"), self.index_target_uom)
        root.addLayout(form)

        self.table = QTableWidget(len(snapshot.channels), 9, self)
        self.table.setHorizontalHeaderLabels(
            [
                self._t("etp12.review_enabled"),
                self._t("etp12.review_channel"),
                self._t("etp12.review_data_kind"),
                self._t("etp12.review_source_uom"),
                self._t("etp12.review_canonical"),
                self._t("etp12.review_semantic"),
                self._t("etp12.review_quantity"),
                self._t("etp12.review_target_uom"),
                self._t("etp12.review_samples"),
            ]
        )
        override_by_uri = {item.channel_uri: item for item in self.plan.channels}
        self._checks: list[QCheckBox] = []
        for row, channel in enumerate(snapshot.channels):
            override = override_by_uri[channel.channel_uri]
            check = QCheckBox(self.table)
            check.setChecked(override.import_enabled)
            self._checks.append(check)
            self.table.setCellWidget(row, 0, check)
            for column, text in (
                (1, channel.channel_name),
                (2, channel.data_kind or ""),
                (3, override.source_uom or ""),
                (4, override.canonical_mnemonic or ""),
                (5, override.canonical_kind or ""),
                (
                    6,
                    override.quantity_class.value
                    if isinstance(override.quantity_class, QuantityClass)
                    else str(override.quantity_class or QuantityClass.UNKNOWN.value),
                ),
                (7, override.canonical_uom or ""),
                (8, ", ".join(channel.samples)),
            ):
                item = QTableWidgetItem(text)
                if column in {1, 2, 8}:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 1:
                    item.setData(Qt.ItemDataRole.UserRole, channel.channel_uri)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        root.addWidget(self.table, 1)

        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.issues = QPlainTextEdit(self)
        self.issues.setReadOnly(True)
        self.issues.setMaximumHeight(150)
        root.addWidget(self.issues)

        actions = QHBoxLayout()
        self.preview_button = QDialogButtonBox(self)
        self.preview_button.addButton(
            self._t("etp12.review_validate"), QDialogButtonBox.ButtonRole.ActionRole
        ).clicked.connect(self._preview)
        actions.addWidget(self.preview_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)
        self._preview()

    def _t(self, key: str, **kwargs: object) -> str:
        return self.localizer.text(key, **kwargs)

    def _collect_plan(self) -> Etp12ImportReviewPlan:
        overrides: list[Etp12ChannelOverride] = []
        existing = {item.channel_uri: item for item in self.plan.channels}
        for row, channel in enumerate(self.snapshot.channels):
            current = existing[channel.channel_uri]
            quantity_text = self._cell_text(row, 6)
            try:
                quantity = QuantityClass(quantity_text)
            except ValueError:
                quantity = QuantityClass.UNKNOWN
            overrides.append(
                replace(
                    current,
                    import_enabled=self._checks[row].isChecked(),
                    source_uom=self._cell_text(row, 3) or None,
                    canonical_mnemonic=self._cell_text(row, 4) or None,
                    canonical_kind=self._cell_text(row, 5) or None,
                    quantity_class=quantity,
                    canonical_uom=self._cell_text(row, 7) or None,
                )
            )
        index_type = self.index_type.currentData()
        if not isinstance(index_type, IndexType):
            raise ValueError("ETP Import Review requires a valid index type")
        return replace(
            self.plan,
            dataset_name=self.dataset_name.text().strip(),
            index_mnemonic=self.index_mnemonic.text().strip(),
            index_type=index_type,
            index_source_uom=self.index_source_uom.text().strip() or None,
            index_canonical_uom=self.index_target_uom.text().strip() or None,
            timezone="UTC" if index_type is IndexType.DATETIME else None,
            channels=tuple(overrides),
        )

    def _cell_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        if item is None:
            raise ValueError(
                f"ETP Import Review table cell ({row}, {column}) is missing"
            )
        return item.text().strip()

    def _preview(self) -> None:
        try:
            self.plan = self._collect_plan()
            review = self.controller.preview(self.snapshot, self.plan)
        except Exception as exc:  # noqa: BLE001
            self.summary.setText(str(exc))
            return
        self.summary.setText(
            self._t(
                "etp12.review_summary",
                channels=sum(item.import_enabled for item in review.channels),
                warnings=review.warning_count,
                errors=review.error_count,
            )
        )
        messages = [f"[{item.severity.value}] {item.code}: {item.message}" for item in review.issues]
        messages.extend(
            f"[{issue.severity.value}] {issue.code}: {issue.message}"
            for channel in review.channels
            for issue in channel.issues
        )
        self.issues.setPlainText("\n".join(messages) or self._t("etp12.review_no_issues"))

    def _commit(self) -> None:
        try:
            self.plan = self._collect_plan()
            self.commit_result = self.controller.commit(self.snapshot, self.plan)
        except Exception as exc:  # noqa: BLE001
            self.summary.setText(str(exc))
            self._preview()
            return
        self.accept()
