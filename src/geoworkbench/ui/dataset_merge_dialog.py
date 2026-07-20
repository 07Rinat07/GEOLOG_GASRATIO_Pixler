from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.services.dataset_merge import DatasetMergeAnalysis
from geoworkbench.services.localization import AppLanguage, Localizer


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
        self.resize(620, 360)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.source_combo = QComboBox()
        for dataset in controller.available_sources():
            self.source_combo.addItem(dataset.name, dataset.dataset_id)
        form.addRow(self._t("merge.source"), self.source_combo)
        root.addLayout(form)
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
        self._refresh_analysis()

    @property
    def source_dataset_id(self) -> str | None:
        value = self.source_combo.currentData()
        return value if isinstance(value, str) else None

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
                "merge.preview",
                source=analysis.source_sample_count,
                target=analysis.target_sample_count,
                merged=analysis.merged_sample_count,
                overlap=analysis.overlap_sample_count,
            )
        )
        if analysis.mnemonic_conflicts:
            self.conflicts.addItems(analysis.mnemonic_conflicts)
        else:
            self.conflicts.addItem(self._t("merge.no_conflicts"))
        self._update_accept_state()

    def _update_accept_state(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self.analysis is not None and self.analysis.can_merge
        )

    def _accept_validated(self) -> None:
        if (
            self.analysis is not None
            and self.analysis.can_merge
            and self.source_dataset_id is not None
        ):
            self.accept()
