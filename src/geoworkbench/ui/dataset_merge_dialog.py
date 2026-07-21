from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.services.dataset_merge import (
    DatasetMergeAnalysis,
    MergeOverlapPolicy,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.las_output_paths import available_las_output_path


class DatasetMergeDialog(QDialog):
    def __init__(
        self,
        controller: DatasetMergeController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.analysis: DatasetMergeAnalysis | None = None
        self.setWindowTitle(self._t("merge.title"))
        self.resize(680, 430)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.source_combo = QComboBox()
        for dataset in controller.available_sources():
            self.source_combo.addItem(dataset.name, dataset.dataset_id)
        form.addRow(self._t("merge.source"), self.source_combo)
        self.policy_combo = QComboBox()
        for policy in MergeOverlapPolicy:
            self.policy_combo.addItem(self._t(f"merge.policy.{policy.value}"), policy)
        self.policy_combo.setCurrentIndex(
            self.policy_combo.findData(MergeOverlapPolicy.PRESERVE_EXISTING)
        )
        form.addRow(self._t("merge.policy"), self.policy_combo)
        root.addLayout(form)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel(self._t("las_editor.output_file")))
        self.output_input = QLineEdit()
        target = controller.session.current_dataset
        target_name = target.name if target is not None else "merged"
        self.output_input.setText(str(available_las_output_path(Path.cwd() / f"{target_name}_merged.las")))
        self.output_input.textChanged.connect(self._update_accept_state)
        output_row.addWidget(self.output_input, 1)
        output_button = QPushButton(self._t("las_editor.choose_output"))
        output_button.clicked.connect(self._browse_output)
        output_row.addWidget(output_button)
        root.addLayout(output_row)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setObjectName("dataset-merge-preview")
        root.addWidget(self.preview)
        root.addWidget(QLabel(self._t("merge.conflicts")))
        self.conflicts = QListWidget()
        self.conflicts.setObjectName("dataset-merge-conflicts")
        root.addWidget(self.conflicts)
        self.note = QLabel(self._t("merge.note"))
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("merge.create"))
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.source_combo.currentIndexChanged.connect(self._refresh_analysis)
        self.policy_combo.currentIndexChanged.connect(self._refresh_analysis)
        self._refresh_analysis()

    @property
    def source_dataset_id(self) -> str | None:
        value = self.source_combo.currentData()
        return value if isinstance(value, str) else None

    @property
    def output_path(self) -> Path | None:
        value = self.output_input.text().strip()
        if not value:
            return None
        path = Path(value)
        return path if path.suffix.casefold() == ".las" else path.with_suffix(".las")

    @property
    def overlap_policy(self) -> MergeOverlapPolicy:
        value = self.policy_combo.currentData()
        return value if isinstance(value, MergeOverlapPolicy) else MergeOverlapPolicy(value)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh_analysis(self) -> None:
        self.conflicts.clear()
        source_id = self.source_dataset_id
        if source_id is None:
            self.analysis = None
            self.preview.setText(self._t("merge.no_source"))
            self._update_accept_state()
            return
        try:
            analysis = self.controller.analyze(source_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            self.analysis = None
            self.preview.setText(self._t("merge.invalid", error=str(exc)))
            self._update_accept_state()
            return
        self.analysis = analysis
        self.preview.setText(
            self._t(
                "merge.preview_extended",
                source=analysis.source_sample_count,
                target=analysis.target_sample_count,
                merged=analysis.merged_sample_count,
                overlap=analysis.overlap_sample_count,
                merged_curves=analysis.merged_curve_count,
                source_only=analysis.source_only_curve_count,
                target_only=analysis.target_only_curve_count,
                value_conflicts=analysis.overlap_value_conflict_count,
            )
        )
        if analysis.mnemonic_conflicts:
            for mnemonic in analysis.mnemonic_conflicts:
                self.conflicts.addItem(self._t("merge.shared_curve", mnemonic=mnemonic))
        if analysis.metadata_conflicts:
            for conflict in analysis.metadata_conflicts:
                self.conflicts.addItem(self._t("merge.metadata_conflict", conflict=conflict))
        if not analysis.mnemonic_conflicts and not analysis.metadata_conflicts:
            self.conflicts.addItem(self._t("merge.no_conflicts"))
        self._update_accept_state()

    def _browse_output(self) -> None:
        initial = self.output_path or (Path.cwd() / "merged.las")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("las_editor.choose_output_title"),
            str(initial),
            "LAS (*.las)",
        )
        if filename:
            self.output_input.setText(str(Path(filename).with_suffix(".las")))

    def _update_accept_state(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self.analysis is not None
            and self.analysis.can_merge
            and self.output_path is not None
        )

    def _accept_validated(self) -> None:
        if (
            self.analysis is not None
            and self.analysis.can_merge
            and self.source_dataset_id is not None
        ):
            self.accept()
