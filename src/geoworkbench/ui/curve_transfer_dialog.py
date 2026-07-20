from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.services.curve_transfer import CurveTransferAnalysis
from geoworkbench.services.localization import AppLanguage, Localizer


class CurveTransferDialog(QDialog):
    def __init__(
        self,
        controller: CurveTransferController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.analysis: CurveTransferAnalysis | None = None
        self.setWindowTitle(self._t("transfer.title"))
        self.resize(760, 480)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.source_combo = QComboBox()
        for dataset in controller.available_sources():
            self.source_combo.addItem(dataset.name, dataset.dataset_id)
        form.addRow(self._t("transfer.source"), self.source_combo)
        root.addLayout(form)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setObjectName("curve-transfer-preview")
        root.addWidget(self.preview)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("curve-transfer-candidates")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("transfer.use"),
                self._t("data.mnemonic"),
                self._t("data.unit"),
                self._t("data.missing"),
                self._t("transfer.status"),
            ]
        )
        self.table.itemChanged.connect(self._update_accept_state)
        root.addWidget(self.table)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("transfer.apply"))
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.source_combo.currentIndexChanged.connect(self._refresh_analysis)
        self._refresh_analysis()

    @property
    def source_dataset_id(self) -> str | None:
        value = self.source_combo.currentData()
        return value if isinstance(value, str) else None

    @property
    def selected_curve_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            curve_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if (
                item is not None
                and item.checkState() == Qt.CheckState.Checked
                and isinstance(curve_id, str)
            ):
                selected.append(curve_id)
        return tuple(selected)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh_analysis(self) -> None:
        source_id = self.source_dataset_id
        if source_id is None:
            self.analysis = None
            self.table.setRowCount(0)
            self.preview.setText(self._t("transfer.no_source"))
            self._update_accept_state()
            return
        try:
            analysis = self.controller.analyze(source_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            self.analysis = None
            self.table.setRowCount(0)
            self.preview.setText(self._t("transfer.invalid", error=str(exc)))
            self._update_accept_state()
            return
        self.analysis = analysis
        self.preview.setText(
            self._t(
                "transfer.preview",
                mapping=self._t(f"transfer.mapping.{analysis.mapping.value}"),
                available=len(analysis.transferable),
                total=len(analysis.candidates),
            )
        )
        self.table.blockSignals(True)
        self.table.setRowCount(len(analysis.candidates))
        for row, candidate in enumerate(analysis.candidates):
            use_item = QTableWidgetItem()
            use_item.setData(Qt.ItemDataRole.UserRole, candidate.curve_id)
            use_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            use_item.setCheckState(
                Qt.CheckState.Checked if candidate.conflict is None else Qt.CheckState.Unchecked
            )
            if candidate.conflict is not None:
                use_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 0, use_item)
            for column, value in enumerate(
                (
                    candidate.mnemonic,
                    candidate.unit or "—",
                    str(candidate.missing_count),
                    self._conflict_text(candidate.conflict),
                ),
                start=1,
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self._update_accept_state()

    def _conflict_text(self, conflict: str | None) -> str:
        if conflict is None:
            return self._t("transfer.ready")
        return {
            "Мнемоника занята кривой приёмника": self._t("transfer.conflict.curve"),
            "Мнемоника зарезервирована индексом приёмника": self._t("transfer.conflict.index"),
        }.get(conflict, conflict)

    def _update_accept_state(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self.analysis is not None and bool(self.selected_curve_ids)
        )

    def _accept_validated(self) -> None:
        if (
            self.analysis is not None
            and self.source_dataset_id is not None
            and self.selected_curve_ids
        ):
            self.accept()
