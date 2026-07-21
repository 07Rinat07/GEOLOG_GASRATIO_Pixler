from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.services.external_las_insert import (
    ExternalLasCurveSelection,
    ExternalLasInsertAnalysis,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class ExternalLasInsertDialog(QDialog):
    def __init__(
        self,
        controller: ExternalLasInsertController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        initial_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.analysis: ExternalLasInsertAnalysis | None = None
        self.setWindowTitle(self._t("external_las.title"))
        self.resize(980, 620)

        root = QVBoxLayout(self)
        file_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText(self._t("external_las.choose_hint"))
        file_row.addWidget(self.path_input, 1)
        self.browse_button = QPushButton(self._t("external_las.browse"))
        self.browse_button.clicked.connect(self._browse)
        file_row.addWidget(self.browse_button)
        root.addLayout(file_row)

        self.summary = QLabel(self._t("external_las.no_source"))
        self.summary.setWordWrap(True)
        self.summary.setObjectName("external-las-summary")
        root.addWidget(self.summary)

        self.issues = QListWidget()
        self.issues.setObjectName("external-las-issues")
        self.issues.setMaximumHeight(110)
        root.addWidget(self.issues)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("external-las-curves")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("external_las.use"),
                self._t("external_las.source_mnemonic"),
                self._t("external_las.unit"),
                self._t("external_las.description"),
                self._t("external_las.target_mnemonic"),
                self._t("external_las.display_name"),
                self._t("external_las.samples"),
            ]
        )
        self.table.itemChanged.connect(self._update_accept_state)
        root.addWidget(self.table, 1)

        note = QLabel(self._t("external_las.safe_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("external_las.insert")
        )
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        if initial_path is not None:
            self.load_path(initial_path)
        else:
            self._update_accept_state()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @property
    def selections(self) -> tuple[ExternalLasCurveSelection, ...]:
        result: list[ExternalLasCurveSelection] = []
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, 0)
            if use_item is None or use_item.checkState() != Qt.CheckState.Checked:
                continue
            source_curve_id = use_item.data(Qt.ItemDataRole.UserRole)
            target_item = self.table.item(row, 4)
            display_item = self.table.item(row, 5)
            if not isinstance(source_curve_id, str) or target_item is None:
                continue
            result.append(
                ExternalLasCurveSelection(
                    source_curve_id=source_curve_id,
                    target_mnemonic=target_item.text(),
                    display_name=display_item.text() if display_item is not None else "",
                )
            )
        return tuple(result)

    def load_path(self, path: str | Path) -> None:
        source = Path(path)
        self.path_input.setText(str(source))
        self.issues.clear()
        try:
            analysis = self.controller.analyze_file(source)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            self.analysis = None
            self.table.setRowCount(0)
            self.summary.setText(self._t("external_las.invalid", error=str(exc)))
            self.issues.addItem(str(exc))
            self._update_accept_state()
            return
        self.analysis = analysis
        self.summary.setText(
            self._t(
                "external_las.summary",
                source_min=f"{analysis.source_depth_min:g}",
                source_max=f"{analysis.source_depth_max:g}",
                target_min=f"{analysis.target_depth_min:g}",
                target_max=f"{analysis.target_depth_max:g}",
                unit=analysis.target_depth_unit,
                overlap_min=f"{analysis.overlap_top:g}",
                overlap_max=f"{analysis.overlap_bottom:g}",
                mapping=self._t(f"external_las.mapping.{analysis.mapping.value}"),
                count=len(analysis.candidates),
            )
        )
        if analysis.source_reversed_in_memory:
            self.issues.addItem(self._t("external_las.reversed_source"))
        if analysis.depth_conversion_factor != 1.0:
            self.issues.addItem(
                self._t(
                    "external_las.depth_converted",
                    source=analysis.source_depth_unit,
                    target=analysis.target_depth_unit,
                )
            )
        self._populate_table(analysis)
        self._update_accept_state()

    def _populate_table(self, analysis: ExternalLasInsertAnalysis) -> None:
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(analysis.candidates))
            for row, candidate in enumerate(analysis.candidates):
                use_item = QTableWidgetItem()
                use_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                use_item.setCheckState(Qt.CheckState.Checked)
                use_item.setData(Qt.ItemDataRole.UserRole, candidate.source_curve_id)
                self.table.setItem(row, 0, use_item)
                self.table.setItem(row, 1, _readonly_item(candidate.source_mnemonic))
                self.table.setItem(row, 2, _readonly_item(candidate.source_unit or "—"))
                self.table.setItem(row, 3, _readonly_item(candidate.source_description or "—"))
                self.table.setItem(row, 4, QTableWidgetItem(candidate.suggested_mnemonic))
                self.table.setItem(
                    row,
                    5,
                    QTableWidgetItem(candidate.source_description or candidate.source_mnemonic),
                )
                self.table.setItem(
                    row,
                    6,
                    _readonly_item(
                        self._t(
                            "external_las.sample_counts",
                            finite=candidate.finite_count,
                            missing=candidate.missing_count,
                        )
                    ),
                )
        finally:
            self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self._t("external_las.choose_title"),
            str(Path.cwd()),
            "LAS (*.las)",
        )
        if filename:
            self.load_path(filename)

    def _update_accept_state(self) -> None:
        selected = self.selections
        valid = self.analysis is not None and bool(selected)
        names = [item.target_mnemonic.strip().casefold() for item in selected]
        valid = valid and all(names) and len(set(names)) == len(names)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)

    def _accept_validated(self) -> None:
        if self.analysis is not None and self.selections:
            self.accept()


def _readonly_item(value: str) -> QTableWidgetItem:
    item = QTableWidgetItem(value)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item
